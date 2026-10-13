"""
Input guard tests for LogisticRegressionClassifier.classify().

Background: the model only knows the words in its training vocabulary
(symptom codes like "high_fever" plus Swahili symptom phrases). Words
outside it add nothing to the feature vector, and an all-zero vector was
predicted LOW at ~95% -- so "I cannot breathe and have crushing chest pain"
and "ana homa na degedege" (fever and convulsions) came back as LOW.

The guard: no recognised symptom -> not assessed; some words not understood
AND the model says LOW -> not assessed. A not-assessed result is reported as
HIGH (the safe direction) with assessed=False.
"""

import pytest
from classifier.logistic_regression import LogisticRegressionClassifier


@pytest.fixture(scope="module")
def clf():
    c = LogisticRegressionClassifier()
    c.train()
    return c


@pytest.mark.parametrize("text", [
    "I cannot breathe and have crushing chest pain",   # free English text
    "mtoto ana degedege",                              # Swahili: child has convulsions
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
    """'homa' (fever) is known, 'degedege' (convulsions) is not. The raw model
    rates this LOW at ~97%; the guard must refuse to make that claim."""
    r = clf.classify("ana homa na degedege")
    assert r["assessed"] is False
    assert r["severity"] != "LOW"
    assert "degedege" in r["unrecognised"]
    assert "homa" in r["symptoms"]


def test_unread_words_are_listed_in_reason(clf):
    r = clf.classify("ana homa na degedege")
    assert "degedege" in r["reason"]


def test_fully_recognised_input_is_assessed_normally(clf):
    r = clf.classify("high_fever vomiting abdominal_pain")
    assert r["assessed"] is True
    assert r["unrecognised"] == []
    assert r["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    assert 0.0 <= r["confidence"] <= 1.0


def test_fully_recognised_low_input_is_still_allowed_to_be_low(clf):
    """The guard must not turn every LOW into 'not assessed': only LOW given
    while ignoring part of the input is blocked."""
    r = clf.classify("slurred_speech loss_of_balance")  # known words, model says LOW
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
