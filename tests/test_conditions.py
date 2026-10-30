"""Tests for conditions.py (possible conditions with match scores)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import conditions as c  # noqa: E402


def test_loads_41_diseases_with_names_and_tiers():
    m = c._model()
    assert len(m["diseases"]) == 41
    for d in m["diseases"]:
        assert d in c.DISPLAY, d
        assert m["urgency"].get(d) in ("LOW", "MEDIUM", "HIGH", "CRITICAL"), d


def test_display_names_fix_source_typos():
    names = " ".join(en for en, _ in c.DISPLAY.values())
    for typo in ("Paroymsal", "hemmorhoids", "diseae", "Osteoarthristis"):
        assert typo not in names


def test_scores_sum_to_one_and_sorted():
    ranked = c.scores({"cough", "runny_nose"})
    assert abs(sum(p for _, p in ranked) - 1.0) < 1e-9
    probs = [p for _, p in ranked]
    assert probs == sorted(probs, reverse=True)


def test_classic_malaria_profile():
    r = c.possible_conditions({"high_fever", "chills", "sweating", "headache"})
    assert r["items"][0]["disease"] == "Malaria"
    assert r["items"][0]["percent"] >= 50


def test_common_cold():
    r = c.possible_conditions({"cough", "runny_nose", "continuous_sneezing"})
    assert r["items"][0]["disease"] == "Common Cold"


def test_heart_attack_is_listed_for_chest_pain_breathlessness_sweating():
    r = c.possible_conditions({"chest_pain", "breathlessness", "sweating"})
    names = [i["disease"] for i in r["items"]]
    assert "Heart attack" in names
    assert any(i["serious"] for i in r["items"])


def test_mild_fever_gets_synonym_credit():
    r = c.possible_conditions({"mild_fever", "headache", "vomiting"})
    assert "Malaria" in [i["disease"] for i in r["items"]]


def test_unknown_codes_give_no_conditions():
    r = c.possible_conditions({"convulsions", "snake_bite"})
    assert r["items"] == []
    assert r["used_codes"] == []
    assert set(r["ignored_codes"]) == {"convulsions", "snake_bite"}


def test_empty_input():
    assert c.possible_conditions(set())["items"] == []
    assert c.possible_conditions(None)["items"] == []
    assert c.scores([]) == []


def test_top_n_and_min_show():
    r = c.possible_conditions({"itching", "skin_rash"})
    assert 1 <= len(r["items"]) <= c.TOP_N
    for it in r["items"]:
        assert it["match"] >= c.MIN_SHOW
        assert 1 <= it["percent"] <= 100
        assert it["name"]["en"] and it["name"]["sw"]


def test_mismatch_warning():
    serious = c.possible_conditions({"chest_pain", "breathlessness", "sweating"})
    assert c.mismatch_warning(serious, "LOW") is True
    assert c.mismatch_warning(serious, "CRITICAL") is False
    mild = c.possible_conditions({"cough", "runny_nose", "continuous_sneezing"})
    assert c.mismatch_warning(mild, "LOW") is False


def test_multinomial_beats_bernoulli_on_simulation():
    multi = c.evaluate(temperatures=(1.0,), kind="multinomial")[1.0]
    bern = c.evaluate(temperatures=(1.0,), kind="bernoulli")[1.0]
    assert multi["top3"] >= 0.95
    assert multi["top1"] >= bern["top1"]
