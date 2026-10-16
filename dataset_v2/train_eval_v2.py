#!/usr/bin/env python3
"""Run from inside dataset_v2/ after build_dataset_v2.py. Train the SACA LR (same settings as classifier/logistic_regression.py) on the v2 data and evaluate."""
import sys, re
import numpy as np, pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, recall_score
from sklearn.dummy import DummyClassifier
from symptom_codes import to_v2_codes
from classifier.symptom_codes import only_nonspecific

LAB = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
R = {l: i for i, l in enumerate(LAB)}


def make():
    return Pipeline([("v", CountVectorizer(lowercase=True, strip_accents="unicode", stop_words="english",
                                           max_features=500, min_df=2, max_df=0.8)),
                     ("c", LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced",
                                              solver="lbfgs", random_state=42))])


def load(p):
    d = pd.read_csv(p).dropna(subset=["symptom_text", "severity"])
    d["symptom_text"] = d.symptom_text.astype(str).str.lower().str.strip()
    d["severity"] = d.severity.astype(str).str.upper().str.strip()
    return d


def report(name, y, p, out):
    y = np.array([R[v] for v in y]); p = np.array([R[v] for v in p])
    out.append(f"== {name}  (n={len(y)})")
    out.append(f"accuracy {accuracy_score(y,p):.3f}   macro-F1 {f1_score(y,p,average='macro'):.3f}")
    rec = recall_score(y, p, average=None, labels=range(4), zero_division=0)
    out.append("recall  " + "  ".join(f"{LAB[i]} {rec[i]:.3f}" for i in range(4)))
    out.append(f"under-triage (pred below true): {(p<y).mean():.3%}   over-triage: {(p>y).mean():.3%}")
    sev = y >= 2
    out.append(f"dangerous under-triage (true HIGH/CRITICAL predicted LOW/MEDIUM): {((p<=1)&sev).sum()} of {sev.sum()}")
    crit = y == 3
    out.append(f"CRITICAL predicted below HIGH: {((p<=1)&crit).sum()} of {crit.sum()}")
    cm = confusion_matrix(y, p, labels=range(4))
    out.append("confusion (rows=true, cols=pred; LOW MED HIGH CRIT):\n" + "\n".join("   " + " ".join(f"{v:5d}" for v in r) for r in cm))


# hand-written acceptance cases: (codes, minimum acceptable severity, why)
ACCEPT = [
 ("coma", "CRITICAL", "ETAT coma"), ("convulsions", "CRITICAL", "ETAT convulsing"),
 ("convulsions high_fever", "CRITICAL", "febrile convulsion"), ("cyanosis", "CRITICAL", "ETAT central cyanosis"),
 ("severe_respiratory_distress cough", "CRITICAL", "ETAT"), ("stridor", "CRITICAL", "airway"),
 ("unable_to_drink vomiting", "CRITICAL", "IMCI danger sign"), ("vomits_everything", "CRITICAL", "IMCI danger sign"),
 ("unable_to_breastfeed", "CRITICAL", "IMCI danger sign"), ("uncontrolled_bleeding", "CRITICAL", "ETAT circulation"),
 ("cold_extremities lethargy", "CRITICAL", "shock sign"), ("purpuric_rash high_fever", "CRITICAL", "meningococcaemia"),
 ("altered_sensorium", "CRITICAL", "ETAT"), ("altered_sensorium headache", "CRITICAL", "ETAT"),
 ("chest_pain breathlessness", "CRITICAL", "ACS/PE"), ("chest_pain sweating vomiting", "CRITICAL", "ACS"),
 ("chest_pain fast_heart_rate", "CRITICAL", "cardiac"), ("weakness_of_one_body_side slurred_speech", "CRITICAL", "stroke FAST"),
 ("weakness_of_one_body_side", "CRITICAL", "stroke FAST"), ("stiff_neck high_fever headache", "CRITICAL", "meningitis"),
 ("lethargy sunken_eyes diarrhoea", "CRITICAL", "severe dehydration"),
 ("chest_pain", "HIGH", "single red flag"), ("breathlessness", "HIGH", "single red flag"),
 ("blood_in_sputum", "HIGH", "single red flag"), ("blood_in_sputum cough weight_loss", "HIGH", "TB / PE"),
 ("stomach_bleeding", "HIGH", "GI bleed"), ("slurred_speech", "HIGH", "stroke sign"),
 ("breathlessness cough high_fever", "HIGH", "pneumonia"), ("dehydration diarrhoea vomiting", "HIGH", "IMCI dehydration"),
 ("chills high_fever vomiting headache sweating", "HIGH", "malaria"),
 ("high_fever", "MEDIUM", "fever in malaria area"), ("high_fever headache", "MEDIUM", "fever"),
 ("mild_fever cough", "MEDIUM", "fever"), ("fast_heart_rate", "MEDIUM", "tachycardia"),
 ("bloody_stool diarrhoea", "MEDIUM", "dysentery"), ("lethargy", "MEDIUM", "ETAT priority sign"),
 ("stiff_neck", "MEDIUM", "meningism"),
 ("snake_bite", "HIGH", "snakebite needs facility"), ("snake_envenomation", "CRITICAL", "systemic envenoming"),
 ("snake_bite breathlessness", "CRITICAL", "neurotoxic respiratory failure"),
 ("head_injury vomiting", "CRITICAL", "raised intracranial pressure"), ("head_injury", "HIGH", "head injury"),
 ("pregnancy headache", "HIGH", "pre-eclampsia sign"), ("pregnancy blurred_and_distorted_vision", "HIGH", "pre-eclampsia sign"),
 ("pregnancy abdominal_pain", "HIGH", "pregnancy danger sign"), ("pre_eclampsia", "HIGH", "needs referral"),
 ("puerperal_sepsis", "CRITICAL", "maternal sepsis"), ("bulging_fontanelle", "CRITICAL", "infant meningitis"),
 ("abdominal_rigidity", "CRITICAL", "peritonitis"), ("weak_pulse", "HIGH", "shock sign"),
 ("severe_pallor", "HIGH", "severe anaemia"), ("kwashiorkor_signs", "HIGH", "severe malnutrition"),
 ("burns", "HIGH", "burns"), ("fracture", "HIGH", "fracture"), ("low_blood_pressure", "HIGH", "possible shock"),
]
# upper bounds: vague, non-specific symptoms must not be rated above MEDIUM
ACCEPT_MAX = ["headache", "nausea", "vomiting", "fatigue", "cough", "headache nausea", "fatigue headache nausea",
              "fatigue headache vomiting", "back_pain headache", "malaise muscle_pain", "abdominal_pain nausea vomiting"]
