"""Compatibility shim for train_eval_v2.py. The real implementation lives in
classifier/symptom_codes.py (the app uses it); this just keeps the old call."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from classifier.symptom_codes import read_swahili  # noqa: E402


def to_v2_codes(text):
    """Return (v2_codes, unmapped_phrases)."""
    r = read_swahili(text)
    return r.codes, r.unmapped
