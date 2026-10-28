# SACA dataset v2 (draft for clinician review)

The app trains on `dataset_v2/saca_v2_train.csv`. The old `saca_train.csv` / `saca_test.csv` are kept only because `svm_classifier.py` and `score_classifiers.py` still read them.

## What was wrong with v1
Labels were the sum of per-symptom weights (`Symptom-severity.csv`) bucketed at 13/25/40, so "severity" was close to "number of symptoms"; `coma` alone summed to LOW. 76% of the 16,812 training rows were three Swahili sentence templates around the same ~240 English combinations (1,716 distinct texts), and the test file shared texts with the train file.

## How v2 labels a symptom set S
`label(S) = max( red-flag floor(S), disease tier(S) )`

* **red-flag floor** - highest `min_tier` of any rule in `red_flags.csv` whose codes are all present (89 rules; WHO ETAT / IMCI / WHO-ICRC Basic Emergency Care / pregnancy and snakebite danger signs / the team's own override list; every rule is DRAFT).
* **disease tier** (`disease_urgency.csv`, 41 diseases, DRAFT):
  * S is one of the 304 distinct Kaggle combinations: highest tier of the diseases that produced it (0 conflicts).
  * S is a partial presentation (1-3 symptoms from one disease's pool): the **lowest** tier among the diseases that can produce it. `python build_dataset_v2.py median|max` switches policy; 356 of 8,279 labels differ between min and max.
  * **Non-specific cap:** a partial presentation made only of symptoms in `nonspecific_symptoms.csv` (headache, nausea, vomiting, fatigue, malaise, loss of appetite, muscle/joint/back pain, dizziness, cough, abdominal pain) is capped at MEDIUM on disease grounds. 82 sets changed. Without it `fatigue headache nausea` was HIGH, only because Dengue, Typhoid and Hypoglycemia are the only diseases in this data that contain all three.

Rows are distinct symptom sets in sorted code order: 8,279 sets (304 observed Kaggle combinations, 4,613 partial, 3,362 synthetic red-flag sets), split 80/20 on distinct sets stratified by label (6,624 / 1,655, asserted disjoint). 47 codes absent from the Kaggle data (`convulsions`, `snake_bite`, `head_injury`, `pregnancy`, ...) exist only in synthetic rows. The class mix is partly an artefact of those rows (CRITICAL is about 17%), not a prevalence.

## Reproduce
```
cd dataset_v2
python build_dataset_v2.py      # writes saca_v2_*.csv + build_report_v2.txt
python train_eval_v2.py         # writes eval_report_v2.txt
```
Re-running gives byte-identical files.

## Results (same LR settings as `classifier/logistic_regression.py`)
| on the v2 test file (1,655 sets) | accuracy | CRITICAL recall | true HIGH/CRIT predicted LOW/MED |
|---|---|---|---|
| LR alone | 0.885 | 0.986 | 93 / 909 |
| LR + non-specific ceiling + red-flag floor (what the app returns) | 0.909 | 1.000 | 58 / 909 |
| old v1 LR, scored on the v2 labels | 0.232 | 0.014 | 890 / 909 |

Hand-written checks (`train_eval_v2.py`): 55 code lists with a minimum severity (LR alone 53, with the floor 55; the old model 4); 11 vague symptom sets that must stay at or below MEDIUM (LR alone 9, with the ceiling 11); 14 English sentences 14/14; 19 Swahili phrases 19/19.

**Read these numbers carefully.** The labels are a deterministic function of the codes, so 0.91 only shows the model reproduces my rules, not that the rules are clinically right. The old-model row is not like-for-like (its vocabulary lacks the 47 added codes). The hand-written checks were written by the same person who wrote the rules. Remaining misses are mostly HIGH rated MEDIUM (52 of 909).

## How input is read (`classifier/symptom_codes.py`)
1. English phrases (whole-word, longest first, `ENGLISH_PHRASES`) -> v2 codes.
2. Swahili phrases (`keywords.py` -> team code -> `code_crosswalk.csv`) -> v2 codes. Matched phrases are consumed, so `kukohoa damu` gives `blood_in_sputum` only.
3. Code tokens typed or extracted directly (e.g. `chest_pain`) pass through.
4. LR predicts. Then the non-specific ceiling (1-3 vague codes never above MEDIUM), then the red-flag floor (raise only). When either changes the result, `confidence` is `None` and the reason says which.
5. Input guard: nothing recognised -> NOT ASSESSED; any word not understood **and** final severity LOW -> NOT ASSESSED. A Swahili phrase that is known but has no v2 code (only `ini kuvimba`, `wengu kuvimba`, `ini na wengu kuvimba` now) counts as not understood.

The crosswalk covers 121 of the team's 124 codes (19 same, 55 mapped, 47 with their own v2 code and a red-flag rule; 3 uncovered examination findings).

## Clinician review (`review/`)
`make_review_sheet.py` builds `clinician_review_sheet.xlsx` (120 held-out symptom sets, 30 per tier, shuffled, symptoms only) and `review_answer_key.csv` (rule label and app prediction per ID; **do not send this file to the reviewer**). Give the xlsx to a clinician, then run `python score_review.py <filled file>.xlsx` for agreement, weighted kappa, under-triage and the list of 2+ tier disagreements, against both the app and the dataset's rule labels. That is the first number here that is not circular. The tier definitions on the Instructions sheet are the team's working ones; agree them with the clinician first.

## Known limits
* **Negation is not understood** ("no fever" is read as fever, "no chest pain" as chest pain). The error is towards a higher severity, never lower. Swahili has the same limit.
* **English phrase coverage is a fixed list.** Anything outside it ends up "not understood" (so never LOW). `keywords.py` still matches exact substrings, so other Swahili inflections are missed the same way.
* **Tiers and thresholds are drafts.** The new rules (snakebite, head injury, pregnancy danger signs, burns, severe pallor, bulging fontanelle, ...) are from my knowledge of WHO IMCI / pregnancy / snakebite guidance; the searches run for them returned only result lists, not page text, so they were not re-checked against the documents in the session. Nobody clinical has reviewed any of it.
* **Adult vs paediatric:** the ETAT/IMCI signs are paediatric, the Kaggle diseases adult-oriented, and there is no age input.
* **Kaggle diseases are a closed 41-disease world,** so partial-presentation labels depend on which diseases happen to be in it.
* **PyInstaller:** a build must bundle `dataset_v2/saca_v2_train.csv`, `red_flags.csv`, `code_crosswalk.csv`, `nonspecific_symptoms.csv`. There is no build config in the repo, so none was changed.