EN = [  # English sentence, minimum acceptable severity
 ("I cannot breathe and have crushing chest pain", "CRITICAL"), ("she coughed up blood this morning", "HIGH"),
 ("my child is unconscious", "CRITICAL"), ("he has had a seizure", "CRITICAL"), ("blue lips and fast breathing", "CRITICAL"),
 ("bitten by a snake yesterday", "HIGH"), ("he fell and hit his head and keeps vomiting", "CRITICAL"),
 ("pregnant woman with headache and blurred vision", "HIGH"), ("child is floppy and has diarrhea and sunken eyes", "CRITICAL"),
 ("stiff neck and high fever", "CRITICAL"), ("pain in my chest", "HIGH"), ("high fever and vomiting", "MEDIUM"),
 ("just a mild headache", "LOW"), ("I have a cough", "LOW"),
]
SW = [  # Swahili phrase, minimum acceptable severity
 ("mtoto hajitambui", "CRITICAL"), ("ana degedege", "CRITICAL"), ("ana homa na degedege", "CRITICAL"),
 ("ameshindwa kunywa na anatapika kila kitu", "CRITICAL"), ("maumivu ya kifua na kupumua kwa shida", "CRITICAL"),
 ("ana kuhara na macho yaliyozama", "HIGH"), ("anakohoa damu", "HIGH"), ("ana homa kali na kutetemeka", "MEDIUM"),
 ("ana homa", "MEDIUM"), ("maumivu ya kifua", "HIGH"), ("shingo ngumu na homa", "CRITICAL"),
 ("kupumua kwa shida", "HIGH"), ("kukohoa damu", "HIGH"), ("kupoteza fahamu", "CRITICAL"), ("amezimia", "CRITICAL"), ("kukosa fahamu", "CRITICAL"), ("kikohozi cha damu", "HIGH"), ("kikohozi", "LOW"), ("maumivu ya kichwa", "LOW"),
]


