"""
SACA - Abstract classifier interface

Every classification approach (rule-based, Random Forest, SVM,
Logistic Regression, hybrid ensemble) must inherit from
BaseClassifier and implement classify().

This keeps all five approaches interchangeable behind a single
FastAPI endpoint, and keeps their output format consistent so the
frontend and comparison/evaluation code don't need to know which
approach produced a given result.
"""

from abc import ABC, abstractmethod


SEVERITY_SW = {
    "CRITICAL": "HATARI",
    "HIGH": "HARAKA",
    "MEDIUM": "WASTANI",
    "LOW": "SALAMA",
}

VALID_SEVERITIES = set(SEVERITY_SW.keys())

DISCLAIMER = "Matokeo haya ni ya msaada tu. Tafadhali wasiliana na mtoa huduma wa afya."


class BaseClassifier(ABC):
    """
    Abstract base class for all SACA symptom classifiers.

    Subclasses must implement classify(symptom_text) and return a
    dict built with build_result(), so every approach returns the
    same shape regardless of the underlying method.
    """

    name: str = "base"

    @abstractmethod
    def classify(self, symptom_text: str) -> dict:
        raise NotImplementedError

    def build_result(
        self, severity: str, symptoms: list, reason: str, confidence: float | None = None
    ) -> dict:
        """
        Build a standardised result dict. All subclasses should use
        this instead of constructing the return dict by hand, so the
        output shape can't drift between approaches.

        confidence is optional: rule-based classifiers have no real
        probability to report (they're deterministic if/else logic),
        so they should simply omit it, leaving it as None rather than
        fabricating a number. ML approaches (SVM, Random Forest,
        Logistic Regression) that support predict_proba() should pass
        the probability of the predicted class here.
        """
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}' from classifier '{self.name}'. "
                f"Must be one of {sorted(VALID_SEVERITIES)}."
            )

        if confidence is not None:
            if not isinstance(confidence, (int, float)):
                raise ValueError(
                    f"confidence must be a number or None, got {type(confidence).__name__} "
                    f"from classifier '{self.name}'."
                )
            if not (0.0 <= confidence <= 1.0):
                raise ValueError(
                    f"confidence must be between 0 and 1, got {confidence} "
                    f"from classifier '{self.name}'."
                )
            confidence = round(float(confidence), 4)

        return {
            "severity": severity,
            "severity_sw": SEVERITY_SW[severity],
            "symptoms": symptoms,
            "reason": reason,
            "disclaimer": DISCLAIMER,
            "classifier": self.name,
            "confidence": confidence,
        }