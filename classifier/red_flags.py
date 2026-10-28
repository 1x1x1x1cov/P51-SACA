"""
Red-flag safety layer for SACA.

WHY THIS EXISTS
The Logistic Regression model was trained on saca_train.csv, where the severity
label is just a bucketed SUM of symptom weights (LOW <=12, MEDIUM 13-24,
HIGH 25-39, CRITICAL 40+) over rows averaging ~21 symptoms. A real patient
describes 2-5 symptoms, so their total weight is small and the model almost
never returns HIGH/CRITICAL -- e.g. "coma" alone comes back LOW, and "chest pain
+ breathlessness + vomiting + headache" comes back MEDIUM at 98% confidence.

This layer sets a minimum severity ("floor") when known danger signs are
present. It can only RAISE severity, never lower it: final = max(model, floors).

!! The rules below are a PROPOSED starting set, not clinical guidance. They
!! must be reviewed/edited by someone with clinical input before real use.
"""

import re

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Extra tokens the LLM extractor may output that are NOT in Symptom-severity.csv.
# The Logistic Regression ignores unknown words, but these let the red-flag layer
# see danger signs the classifier vocabulary has no word for.
EXTRA_TOKENS = (
    "vomiting_blood",
    "loss_of_consciousness",
    "seizure",
    "severe_bleeding",
)

# (required tokens -- ALL must be present, minimum severity, human-readable reason)
RULES = [
    ({"vomiting_blood"},               "CRITICAL", "vomiting blood"),
    ({"loss_of_consciousness"},        "CRITICAL", "loss of consciousness"),
    ({"coma"},                         "CRITICAL", "coma"),
    ({"seizure"},                      "CRITICAL", "seizure"),
    ({"severe_bleeding"},              "CRITICAL", "severe bleeding"),
    ({"chest_pain", "breathlessness"}, "CRITICAL", "chest pain with breathlessness"),
    ({"chest_pain"},                   "HIGH",     "chest pain"),
    ({"breathlessness"},               "HIGH",     "difficulty breathing"),
    ({"slurred_speech"},               "HIGH",     "slurred speech"),
    ({"weakness_in_limbs"},            "HIGH",     "weakness in limbs"),
    ({"stiff_neck", "high_fever"},     "HIGH",     "stiff neck with high fever"),
    ({"blood_in_sputum"},              "HIGH",     "coughing blood"),
    ({"bloody_stool"},                 "HIGH",     "blood in stool"),
    ({"stomach_bleeding"},             "HIGH",     "stomach bleeding"),
]


def _present(token: str, tokens: set, text: str) -> bool:
    """A token counts if it was extracted, or (offline fallback) its words appear in the raw text."""
    if token in tokens:
        return True
    return re.search(r"\b" + re.escape(token.replace("_", " ")) + r"\b", text) is not None


def check_red_flags(symptom_text: str, extra_text: str = "") -> tuple:
    """
    Returns (floor_severity or None, [reasons]).
    symptom_text: extracted tokens (or raw text on fallback).
    extra_text:   optional raw patient text, scanned for plain phrases like "chest pain".
    """
    text = f"{symptom_text} {extra_text}".lower()
    tokens = set(text.split())
    floor, reasons = None, []
    for required, severity, reason in RULES:
        if all(_present(t, tokens, text) for t in required):
            reasons.append(reason)
            if floor is None or SEVERITY_ORDER.index(severity) > SEVERITY_ORDER.index(floor):
                floor = severity
    return floor, reasons


def apply_floor(model_severity: str, floor):
    """Return the higher of the model's severity and the red-flag floor."""
    if floor and SEVERITY_ORDER.index(floor) > SEVERITY_ORDER.index(model_severity):
        return floor
    return model_severity