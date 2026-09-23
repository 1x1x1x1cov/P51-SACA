from classifier.pipeline import SACAPipeline


# -------------------------------------------------
# TEST 1: Extraction succeeds
# -------------------------------------------------

def successful_extractor(raw_text):
    return "fever headache nausea"


def test_extraction_success():

    pipeline = SACAPipeline(
        extractor=successful_extractor
    )

    result = pipeline.classify(
        "The patient has a fever, headache and nausea."
    )

    assert result["fallback_used"] is False
    assert result["input_source"] == "LLM extraction"
    assert result["extracted_text"] == "fever headache nausea"


# -------------------------------------------------
# TEST 2: Extraction fails / times out
# -------------------------------------------------

def failed_extractor(raw_text):

    raise TimeoutError(
        "LLM extraction timed out"
    )


def test_extraction_failure():

    pipeline = SACAPipeline(
        extractor=failed_extractor
    )

    raw_text = (
        "The patient has a high fever "
        "and complains of headaches and nausea."
    )

    result = pipeline.classify(raw_text)

    assert result["fallback_used"] is True
    assert result["input_source"] == "Raw text fallback"
    assert result["extracted_text"] is None


# -------------------------------------------------
# TEST 3: Extraction returns empty text
# -------------------------------------------------

def empty_extractor(raw_text):
    return ""


def test_empty_extraction():

    pipeline = SACAPipeline(
        extractor=empty_extractor
    )

    result = pipeline.classify(
        "The patient has fever and nausea."
    )

    assert result["fallback_used"] is True