"""
Body Map free-text box. The page sends the picked codes (p=) and the typed text (typed=) to the
assessment quiz, which classifies "<picked codes> <typed text>", so the pipeline must read that mixed string correctly. The template is checked
statically (no browser), and the mixed string is run through the real classifier.
"""
from pathlib import Path

import pytest

from classifier.pipeline import SACAPipeline

TEMPLATE = (Path(__file__).resolve().parent.parent / "templates" / "body_map.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pipeline():
    p = SACAPipeline()  # no extractor: raw-text path, no network
    p.classifier.train()
    return p


def test_template_has_free_text_box_in_both_languages():
    # The page is translated on the server now (i18n.py), so the box and its placeholder go through _().
    assert 'id="free-text"' in TEMPLATE and 'name="typed"' in TEMPLATE
    assert "_('For example: fever and headache, or: homa na maumivu ya kichwa')" in TEMPLATE
    assert 'id="form-error"' in TEMPLATE


def test_next_sends_codes_and_typed_text_to_the_quiz_and_accepts_text_only():
    assert "action=\"{{ url_for('main.assess') }}\"" in TEMPLATE and 'name="p"' in TEMPLATE
    assert 'name="mode" value="bodymap"' in TEMPLATE
    # submit is blocked only when nothing is picked AND nothing is typed
    assert 'Object.keys(seen).length > 0 || document.getElementById("free-text").value.trim() !== ""' in TEMPLATE


def test_picked_codes_plus_typed_swahili_keeps_critical(pipeline):
    r = pipeline.classify("headache dizziness ana homa na degedege")
    assert r["severity"] == "CRITICAL" and r["assessed"]


def test_picked_codes_plus_typed_danger_phrase_is_raised(pipeline):
    base = pipeline.classify("headache dizziness")["severity"]
    mixed = pipeline.classify("headache dizziness I have been vomiting blood since morning")
    assert base == "LOW"
    assert mixed["severity"] in ("HIGH", "CRITICAL")


def test_unreadable_typed_text_is_not_assessed_as_low(pipeline):
    r = pipeline.classify("headache dizziness gibberishxyz")
    assert r["severity"] != "LOW" and r["assessed"] is False
