#!/usr/bin/env python3
"""Build the blind clinician review sheet (the first non-circular check of the model).

Run from dataset_v2/review/ :  python make_review_sheet.py
Writes:
  clinician_review_sheet.xlsx   give THIS to the clinician. Symptoms only, no model labels.
  review_answer_key.csv         keep THIS back. Rule label and app prediction per ID.

120 symptom sets are drawn from the held-out test file (saca_v2_test.csv), 30 per rule-label tier,
shuffled, so the clinician cannot infer a label from the order. The mix favours observed (real
Kaggle combinations) and partial presentations over synthetic red-flag rows.
"""
import os
import random
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from classifier.logistic_regression import LogisticRegressionClassifier  # noqa: E402

SEED = 7
PER_TIER = 30
QUOTA = {"observed": 8, "partial": 14, "redflag": 8}   # per tier, filled in this priority order
TIERS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def plain(codes):
    """symptom codes -> readable phrase list"""
    out = []
    for c in codes.split():
        c = c.replace("_(typhos)", "").replace("_", " ").replace("ofurine", "of urine").strip()
        out.append(c)
    return ", ".join(out)


def main():
    rng = random.Random(SEED)
    te = pd.read_csv(os.path.join(HERE, "..", "saca_v2_test.csv"))
    te = te[te.n_symptoms <= 8]
    picks = []
    for tier in TIERS:
        g = te[te.severity == tier]
        chosen = []
        for src, q in QUOTA.items():
            pool = g[g.source == src].index.tolist()
            rng.shuffle(pool)
            chosen += pool[:q]
        rest = [i for i in g.index if i not in chosen]
        rng.shuffle(rest)
        chosen += rest[: PER_TIER - len(chosen)]
        picks += chosen[:PER_TIER]
    rng.shuffle(picks)
    sample = te.loc[picks].reset_index(drop=True)
    sample["id"] = [f"R{i + 1:03d}" for i in range(len(sample))]

    clf = LogisticRegressionClassifier()
    clf.train()
    sample["app_prediction"] = [clf.classify(t)["severity"] for t in sample.symptom_text]
    sample[["id", "symptom_text", "severity", "source", "app_prediction"]].rename(
        columns={"severity": "rule_label"}).to_csv(os.path.join(HERE, "review_answer_key.csv"), index=False)

    wb = Workbook()
    ws = wb.active
    ws.title = "Instructions"
    arial = Font(name="Arial", size=10)
    bold = Font(name="Arial", size=10, bold=True)
    head = Font(name="Arial", size=14, bold=True)
    fill_in = PatternFill("solid", fgColor="FFF2CC")
    rows = [
        ("SACA triage review - instructions", head),
        ("", arial),
        ("What this is: SACA is an offline triage aid for rural Tanzania. Each row on the 'Review' sheet lists "
         "symptoms a patient has reported and nothing else. For each row, give the urgency you would assign "
         "to a patient presenting at a rural clinic with only these symptoms.", arial),
        ("", arial),
        ("Fill in only the yellow cells in column C (Your rating) and, optionally, column D (Comment).", bold),
        ("", arial),
        ("Rating scale (team's working definitions - change them if your protocol differs and tell us):", bold),
        ("LOW       - no urgency; routine care or self-care advice", arial),
        ("MEDIUM    - should see a health worker within the next few days", arial),
        ("HIGH      - should be seen the same day", arial),
        ("CRITICAL  - emergency; needs immediate attention / referral now", arial),
        ("", arial),
        ("Please rate the symptoms as listed. If a row is too vague to rate, pick the lowest tier you would be "
         "comfortable with and say so in the Comment column.", arial),
        ("A row may mix adult and child symptoms; rate for the most plausible patient and note the age group "
         "you assumed in Comment if it matters.", arial),
        ("", arial),
        ("Example (not part of the data):", bold),
        ("   Symptoms: 'cough, weight loss, night sweats'   ->   Your rating: HIGH   Comment: possible TB, same-day assessment", arial),
    ]
    for r, (text, f) in enumerate(rows, start=1):
        c = ws.cell(row=r, column=1, value=text)
        c.font = f
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 110

    rv = wb.create_sheet("Review")
    rv["A1"] = "SACA triage review"
    rv["A1"].font = head
    rv["A2"] = "Rated:"
    rv["A2"].font = bold
    rv["B2"] = f'=COUNTA(C5:C{4 + len(sample)})&" of {len(sample)}"'
    rv["B2"].font = arial
    hdr = ["ID", "Symptoms reported", "Your rating", "Comment (optional)"]
    for i, h in enumerate(hdr, start=1):
        c = rv.cell(row=4, column=i, value=h)
        c.font = bold
        c.fill = PatternFill("solid", fgColor="D9E1F2")
    for r, row in enumerate(sample.itertuples(), start=5):
        rv.cell(row=r, column=1, value=row.id).font = arial
        c = rv.cell(row=r, column=2, value=plain(row.symptom_text))
        c.font = arial
        c.alignment = Alignment(wrap_text=True, vertical="top")
        rv.cell(row=r, column=3).fill = fill_in
        rv.cell(row=r, column=3).font = arial
        rv.cell(row=r, column=4).fill = fill_in
        rv.cell(row=r, column=4).font = arial
        rv.cell(row=r, column=4).alignment = Alignment(wrap_text=True, vertical="top")
    dv = DataValidation(type="list", formula1='"LOW,MEDIUM,HIGH,CRITICAL"', allow_blank=True,
                        showErrorMessage=True, errorTitle="Rating", error="Pick LOW, MEDIUM, HIGH or CRITICAL")
    rv.add_data_validation(dv)
    dv.add(f"C5:C{4 + len(sample)}")
    rv.column_dimensions["A"].width = 8
    rv.column_dimensions["B"].width = 70
    rv.column_dimensions["C"].width = 16
    rv.column_dimensions["D"].width = 50
    rv.freeze_panes = "A5"
    wb.save(os.path.join(HERE, "clinician_review_sheet.xlsx"))
    print(f"wrote {len(sample)} rows; tiers {sample.severity.value_counts().to_dict()}; "
          f"sources {sample.source.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
