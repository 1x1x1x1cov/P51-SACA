"""
Input guard tests for LogisticRegressionClassifier.classify().

Background: the model only knows symptom codes (the v2 vocabulary). Words
outside it add nothing to the feature vector, and an all-zero vector was
predicted LOW at ~95% -- so "I cannot breathe and have crushing chest pain"
came back as LOW. Swahili phrases are now converted to codes first
(classifier/symptom_codes.py), see tests/test_v2_normalisation.py.

The guard: no recognised symptom -> not assessed; some words not understood
AND the final severity is LOW -> not assessed. A not-assessed result is
reported as HIGH (the safe direction) with assessed=False.
"""

import pytest
from classifier.logistic_regression import LogisticRegressionClassifier


@pytest.fixture(scope="module")
def clf():
    c = LogisticRegressionClassifier()
    c.train()
    return c


@pytest.mark.parametrize("text", [
    "my tooth hurts and my hair is falling out",       # free English text, no known symptom
    "nina maumivu ya meno",                            # Swahili, symptom not in the vocabulary
    "asdfgh qwerty",                                   # gibberish
    "na ya kwa",                                       # Swahili function words only
    "the patient is unwell",
])
def test_input_with_no_known_symptom_is_not_assessed(clf, text):
    r = clf.classify(text)
    assert r["assessed"] is False
    assert r["severity"] != "LOW"
    assert r["confidence"] is None
    assert r["symptoms"] == []


def test_partly_understood_input_cannot_be_low(clf):
    """'kikohozi' (cough) is known and rated LOW on its own; 'xyzabc' is not
    understood. The guard must refuse to make a LOW claim while ignoring it."""
    r = clf.classify("kikohozi xyzabc")
    assert r["assessed"] is False
    assert r["severity"] != "LOW"
    assert "xyzabc" in r["unrecognised"]
    assert "cough" in r["symptoms"]


def test_unread_words_are_listed_in_reason(clf):
    r = clf.classify("kikohozi xyzabc")
    assert "xyzabc" in r["reason"]


def test_fully_recognised_input_is_assessed_normally(clf):
    r = clf.classify("high_fever vomiting abdominal_pain")
    assert r["assessed"] is True
    assert r["unrecognised"] == []
    assert r["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert 0.0 <= r["confidence"] <= 1.0


def test_fully_recognised_low_input_is_still_allowed_to_be_low(clf):
    """The guard must not turn every LOW into 'not assessed': only LOW given
    while ignoring part of the input is blocked."""
    r = clf.classify("cough")  # known word, rated LOW
    assert r["severity"] == "LOW"
    assert r["assessed"] is True


def test_partly_understood_but_not_low_keeps_model_severity_and_warns(clf):
    r = clf.classify("high_fever vomiting abdominal_pain unknownword")
    assert r["assessed"] is True
    assert r["severity"] != "LOW"
    assert r["unrecognised"] == ["unknownword"]


def test_swahili_function_words_alone_do_not_count_as_recognised(clf):
    r = clf.classify("dalili nina na")
    assert r["assessed"] is False


def test_empty_input_is_flagged_not_assessed(clf):
    r = clf.classify("")
    assert r["assessed"] is False
