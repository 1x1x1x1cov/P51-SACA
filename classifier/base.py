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

    #: Short identifier used in comparison results and logging,
    #: e.g. "rule_based", "random_forest", "svm", "logistic_regression", "hybrid".
    name: str = "base"

    @abstractmethod
    def classify(self, symptom_text: str) -> dict:
        """
        Classify raw symptom text and return a severity result.

        Args:
            symptom_text: Raw Swahili symptom input from the user.

        Returns:
            dict shaped by build_result(), containing severity,
            severity_sw, symptoms, reason, and disclaimer.
        """
        raise NotImplementedError

    def build_result(self, severity: str, symptoms: list, reason: str) -> dict:
        """
        Build a standardised result dict. All subclasses should use
        this instead of constructing the return dict by hand, so the
        output shape can't drift between approaches.
        """
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}' from classifier '{self.name}'. "
                f"Must be one of {sorted(VALID_SEVERITIES)}."
            )

        return {
            "severity": severity,
            "severity_sw": SEVERITY_SW[severity],
            "symptoms": symptoms,
            "reason": reason,
            "disclaimer": DISCLAIMER,
            "classifier": self.name,
        }