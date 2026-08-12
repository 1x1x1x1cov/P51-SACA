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
- `GET /keywords` — full Swahili symptom keyword list (for frontend dropdowns/autocomplete)

## Running a classifier standalone (no server needed)

Each classifier can be run directly for quick testing, without starting the API:

```
python3 -m classifier.rule_based
```

This runs the built-in test cases in that file and prints the results.

## Adding a new classifier (Random Forest, SVM, Logistic Regression, hybrid)

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
4. To wire it into the API, swap the `active_classifier` line in `main.py`.

## Regenerating the training dataset

If `Symptom-severity.csv` or `dataset.csv` change, regenerate the cleaned dataset:

```
python3 prepare_dataset.py
```

This writes `saca_dataset.csv` and prints the severity tier distribution so you can sanity check it before committing.

## Common issues

- **`ModuleNotFoundError: No module named 'classifier'`** — you're running a classifier file directly (`python3 classifier/rule_based.py`) instead of as a module (`python3 -m classifier.rule_based`). Always run from the repo root using the `-m` form for anything inside the `classifier/` package.
- **Empty `/sessions` after restarting the server** — check you're launching `uvicorn` from the same directory each time. `saca.db` is created relative to wherever you run the command from.