"""
v2 wiring tests: Swahili -> codes, the red-flag floor, and dataset/vocabulary
consistency. See dataset_v2/README_v2.md.
"""

import pandas as pd
import pytest

from classifier.logistic_regression import LogisticRegressionClassifier, DEFAULT_TRAIN_PATH
from classifier.symptom_codes import crosswalk_targets, red_flag_codes, read_swahili

RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@pytest.fixture(scope="module")
def clf():
    c = LogisticRegressionClassifier()
    c.train()
    return c


# ---- data / vocabulary consistency ---------------------------------------

def test_train_and_test_files_share_no_text():
    tr = pd.read_csv(DEFAULT_TRAIN_PATH)
    te = pd.read_csv(DEFAULT_TRAIN_PATH.replace("train", "test"))
    assert not set(tr.symptom_text) & set(te.symptom_text)


def test_every_crosswalk_and_red_flag_code_is_in_the_model_vocabulary(clf):
    vocab = set(clf.pipeline.named_steps["vectorizer"].vocabulary_)
    assert crosswalk_targets() <= vocab
    assert red_flag_codes() <= vocab


# ---- Swahili input is read, not ignored ----------------------------------

@pytest.mark.parametrize("text,minimum", [
    ("ana degedege", "CRITICAL"),
    ("ana homa na degedege", "CRITICAL"),
    ("amezimia", "CRITICAL"),
    ("kukosa fahamu", "CRITICAL"),
    ("mtoto hajitambui", "CRITICAL"),
    ("kupoteza fahamu", "CRITICAL"),
    ("ameshindwa kunywa na anatapika kila kitu", "CRITICAL"),
    ("maumivu ya kifua na kupumua kwa shida", "CRITICAL"),
    ("shingo ngumu na homa", "CRITICAL"),
    ("kukohoa damu", "HIGH"),
    ("anakohoa damu", "HIGH"),
    ("kikohozi cha damu", "HIGH"),
    ("maumivu ya kifua", "HIGH"),
    ("kupumua kwa shida", "HIGH"),
    ("ana kuhara na macho yaliyozama", "HIGH"),
    ("ana homa", "MEDIUM"),
])
def test_swahili_danger_phrases_reach_the_right_severity(clf, text, minimum):
    r = clf.classify(text)
    assert r["assessed"] is True, r
    assert RANK[r["severity"]] >= RANK[minimum], r
    assert r["unrecognised"] == [], r


def test_matched_phrase_is_consumed_so_blood_cough_is_not_also_plain_cough():
    reading = read_swahili("kukohoa damu")
    assert reading.codes == ["blood_in_sputum"]


def test_swahili_cough_alone_is_low_and_assessed(clf):
    r = clf.classify("kikohozi")
    assert r["severity"] == "LOW"
    assert r["assessed"] is True


def test_known_swahili_phrase_with_no_v2_code_is_not_rated_low(clf):
    """Snake bite is in keywords.py but has no v2 code. 'kikohozi' on its own
    is LOW; with an unratable phrase beside it, the result must not be LOW."""
    phrase = "kuumwa na nyoka"
    assert read_swahili(phrase).unmapped, "test needs a mapped-but-unratable phrase"
    r = clf.classify("kikohozi " + phrase)
    assert r["assessed"] is False
    assert r["severity"] != "LOW"
    assert phrase in r["unrecognised"]


# ---- red-flag floor ------------------------------------------------------

def test_floor_raises_model_prediction_and_drops_model_confidence(clf):
    """The model alone rates this MEDIUM; rule RF30 (meningitis) makes it CRITICAL."""
    r = clf.classify("stiff_neck high_fever headache")
    assert r["severity"] == "CRITICAL"
    assert "RF30" in r["red_flag_rules"]
    assert r["confidence"] is None
    assert "RF30" in r["reason"]


@pytest.mark.parametrize("codes,minimum", [
    ("coma", "CRITICAL"), ("convulsions", "CRITICAL"), ("cyanosis", "CRITICAL"),
    ("stridor", "CRITICAL"), ("uncontrolled_bleeding", "CRITICAL"),
    ("unable_to_drink vomiting", "CRITICAL"), ("altered_sensorium headache", "CRITICAL"),
    ("weakness_of_one_body_side", "CRITICAL"), ("slurred_speech weakness_in_limbs", "CRITICAL"),
    ("chest_pain sweating vomiting", "CRITICAL"), ("lethargy sunken_eyes diarrhoea", "CRITICAL"),
    ("chest_pain", "HIGH"), ("breathlessness", "HIGH"), ("blood_in_sputum", "HIGH"),
    ("stomach_bleeding", "HIGH"), ("slurred_speech", "HIGH"),
    ("dehydration diarrhoea vomiting", "HIGH"),
    ("high_fever", "MEDIUM"), ("fast_heart_rate", "MEDIUM"), ("lethargy", "MEDIUM"),
])
def test_red_flag_codes_never_come_back_below_their_rule(clf, codes, minimum):
    r = clf.classify(codes)
    assert RANK[r["severity"]] >= RANK[minimum], r


def test_floor_never_lowers_a_model_prediction(clf):
    r = clf.classify("chest_pain breathlessness sweating vomiting")
    assert r["severity"] == "CRITICAL"
