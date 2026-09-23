# SACA — Dev Environment Setup

## Prerequisites

- Python 3.10+
- pip

## Setup

1. Clone the repo and `cd` into it.

2. Create a virtual environment:
   ```
   python3 -m venv venv
   source venv/bin/activate      # Mac/Linux
   venv\Scripts\activate         # Windows
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. (Optional, only needed for AMMU's LLM-phrased replies) Create a `.env` file in the repo root with:
   ```
   GROQ_API_KEY=your-key-here
   ```
   Get a free key at [console.groq.com/keys](https://console.groq.com/keys). `ammu_safety.py` reads this via `python-dotenv`. If it's unset, AMMU still works normally — `ammu_api.py` falls back to its fixed, non-LLM reply text whenever the Groq call fails or isn't configured, so this is not required to run the app.

## Running the API server

From the repo root:

```
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. The interactive docs are at `http://127.0.0.1:8000/docs`.

`saca.db` is created automatically on first run (in whatever directory you launched the server from). It's gitignored — don't commit it, each person's local DB is their own.

## Endpoints

- `GET /` — health check
- `POST /classify` — send `{"symptom_text": "..."}`, get back a severity result
- `GET /sessions` — all saved classification sessions, most recent first
- `GET /sync/pending` — unsynced sessions, for offline sync
- `POST /sync/confirm` — send `{"session_ids": [...]}` to mark sessions as synced
- `GET /keywords` — full Swahili symptom keyword list (for frontend dropdowns/autocomplete)
- `GET /ammu` — serves the AMMU conversational UI (`ammu.html`)
- `POST /ammu/respond` — send `{"user_text": "..."}`, get back a conversational reply plus severity. Classifies with the same active classifier as `/classify`, then optionally rephrases the reply via Groq (`ammu_safety.py`), gated by a safety check that always falls back to a fixed, verified-safe reply if the LLM call fails or the output doesn't pass

## Running a classifier standalone (no server needed)

Each classifier can be run directly for quick testing, without starting the API:

```
python3 -m classifier.logistic_regression
```

This runs the built-in test cases in that file and prints the results. (`python3 -m classifier.rule_based` still works too, but `rule_based.py` is not used by the live app — see below.)

## Classifier: Logistic Regression is the only one the app uses

Per the team's 2026-09-11 decision, **Logistic Regression is the sole classifier for both `/classify` and `/ammu/respond`.** `main.py` and `ammu_api.py` each construct their own `LogisticRegressionClassifier()`. `rule_based.py`, `rule_based_en.py`, and `svm.py` are kept in `classifier/` only so `score_classifiers.py` can still score them for comparison — they are not wired into the live app anywhere, and shouldn't be.

**If you're touching `main.py` or `ammu_api.py`, especially while merging another branch, double-check the `active_classifier` / `classifier` line still says `LogisticRegressionClassifier()` before you push.** This has already broken once (2026-09-23): a branch that forked before this decision existed got merged into `main` and silently reverted both files back to `RuleBasedClassifier()`, undoing the decision without anyone noticing until a later audit. `main` is now protected by a ruleset requiring a PR — review this specifically on any PR that touches either file.

## Adding a new classifier (comparison-only — not for the live app)

To add a classifier for `score_classifiers.py` to compare (not to make it active — see above):

1. Create a new file in `classifier/`, e.g. `classifier/random_forest.py`.
2. Subclass `BaseClassifier` from `classifier/base.py`:

   ```python
   from classifier.base import BaseClassifier

   class RandomForestClassifier(BaseClassifier):
       name = "random_forest"

       def classify(self, symptom_text: str) -> dict:
           # your logic here
           return self.build_result(severity, symptoms, reason)
   ```

3. `severity` must be one of `"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"` — `build_result()` will raise an error if it isn't, so mistakes get caught immediately rather than silently breaking the frontend.
4. `score_classifiers.py` auto-discovers it — no other wiring needed. Do **not** swap it into `main.py`'s or `ammu_api.py`'s active classifier without an explicit team decision, per the section above.

## Regenerating the training dataset

If `Symptom-severity.csv` or `dataset.csv` change, regenerate the cleaned dataset:

```
python3 prepare_dataset.py
```

This writes `saca_dataset.csv` and prints the severity tier distribution so you can sanity check it before committing.

`saca_train.csv`/`saca_test.csv` are bilingual (English + Swahili) and must stay leak-free: no `symptom_text` value may appear in both files. Before committing any change to either file, verify directly:

```python
import pandas as pd
train = pd.read_csv("saca_train.csv")
test = pd.read_csv("saca_test.csv")
assert not (set(train["symptom_text"]) & set(test["symptom_text"])), "train/test leakage!"
```

This isn't a formality — it broke twice already (Sept 9 and Sept 22), both times because a "corrected" or "post-fix" file was trusted by its name/label instead of actually checked.

## Common issues

- **`ModuleNotFoundError: No module named 'classifier'`** — you're running a classifier file directly (`python3 classifier/rule_based.py`) instead of as a module (`python3 -m classifier.rule_based`). Always run from the repo root using the `-m` form for anything inside the `classifier/` package.
- **Empty `/sessions` after restarting the server** — check you're launching `uvicorn` from the same directory each time. `saca.db` is created relative to wherever you run the command from.
- **AMMU replies always use the fixed/canned text, never the LLM phrasing** — either `GROQ_API_KEY` isn't set (see Setup step 4) or the LLM's reply is failing `ammu_safety.py`'s safety check (it's a fairly strict keyword match — see `ammu_log.txt` for real pass/fail examples). This is expected behavior, not a bug: the fallback is intentional and safe.
