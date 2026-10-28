"""The LLM extractor must never be able to lower a result."""
import pytest

from classifier.pipeline import SACAPipeline


@pytest.fixture(scope="module")
def trained_classifier():
    pipeline = SACAPipeline()
    pipeline.classifier.train()
    return pipeline.classifier


def make(trained_classifier, extractor):
    pipeline = SACAPipeline(extractor=extractor)
    pipeline.classifier = trained_classifier
    return pipeline


def test_mistranslated_extraction_cannot_lower_the_result(trained_classifier):
    # Real case: the extractor returned "high_fever cough" for this phrase,
    # dropping the convulsions (degedege).
    pipeline = make(trained_classifier, lambda text: "high_fever cough")

    result = pipeline.classify("ana homa na degedege")

    assert result["severity"] == "CRITICAL"
    assert result["raised_by_raw_text"] is True
    assert result["extracted_text"] == "high_fever cough"
    assert result["fallback_used"] is False
    assert "typed text" in result["reason"]


def test_extraction_can_still_raise_the_result(trained_classifier):
    pipeline = make(trained_classifier, lambda text: "high_fever convulsions")

    result = pipeline.classify("kikohozi")

    assert result["severity"] == "CRITICAL"
    assert result["raised_by_raw_text"] is False
    assert result["input_source"] == "LLM extraction"


def test_unreadable_typed_text_does_not_override_extraction(trained_classifier):
    # The reader cannot read this sentence ("not assessed"). That must not
    # beat a good extraction.
    pipeline = make(trained_classifier, lambda text: "high_fever convulsions")

    result = pipeline.classify("my child has been shaking and is hot")

    assert result["severity"] == "CRITICAL"
    assert result["raised_by_raw_text"] is False
    assert result["input_source"] == "LLM extraction"


def test_equal_levels_keep_the_extraction_path(trained_classifier):
    pipeline = make(trained_classifier, lambda text: "cough")

    result = pipeline.classify("kikohozi")

    assert result["raised_by_raw_text"] is False
    assert result["input_source"] == "LLM extraction"


@pytest.mark.parametrize(
    "token, expected_level",
    [
        ("vomiting_blood", "HIGH"),
        ("loss_of_consciousness", "CRITICAL"),
        ("severe_bleeding", "CRITICAL"),
    ],
)
def test_extractor_only_danger_tokens_are_understood(
    trained_classifier, token, expected_level
):
    pipeline = make(trained_classifier, lambda text: token)

    result = pipeline.classify("zzz qqq")

    assert result["assessed"] is True
    assert result["severity"] == expected_level


def test_vomiting_blood_with_fever_is_not_lowered(trained_classifier):
    pipeline = make(trained_classifier, lambda text: "vomiting_blood fever")

    result = pipeline.classify("zzz qqq")

    assert result["severity"] in ("HIGH", "CRITICAL")


def test_extraction_failure_still_falls_back(trained_classifier):
    def failing(text):
        raise TimeoutError("timed out")

    pipeline = make(trained_classifier, failing)

    result = pipeline.classify("ana homa na degedege")

    assert result["fallback_used"] is True
    assert result["severity"] == "CRITICAL"
