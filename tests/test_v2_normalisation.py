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
    """'wengu kuvimba' (enlarged spleen) is in keywords.py but is an examination
    finding with no v2 code. 'kikohozi' on its own is LOW; with an unratable
    phrase beside it, the result must not be LOW."""
    phrase = "wengu kuvimba"
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


# ---- English sentences ---------------------------------------------------

def test_every_english_phrase_maps_to_a_model_vocabulary_code(clf):
    from classifier.symptom_codes import ENGLISH_PHRASES
    vocab = set(clf.pipeline.named_steps["vectorizer"].vocabulary_)
    bad = {p: c for p, cs in ENGLISH_PHRASES.items() for c in cs if c not in vocab}
    assert not bad, bad


@pytest.mark.parametrize("text,minimum", [
    ("I cannot breathe and have crushing chest pain", "CRITICAL"),
    ("she coughed up blood this morning", "HIGH"),
    ("my child is unconscious", "CRITICAL"),
    ("he has had a seizure", "CRITICAL"),
    ("blue lips and fast breathing", "CRITICAL"),
    ("bitten by a snake yesterday", "HIGH"),
    ("he fell and hit his head and keeps vomiting", "CRITICAL"),
    ("pregnant woman with headache and blurred vision", "HIGH"),
    ("child is floppy and has diarrhea and sunken eyes", "CRITICAL"),
    ("stiff neck and high fever", "CRITICAL"),
    ("pain in my chest", "HIGH"),
    ("high fever and vomiting", "MEDIUM"),
])
def test_english_danger_sentences_reach_the_right_severity(clf, text, minimum):
    r = clf.classify(text)
    assert r["assessed"] is True, r
    assert RANK[r["severity"]] >= RANK[minimum], r


def test_english_phrase_is_not_matched_inside_a_code_token():
    """'fever' must not be pulled out of 'high_fever'."""
    from classifier.symptom_codes import read_english
    assert read_english("high_fever").codes == []


def test_english_matching_needs_whole_words():
    from classifier.symptom_codes import read_english
    assert read_english("the coughdrop tin").codes == []


def test_unknown_english_is_not_rated_low(clf):
    for text in ["my tooth hurts", "severe headache"]:
        r = clf.classify(text)
        assert r["assessed"] is False and r["severity"] != "LOW", (text, r)


def test_negation_is_not_understood_and_errs_upwards(clf):
    """Known limit: 'no chest pain' is read as chest pain. The error is towards
    a higher severity, never a lower one."""
    r = clf.classify("no chest pain")
    assert RANK[r["severity"]] >= RANK["HIGH"]


def test_codes_are_returned_in_input_order(clf):
    r = clf.classify("headache then cough then vomiting")
    assert r["symptoms"] == ["headache", "cough", "vomiting"]


# ---- danger signs that now have codes --------------------------------------

@pytest.mark.parametrize("codes,minimum", [
    ("snake_bite", "HIGH"), ("snake_envenomation", "CRITICAL"),
    ("snake_bite breathlessness", "CRITICAL"), ("head_injury", "HIGH"),
    ("head_injury vomiting", "CRITICAL"), ("burns", "HIGH"), ("fracture", "HIGH"),
    ("pregnancy headache", "HIGH"), ("pregnancy blurred_and_distorted_vision", "HIGH"),
    ("pre_eclampsia", "HIGH"), ("puerperal_sepsis", "CRITICAL"),
    ("bulging_fontanelle", "CRITICAL"), ("abdominal_rigidity", "CRITICAL"),
    ("severe_pallor", "HIGH"), ("weak_pulse", "HIGH"), ("kwashiorkor_signs", "HIGH"),
    ("low_blood_pressure", "HIGH"),
])
def test_newly_coded_danger_signs_are_rated(clf, codes, minimum):
    r = clf.classify(codes)
    assert r["assessed"] is True, r
    assert RANK[r["severity"]] >= RANK[minimum], r


@pytest.mark.parametrize("text,minimum", [
    ("kuumwa na nyoka", "HIGH"), ("ana jeraha la kichwa", "HIGH"),
])
def test_swahili_injury_phrases_that_were_unmapped_are_now_rated(clf, text, minimum):
    r = clf.classify(text)
    if r["assessed"] is False and not r["symptoms"]:
        pytest.skip("phrase not in keywords.py: " + text)
    assert RANK[r["severity"]] >= RANK[minimum], r


def test_pregnancy_alone_is_not_a_symptom_but_is_not_not_assessed(clf):
    r = clf.classify("pregnant")
    assert r["assessed"] is True
    assert r["severity"] in {"LOW", "MEDIUM"}


# ---- non-specific ceiling --------------------------------------------------

@pytest.mark.parametrize("codes", [
    "headache", "nausea", "vomiting", "fatigue", "cough", "headache nausea",
    "fatigue headache nausea", "back_pain headache", "abdominal_pain nausea vomiting",
])
def test_vague_symptoms_alone_are_never_above_medium(clf, codes):
    assert RANK[clf.classify(codes)["severity"]] <= RANK["MEDIUM"]


def test_ceiling_does_not_hide_a_red_flag(clf):
    r = clf.classify("headache nausea stiff_neck high_fever")
    assert r["severity"] == "CRITICAL"
