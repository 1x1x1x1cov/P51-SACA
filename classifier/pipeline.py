"""
SACA classification pipeline.

Attempts symptom extraction first.
If extraction fails, times out, or returns empty text,
the original raw symptom text is passed directly to
LogisticRegressionClassifier.classify().

Safety rule: the LLM extractor may add information but can never LOWER the
result. When extraction succeeds, the typed text is also read directly by the
classifier's own reader, and if that reading is more serious than the
extracted symptoms, the more serious result is returned. (An extractor can
mistranslate: "ana homa na degedege" has been extracted as "high_fever cough",
which drops the convulsions.)
"""
from classifier.logistic_regression import LogisticRegressionClassifier

SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# Danger tokens the extractor may emit that the classifier's reader does not
# know by that name, rewritten to words the reader does understand.
EXTRACTOR_TOKEN_TO_PHRASE = {
    "vomiting_blood": "vomiting blood",
    "loss_of_consciousness": "unconscious",
    "severe_bleeding": "heavy bleeding",
}


def _normalise_extracted(extracted_text: str) -> str:
    """Rewrite known extractor-only danger tokens into words the reader knows."""
    words = extracted_text.split()
    return " ".join(EXTRACTOR_TOKEN_TO_PHRASE.get(word, word) for word in words)


def _rank(result: dict) -> int:
    return SEVERITY_RANK.get(result.get("severity"), -1)


class SACAPipeline:

    def __init__(self, extractor=None):
        self.classifier = LogisticRegressionClassifier()
        self.extractor = extractor

    def classify(self, raw_text: str) -> dict:

        if not raw_text or not raw_text.strip():
            return self.classifier.classify(raw_text)

        if self.extractor is not None:

            try:
                extracted_text = self.extractor(raw_text)

                if extracted_text and extracted_text.strip():

                    print("[Pipeline] Symptom extraction succeeded.")
                    print(f"[Pipeline] Extracted: {extracted_text}")

                    result = self.classifier.classify(
                        _normalise_extracted(extracted_text)
                    )

                    result["input_source"] = "LLM extraction"
                    result["extracted_text"] = extracted_text
                    result["fallback_used"] = False
                    result["raised_by_raw_text"] = False

                    # The extractor must never lower the result: also read the
                    # typed text directly and keep the more serious outcome.
                    # A "not assessed" reading is ignored here, because it only
                    # means the reader did not understand the text.
                    raw_result = self.classifier.classify(raw_text)

                    if (
                        raw_result.get("assessed", True)
                        and _rank(raw_result) > _rank(result)
                    ):
                        print(
                            "[Pipeline] Typed text is more serious than the "
                            "extracted symptoms; using the higher level."
                        )

                        extracted_level = result["severity"]

                        raw_result["input_source"] = (
                            "LLM extraction + typed-text check"
                        )
                        raw_result["extracted_text"] = extracted_text
                        raw_result["fallback_used"] = False
                        raw_result["raised_by_raw_text"] = True
                        raw_result["reason"] = (
                            f"{raw_result.get('reason', '')} "
                            "The typed text indicated a more serious level "
                            f"than the extracted symptoms ({extracted_level})."
                        ).strip()

                        return raw_result

                    return result

                print("[Pipeline] Extraction returned empty text.")

            except TimeoutError:
                print("[Pipeline] LLM extraction timed out.")

            except Exception as e:
                print(f"[Pipeline] LLM extraction failed: {e}")

        print("[Pipeline] Using raw symptom text fallback.")

        result = self.classifier.classify(raw_text)

        result["input_source"] = "Raw text fallback"
        result["extracted_text"] = None
        result["fallback_used"] = True
        result["raised_by_raw_text"] = False

        return result
