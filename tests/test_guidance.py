"""Tests for guidance.py: the content of the result cards (clinic advice, self-care, medicine information)."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import guidance as g  # noqa: E402

LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _all_texts(obj):
    """Yield every {"en", "sw"} dict anywhere inside obj."""
    if isinstance(obj, dict):
        if set(obj.keys()) == {"en", "sw"}:
            yield obj
            return
        for v in obj.values():
            yield from _all_texts(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            yield from _all_texts(v)


def _module_texts():
    blocks = [g.TIERS, g.SELF_CARE, g.SYMPTOM_SELF_CARE, g.DANGER_SIGNS, g.TOPICS, g.AGE_NOTES,
              g.DURATION_NOTES, g.CAVEAT, g.MEDICINES, g.MED_URGENT, g.MED_GENERAL, g.MED_NOT_ASSESSED, g.LEVEL_NAMES]
    return list(_all_texts(blocks))


def test_every_text_has_english_and_swahili():
    texts = _module_texts()
    assert len(texts) > 150
    for t in texts:
        assert t["en"].strip(), t
        assert t["sw"].strip(), t
        assert t["en"] != t["sw"] or t["en"].isupper(), t  # Swahili must not be a copy of the English


def test_no_doses_anywhere():
    dose = re.compile(r"\b\d+(\.\d+)?\s?(mg|ml|g|mcg|tablets? (a|per) day)\b", re.I)
    for t in _module_texts():
        assert not dose.search(t["en"]), t["en"]
        assert not dose.search(t["sw"]), t["sw"]


def test_only_known_medicines_are_named():
    allowed = {"paracetamol", "ibuprofen", "aspirin", "ors", "zinc"}
    risky = ["amoxicillin", "artemether", "coartem", "quinine", "metronidazole", "ciprofloxacin", "diclofenac",
             "codeine", "tramadol", "morphine", "cotrimoxazole", "doxycycline", "loperamide", "prednisolone"]
    for t in _module_texts():
        low = t["en"].lower()
        for name in risky:
            assert name not in low, (name, t["en"])
    assert {m["id"] for m in g.MEDICINES} <= {"paracetamol", "ibuprofen", "aspirin", "malaria_test", "ors_zinc", "cold"}
    assert allowed  # documented list


def test_every_tier_has_headline_timeframe_steps():
    for key in LEVELS + ["NOT_ASSESSED"]:
        tier = g.TIERS[key]
        assert tier["headline"]["en"] and tier["timeframe"]["en"]
        assert len(tier["steps"]) >= 2
        assert g.SELF_CARE[key]


def test_critical_says_now_and_has_no_home_care():
    r = g.build_guidance("CRITICAL", True, {"chest_pain"})
    assert "now" in r["headline"]["en"].lower() or "immediately" in r["timeframe"]["en"].lower()
    assert r["danger_signs"] is None
    assert r["medicine"]["mode"] == "urgent"
    assert r["medicine"]["items"] == []


def test_high_has_no_medicine_items():
    r = g.build_guidance("HIGH", True, {"high_fever", "headache"})
    assert r["medicine"]["mode"] == "urgent"
    assert r["medicine"]["items"] == []
    joined = " ".join(t["en"] for t in r["medicine"]["general"]).lower()
    assert "do not delay" in joined


def test_not_assessed_falls_back():
    r = g.build_guidance("LOW", False, {"headache"})
    assert r["level_key"] == "NOT_ASSESSED"
    assert r["medicine"]["mode"] == "none"
    assert r["medicine"]["items"] == []


def test_unknown_severity_is_not_assessed():
    r = g.build_guidance("BANANA", True, set())
    assert r["level_key"] == "NOT_ASSESSED"


def test_convulsions_topic_says_nothing_in_mouth():
    r = g.build_guidance("CRITICAL", True, {"convulsions"})
    topic = next(t for t in r["topics"] if t["id"] == "convulsions")
    donts = " ".join(t["en"] for t in topic["dont"]).lower()
    assert "anything in the mouth" in donts
    assert "hold" in donts


def test_snakebite_rejects_harmful_first_aid():
    topic = next(t for t in g.TOPICS if t["id"] == "snakebite")
    donts = " ".join(t["en"] for t in topic["dont"]).lower()
    for word in ["cut", "suck", "tie", "ice"]:
        assert word in donts


def test_topic_cap_and_order():
    codes = {"coma", "breathlessness", "uncontrolled_bleeding", "convulsions", "snake_bite", "burns"}
    r = g.build_guidance("CRITICAL", True, codes)
    ids = [t["id"] for t in r["topics"]]
    assert len(ids) == g.MAX_TOPICS
    assert ids == ["unconscious", "breathing", "bleeding"]


def test_meningitis_needs_fever():
    assert "meningitis" not in [t["id"] for t in g.topics_for({"stiff_neck"})]
    assert "meningitis" in [t["id"] for t in g.topics_for({"stiff_neck", "high_fever"})]


def test_pregnant_headache_high_shows_pregnancy_topic():
    r = g.build_guidance("HIGH", True, {"headache", "pregnancy"}, pregnant=True)
    assert "pregnancy" in [t["id"] for t in r["topics"]]
    assert any("pregnant" in n["en"].lower() for n in r["notes"])


def test_low_paracetamol_for_adult_fever():
    r = g.build_guidance("LOW", True, {"mild_fever", "headache"}, age_years=30)
    ids = [i["id"] for i in r["medicine"]["items"]]
    assert "paracetamol" in ids and "malaria_test" in ids
    assert "aspirin" not in ids  # aspirin warning is for children only
    assert r["medicine"]["mode"] == "info"
    assert any("packet" in t["en"] for t in r["medicine"]["general"])


def test_ibuprofen_blocked_in_pregnancy():
    r = g.build_guidance("MEDIUM", True, {"headache"}, pregnant=True, age_years=27)
    ibu = next(i for i in r["medicine"]["items"] if i["id"] == "ibuprofen")
    assert ibu["blocked"]
    assert "pregnancy" in ibu["points"][0]["en"].lower()
    para = next(i for i in r["medicine"]["items"] if i["id"] == "paracetamol")
    assert not para["blocked"]
    assert any("pregnancy" in p["en"].lower() for p in para["points"])


def test_ibuprofen_blocked_with_dehydration_signs():
    r = g.build_guidance("MEDIUM", True, {"mild_fever", "diarrhoea"}, age_years=8)
    ibu = next(i for i in r["medicine"]["items"] if i["id"] == "ibuprofen")
    assert ibu["blocked"]
    assert "ors_zinc" in [i["id"] for i in r["medicine"]["items"]]


def test_young_baby_blocks_paracetamol_and_ibuprofen():
    r = g.build_guidance("LOW", True, {"mild_fever"}, age_group="infant", age_months_total=1)
    items = {i["id"]: i for i in r["medicine"]["items"]}
    assert items["paracetamol"]["blocked"]
    assert items["ibuprofen"]["blocked"]
    assert "aspirin" in items  # child: the aspirin warning shows


def test_aspirin_warning_when_age_unknown():
    r = g.build_guidance("LOW", True, {"headache"})
    assert "aspirin" in [i["id"] for i in r["medicine"]["items"]]


def test_no_matching_medicine():
    r = g.build_guidance("LOW", True, {"itching"})
    assert r["medicine"]["mode"] == "none_matched"
    assert r["medicine"]["items"] == []


def test_cold_says_antibiotics_do_not_help():
    r = g.build_guidance("LOW", True, {"runny_nose", "cough"}, age_years=40)
    cold = next(i for i in r["medicine"]["items"] if i["id"] == "cold")
    assert "antibiotics do not help" in cold["points"][0]["en"].lower()
    care = " ".join(t["en"] for t in r["self_care"]["steps"]).lower()
    assert "honey" in care and "under 1" in care


def test_four_cards_present():
    r = g.build_guidance("MEDIUM", True, {"cough"}, age_years=40)
    for k in ("clinic", "self_care", "medicine"):
        assert k in r
    assert r["clinic"]["steps"] and r["self_care"]["steps"]
    assert r["self_care"]["danger_signs"] is not None


def test_long_duration_note_for_low_only():
    low = g.build_guidance("LOW", True, {"cough"}, duration="long")
    crit = g.build_guidance("CRITICAL", True, {"cough"}, duration="long")
    assert any("week" in n["en"] for n in low["notes"])
    assert not any("week" in n["en"] for n in crit["notes"])


def test_status_marks_draft():
    r = g.build_guidance("LOW", True, {"cough"})
    assert "DRAFT" in r["status"]
    assert "not" in r["caveat"]["en"].lower()


def test_spoken_summary_languages():
    r = g.build_guidance("CRITICAL", True, {"snake_bite"})
    en = g.spoken_summary(r, "en")
    sw = g.spoken_summary(r, "sw")
    assert "Snakebite" in en
    assert "nyoka" in sw
    assert g.spoken_summary(r, "fr") == en


def test_known_swahili_typos_fixed():
    for t in _module_texts():
        assert "naunywe" not in t["sw"]
        assert "uungua ni" not in t["sw"]
        assert "kwenye uungua" not in t["sw"]


def test_estimated_baby_gets_no_medicine_with_an_age_limit():
    # Age typed as "0 years": could be 1 week or 11 months, so the 2- and 3-month limits cannot be checked.
    r = g.build_guidance("LOW", True, {"mild_fever"}, age_group="infant", age_years=0, age_months_total=0,
                         age_estimated=True)
    items = {i["id"]: i for i in r["medicine"]["items"]}
    for med in ("paracetamol", "ibuprofen"):
        assert items[med]["blocked"]
        assert "under 1 year" in items[med]["points"][0]["en"]


def test_exact_dob_baby_keeps_the_nhs_age_limits():
    r = g.build_guidance("LOW", True, {"mild_fever"}, age_group="infant", age_years=0, age_months_total=6)
    items = {i["id"]: i for i in r["medicine"]["items"]}
    assert not items["paracetamol"]["blocked"]
    assert not items["ibuprofen"]["blocked"]
