"""
SACA classification pipeline.

Attempts symptom extraction first.
If extraction fails, times out, or returns empty text,
the original raw symptom text is passed directly to
LogisticRegressionClassifier.classify().
"""
from classifier.logistic_regression import LogisticRegressionClassifier


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
                        extracted_text
                    )

                    result["input_source"] = "LLM extraction"
                    result["extracted_text"] = extracted_text
                    result["fallback_used"] = False

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

        return result