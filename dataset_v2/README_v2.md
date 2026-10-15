# SACA dataset v2 (draft for clinician review)

Nothing in this folder replaces `saca_train.csv` / `saca_test.csv`. The app still trains on the old files until you point it at `dataset_v2/saca_v2_train.csv`.

## What was wrong with v1
Labels were the sum of per-symptom weights (`Symptom-severity.csv`), bucketed at 13/25/40, so "severity" was close to "number of symptoms". `coma` alone summed to LOW. 76% of the 16,812 training rows were three Swahili sentence templates wrapped around the same ~240 English combinations, so the file had 1,716 distinct texts, and the test file shared texts with it.

## How v2 labels a symptom set S
`label(S) = max( red-flag floor(S), disease tier(S) )`

* **red-flag floor** - highest `min_tier` of any rule in `red_flags.csv` whose codes are all present (40 rules; basis column cites WHO ETAT, IMCI danger signs, WHO-ICRC Basic Emergency Care, or "team override list" = `CRITICAL_OVERRIDE_KEYWORDS` in `keywords.py`).
* **disease tier** (`disease_urgency.csv`, 41 diseases, every tier marked DRAFT):
  * S is one of the 304 distinct combinations in the Kaggle data: highest tier of the diseases that produced it (no combination is shared across tiers, 0 conflicts).
  * S is a partial presentation (1-3 symptoms taken from one disease's symptom pool): the **lowest** tier among the diseases that can produce it. A vague set is only as urgent as the least urgent thing it could be; danger comes from the red-flag rules. `python build_dataset_v2.py median|max` switches policy; only 412 of 6,320 labels differ between min and max, but vague single symptoms (cough, vomiting, headache) flip between LOW and HIGH, so this choice matters.

Rows are distinct symptom sets in sorted code order (6,320 sets: 304 observed, 4,613 partial, 1,403 synthetic red-flag). Codes only, no Swahili sentences. 11 red-flag codes absent from the Kaggle data (`convulsions`, `cyanosis`, ...) exist only in the synthetic rows. The 80/20 split is on distinct sets, stratified by label, and asserts no text is in both files (5,057 train / 1,263 test). The class mix is partly an artefact of the synthetic red-flag rows (CRITICAL = 18%), not a disease prevalence.

## Reproduce
```
cd dataset_v2
python build_dataset_v2.py      # writes saca_v2_*.csv + build_report_v2.txt
python train_eval_v2.py         # writes eval_report_v2.txt
```
Outputs were re-run from a clean copy and are byte-identical.

## Results (same LR settings as `classifier/logistic_regression.py`)
| | accuracy | CRITICAL recall | true HIGH/CRIT predicted LOW/MED |
|---|---|---|---|
| v2 LR on v2 test | 0.899 | 0.959 | 53 / 642 |
| v2 LR + red-flag floor | 0.913 | 1.000 | 41 / 642 |
| old v1 LR on v2 test labels | 0.263 | 0.014 | 623 / 642 |

Hand-written acceptance set (37 code lists): v2 LR alone 36/37 (misses `stiff_neck high_fever headache`), with the floor 37/37; old model 4/37.

**Read these numbers carefully.** The labels are a deterministic function of the codes, so 0.90 only shows that LR can reproduce my rules; it says nothing about clinical validity. The old-model row is not like-for-like (the old vocabulary lacks the 11 added codes, and it was trained to a different definition). The acceptance set and the red-flag floor are the safety evidence, and the acceptance set is written by the same person who wrote the rules.

## Swahili and wiring (done 2026-10-16)
The classifier now uses v2 end to end:

* `classifier/logistic_regression.py` trains on `dataset_v2/saca_v2_train.csv` by default (`DEFAULT_TRAIN_PATH`). `main.py`, `ammu_api.py` and the Flask app all construct this class, so all three get it.
* `classifier/symptom_codes.py` reads Swahili: `keywords.py` phrases -> team codes -> `code_crosswalk.csv` -> v2 codes. A matched phrase is consumed, so `kukohoa damu` gives `blood_in_sputum` only. Code tokens typed or extracted directly (e.g. `chest_pain`) pass straight through.
* After the model, `red_flags.csv` is applied as a floor: it can raise the severity, never lower it. When it does, `confidence` is `None` and the reason names the rule ids; the result also carries `red_flag_rules`.
* Input guard unchanged in spirit: nothing recognised -> not assessed; any word not understood **and** final severity LOW -> not assessed. A Swahili phrase that is known but has no v2 code (snake bite, burns, pregnancy, trauma: 43 of the team's 124 codes) counts as "not understood".
* `keywords.py` gaps fixed: `amezimia`, `kukosa fahamu`, `hajitambui`, `hana fahamu` (unconscious); `kohoa damu`, `kikohozi cha damu`, `makohozi yenye damu` (haemoptysis); `ameshindwa kunywa`, `ameshindwa kunyonya`. It still matches exact substrings, so other inflections will be missed; those inputs end up "not understood", not LOW, unless another recognised symptom is LOW and nothing else is unread.

End to end, the 19 Swahili phrases in `train_eval_v2.py` all pass. `tests/test_v2_normalisation.py` (43 tests) pins this; the whole suite is 90 passing.

Known limits: free English sentences are not read (the LLM extractor in `classifier/llm_extractor.py` is still a placeholder that raises `NotImplementedError`, so the pipeline always falls back to raw text). A vague multi-symptom set can be rated HIGH because, among the 41 diseases in this data, only high-tier ones contain it (`fatigue headache nausea` -> Dengue, Typhoid, Hypoglycemia). A PyInstaller build must bundle `dataset_v2/saca_v2_train.csv`, `red_flags.csv` and `code_crosswalk.csv`.

## Needs a clinician before anyone relies on it
`disease_urgency.csv` tiers, `red_flags.csv` thresholds (e.g. any fever = MEDIUM, chest pain = HIGH), the min-policy for partial sets, and the paediatric/adult mix: the ETAT/IMCI signs are paediatric, and the Kaggle diseases are adult-oriented.
