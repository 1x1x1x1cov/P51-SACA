"""
Swahili text -> v2 symptom codes, and the red-flag floor.

The v2 training data (dataset_v2/saca_v2_train.csv) is made of symptom *codes*
("high_fever", "chest_pain", ...), not sentences. keywords.py turns Swahili
phrases into the team's own codes (124 of them); dataset_v2/code_crosswalk.csv
maps those to the v2 vocabulary. dataset_v2/red_flags.csv holds the red-flag
rules (WHO ETAT / IMCI danger signs, DRAFT -- clinician review needed).

read_swahili() consumes each matched phrase so the words it explained are not
later reported as "not understood". A phrase whose team code has no v2
equivalent (e.g. "nyoka" = snake) is returned in `unmapped`: the system knows
the word but cannot rate it, so the caller must treat it as not understood.
"""

import csv
import os
import sys
from collections import namedtuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

from keywords import SYMPTOM_MAP  # noqa: E402

DATASET_V2_DIR = os.path.join(_ROOT, "dataset_v2")
CROSSWALK_PATH = os.path.join(DATASET_V2_DIR, "code_crosswalk.csv")
RED_FLAGS_PATH = os.path.join(DATASET_V2_DIR, "red_flags.csv")

RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

Reading = namedtuple("Reading", "codes unmapped residual")

_crosswalk = None
_rules = None


def _load_crosswalk():
    global _crosswalk
    if _crosswalk is None:
        with open(CROSSWALK_PATH, newline="", encoding="utf-8") as f:
            _crosswalk = {
                r["team_code"]: [c for c in r["v2_codes"].split("+") if c]
                for r in csv.DictReader(f)
            }
    return _crosswalk


def _load_rules():
    global _rules
    if _rules is None:
        with open(RED_FLAGS_PATH, newline="", encoding="utf-8") as f:
            _rules = [
                (r["rule_id"], frozenset(r["codes"].split(";")), r["min_tier"])
                for r in csv.DictReader(f)
            ]
    return _rules


def crosswalk_targets():
    """Every v2 code the crosswalk can emit."""
    return {c for cs in _load_crosswalk().values() for c in cs}


def red_flag_codes():
    """Every code that appears in a red-flag rule."""
    return {c for _, cs, _ in _load_rules() for c in cs}


def read_swahili(text):
    """Match Swahili phrases in `text`.

    Returns Reading(codes, unmapped, residual):
      codes     v2 codes found (order of discovery, no duplicates)
      unmapped  matched phrases whose team code has no v2 equivalent
      residual  `text` with every matched phrase blanked out
    Longer phrases are matched first and consume their text, so
    "kukohoa damu" yields haemoptysis only, not cough + blood.
    """
    xw = _load_crosswalk()
    residual = text.lower()
    codes, unmapped = [], []
    for phrase in sorted(SYMPTOM_MAP, key=len, reverse=True):
        if phrase in residual:
            residual = residual.replace(phrase, " ")
            mapped = xw.get(SYMPTOM_MAP[phrase], [])
            if not mapped:
                unmapped.append(phrase)
            for c in mapped:
                if c not in codes:
                    codes.append(c)
    return Reading(codes, unmapped, residual)


def red_flag_floor(codes):
    """Highest-tier red-flag rule satisfied by `codes`.

    Returns (severity or None, [rule_ids of every matching rule]).
    """
    have = set(codes)
    hit = [(RANK[t], rid) for rid, cs, t in _load_rules() if cs <= have]
    if not hit:
        return None, []
    top = max(r for r, _ in hit)
    severity = next(k for k, v in RANK.items() if v == top)
    return severity, [rid for _, rid in sorted(hit, reverse=True)]