def main():
    out = []
    tr, te = load("saca_v2_train.csv"), load("saca_v2_test.csv")
    assert not (set(tr.symptom_text) & set(te.symptom_text))
    m = make().fit(tr.symptom_text, tr.severity)
    voc = m.named_steps["v"].vocabulary_
    out.append(f"v2 train rows {len(tr)}, test rows {len(te)}, vocabulary {len(voc)} tokens")
    pred = m.predict(te.symptom_text)
    report("v2 LR on v2 test", te.severity, pred, out)
    rules0 = pd.read_csv("red_flags.csv")
    rl0 = [(set(c.split(";")), R[t]) for c, t in zip(rules0.codes, rules0.min_tier)]
    fl = lambda t: max([x for cs, x in rl0 if cs <= set(t.split())] + [0])
    pf = np.array([LAB[max(R[p], fl(t))] for p, t in zip(pred, te.symptom_text)])
    out.append("")
    report("v2 LR + red-flag floor on v2 test", te.severity, pf, out)
    ceil = lambda p, t: min(R[p], 1) if (R[p] > 1 and only_nonspecific(t.split())) else R[p]
    pa = np.array([LAB[max(ceil(p, t), fl(t))] for p, t in zip(pred, te.symptom_text)])
    out.append("")
    report("v2 LR + non-specific ceiling + red-flag floor (what the app returns) on v2 test", te.severity, pa, out)
    out.append("")
    for s in ("observed", "partial", "redflag"):
        k = te.source == s
        out.append(f"   source={s}: n={k.sum()} acc={accuracy_score(te.severity[k], pred[k]):.3f}")
    dm = DummyClassifier(strategy="most_frequent").fit(tr.symptom_text, tr.severity)
    out.append(f"majority-class baseline accuracy {accuracy_score(te.severity, dm.predict(te.symptom_text)):.3f}")

    # old model (trained on v1 data) scored on v2 test labels and acceptance set
    v1 = load("../saca_train.csv")
    m1 = make().fit(v1.symptom_text, v1.severity)
    out.append("")
    report("OLD v1 model on v2 test (v2 labels)", te.severity, m1.predict(te.symptom_text), out)

    # acceptance set
    sf = {}
    rules = pd.read_csv("red_flags.csv")
    rl = [(set(c.split(";")), R[t]) for c, t in zip(rules.codes, rules.min_tier)]
    def floor(codes):
        s = set(codes.split()); return max([t for cs, t in rl if cs <= s] + [0])
    def run(model, name):
        fails_lr, fails_rule = [], []
        for codes, need, why in ACCEPT:
            p = R[model.predict([codes])[0]]
            if p < R[need]: fails_lr.append((codes, need, LAB[p], why))
            if max(p, floor(codes)) < R[need]: fails_rule.append(codes)
        n = len(ACCEPT)
        out.append(f"{name}: acceptance (codes) LR-only passes {n-len(fails_lr)}/{n}; LR + red-flag floor passes {n-len(fails_rule)}/{n}")
        for f in fails_lr: out.append(f"    LR fail: [{f[0]}] need >= {f[1]}, got {f[2]}  ({f[3]})")
    out.append("")
    run(m, "v2 model"); run(m1, "v1 model")

    # upper bounds
    def fin(codes):
        """What the app returns: LR, non-specific ceiling, then red-flag floor."""
        p = R[m.predict([codes])[0]]
        if p > 1 and only_nonspecific(codes.split()):
            p = 1
        return LAB[max(p, floor(codes))]
    lr_only_over = [c for c in ACCEPT_MAX if R[m.predict([c])[0]] > R["MEDIUM"]]
    over = [c for c in ACCEPT_MAX if R[fin(c)] > R["MEDIUM"]]
    out.append(f"non-specific upper-bound check: LR alone {len(ACCEPT_MAX)-len(lr_only_over)}/{len(ACCEPT_MAX)}; "
               f"with the ceiling {len(ACCEPT_MAX)-len(over)}/{len(ACCEPT_MAX)} stay at or below MEDIUM"
               + (": over " + "; ".join(over) if over else ""))

    # English end-to-end
    out.append("\nEnglish end-to-end (classifier.symptom_codes.read_input -> v2 codes -> LR + red-flag floor):")
    from classifier.symptom_codes import read_input
    from classifier.logistic_regression import SW_FUNCTION_WORDS
    okE = 0
    for ph, need in EN:
        rd = read_input(ph)
        if not rd.codes:
            res, good = "NOT ASSESSED (no code)", False
        else:
            p = fin(" ".join(rd.codes))
            left = [t for t in m.named_steps["v"].build_analyzer()(rd.residual) if t not in SW_FUNCTION_WORDS]
            res = p + (f"  [words not understood: {','.join(left)}]" if left else "")
            good = R[p] >= R[need] and not (p == "LOW" and left)
        okE += good
        out.append(f"   {'PASS' if good else 'FAIL'}  '{ph}' -> {rd.codes} -> {res}   (need >= {need})")
    out.append(f"   English passes {okE}/{len(EN)}")

    # Swahili end-to-end
    out.append("\nSwahili end-to-end (classifier.symptom_codes.read_input -> v2 codes -> LR + red-flag floor):")
    ok = 0
    for ph, need in SW:
        codes, unmapped = to_v2_codes(ph)
        if not codes:
            res = "NOT ASSESSED (no v2 code)"; good = False
        else:
            p = fin(" ".join(codes))
            res = p + (f"  [unmapped: {','.join(unmapped)}]" if unmapped else "")
            good = R[p] >= R[need]
        ok += good
        out.append(f"   {'PASS' if good else 'FAIL'}  '{ph}' -> {codes} -> {res}   (need >= {need})")
    out.append(f"   Swahili passes {ok}/{len(SW)}  (LR + ceiling + red-flag floor)")
    # coverage of team vocabulary
    xw = pd.read_csv("code_crosswalk.csv", keep_default_na=False)
    out.append("\ncrosswalk status of the team's 124 codes:\n" + xw.status.value_counts().to_string())
    out.append("uncovered team codes: " + ", ".join(xw[xw.status == 'uncovered'].team_code))
    open("eval_report_v2.txt", "w").write("\n".join(out) + "\n")
    print("\n".join(out))

main()
