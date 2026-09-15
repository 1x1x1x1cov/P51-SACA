# SACA-2026-09-15-1 — main.py now actually runs LR; retire your standalone protos

**To:** Ryan, Azzam
**Cc:** Minh, Shayan, Hitesh
**From:** Minh (via Claude)
**Date:** 2026-09-15
**Status:** Done, verified, committed to `C:\Users\asus\Desktop\saca`. Not yet `git commit`ed — please review the diff first.

## What changed and why

`main.py` has been hardcoded to `active_classifier = RuleBasedClassifier()` this whole time — it never actually got switched over after the 2026-09-11 decision to make Logistic Regression the sole classifier (SVM dropped, Random Forest cancelled, rule_based retired entirely, no safety-net kept — see the project handoff doc's "TEAM AND SCOPE CHANGE" section if you want the full reasoning). That's the direct reason each of you ended up running your own separate script against your own classifier instead of the real app: the real `/classify` endpoint was never actually showing your model's output, so there was no way to see it working end-to-end without a workaround.

That's fixed now. `main.py` imports and runs `classifier/logistic_regression.py` directly — the same file `score_classifiers.py` and the comparison dashboard already use, not a copy. There is now exactly one place this classifier's logic lives.

## Files changed

- **`main.py`** — `active_classifier` is now `LogisticRegressionClassifier()`, trained eagerly at startup (so a missing/bad `saca_train.csv` fails loudly at launch, not silently on someone's first request).
- **`classifier/logistic_regression.py`** — two real bugs fixed, both already known and documented, neither actually closed before now:
  - `confidence` was computed (`np.max(predict_proba) * 100`) and only ever printed inside the `reason` string — never passed to `build_result()`, so the structured `confidence` field was always `None` no matter what the text said. Now passed correctly, and on the `0.0–1.0` scale `base.py` requires (was on a `0–100` scale, which would have raised `ValueError` on every single request the moment anyone wired it in without noticing the scale mismatch).
  - `symptoms` was passed as the raw input string instead of a token list, unlike every other classifier (`rule_based.py`, `svm.py`). Now `symptom_text.split()`, matching the rest.
  - Added explicit empty/whitespace-input handling (same convention and same message as `rule_based.py`/`svm.py`) — previously empty input would have gone straight into the model with no special case.
- **`svm_classifier.py`** (Azzam's original, at repo root) — path bug fixed: `self.project_root = Path(__file__).resolve().parent.parent` assumed this file lives one level inside `classifier/` (that comment was copied from `classifier/svm.py`, where it's actually true). It doesn't — it's at the repo root — so `.parent.parent` pointed one directory *above* the real repo, and running this as-is raised `FileNotFoundError` on `saca_train.csv` rather than training. Now `.parent`. Verified it actually finds the data and classifies now.
- **`tests/test_classify_endpoint.py`** — rewritten. This file's assertions were written entirely against `rule_based.py`'s behavior (Swahili input, a fixed recognised-symptom vocabulary, deterministic `CRITICAL_OVERRIDE_KEYWORDS`) and would have failed the instant anyone actually flipped the switch in `main.py` — which is presumably part of why nobody did. Rewritten against real LR/English behavior, with assertions grounded in verified model output, not guesses — e.g. the "returns CRITICAL" test now uses a real row from `saca_test.csv` that the trained model actually predicts CRITICAL on at 0.9874 confidence (checked directly), not a hardcoded keyword. See the file's own docstring for the full list of behavioral differences from the old rule_based-based tests (most importantly: LR has no filtered symptom vocabulary, so `symptoms` always reflects the raw input tokens, recognised or not — gibberish no longer comes back as `symptoms: []`).
- **`tests/test_classifier_base.py`** — one unrelated pre-existing stale assertion fixed: `test_output_contains_all_required_keys` didn't include `confidence` in its expected key set, even though `base.py`'s `build_result()` has always returned it. This was failing before any of the above changes — not something I introduced, just something already broken that fit the same "stale test" pattern.

## Verified, not assumed

- Full test suite: **32/32 passing** (`python3 -m pytest tests/ -q`).
- `score_classifiers.py` re-run clean: LR **69.6% accuracy / 66.4% F1**, SVM (`classifier/svm.py`) **identical** — matches the already-documented, already-verified numbers exactly, confirming this change didn't alter model behavior, only fixed the plumbing around it.
- `svm_classifier.py`'s fixed path resolves and trains successfully (spot-checked directly).
- Live `/classify` endpoint smoke-tested end to end via `TestClient`: real input, empty input, `/keywords`, `/` — all correct.

## What you each no longer need to do

- **Azzam:** you don't need to keep running `svm_classifier.py` as a workaround for anything production-related — it's fixed now if you want it (e.g. for the report's "we tried GridSearchCV tuning" narrative), but the actual reported SVM baseline (69.6%/66.4%, identical to LR per-row) already comes from `classifier/svm.py` via `score_classifiers.py`, which was never broken. SVM's role is finished — comparison baseline only, per the 09-11 decision.
- **Ryan:** if you've been running your own copy of your classifier separately to actually see it work (which, given `main.py` was permanently pointed at rule_based, you'd have had good reason to), you shouldn't need to anymore — `main.py` runs `classifier/logistic_regression.py` directly now, live, with both known bugs fixed in that shared file. If you do have a separate script, please retire it in favour of testing against `main.py` / `score_classifiers.py` directly, so there's one source of truth instead of two copies that can drift apart (which is exactly what happened here).

## What's *not* changed, deliberately

- `classifier/rule_based.py`, `rule_based_en.py`, and `svm.py` are untouched and still live in `classifier/` — they're not dead weight, `score_classifiers.py`'s auto-discovery still picks them up for comparison scoring and the dashboard. They're just not what `/classify` runs anymore, which is the actual 09-11 decision working as intended.
- No deterministic critical-keyword safety net exists in the live app. This is the already-accepted tradeoff from the 09-11 decision (rule_based dropped entirely, not kept even as a minimal backstop), not a gap introduced here — flagging it again only so it isn't rediscovered as a surprise later.

## Next step

Diff is sitting in the working tree, not committed. Please review and `git commit` when you're satisfied — I didn't commit on your behalf.
