
"""
Logistic Regression Classifier for SACA.
"""

import os
import sys

import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from classifier.base import BaseClassifier
from classifier.symptom_codes import (
    read_input,
    red_flag_floor,
    only_nonspecific,
    RANK,
    EN_FILLER_WORDS,
)


def resource_path(relative_path):
    """
    Return the absolute path to a bundled resource.

    During development, resources are resolved relative to
    the project directory.

    When packaged with PyInstaller, resources are resolved
    from the bundle directory.
    """

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

    return os.path.join(base_path, relative_path)


# Version 2 dataset: symptom codes labelled using red-flag rules
# and disease urgency.
DEFAULT_TRAIN_PATH = resource_path(
    os.path.join(
        "dataset_v2",
        "saca_v2_train.csv"
    )
)


# Swahili filler words that do not contribute symptom meaning.
SW_FUNCTION_WORDS = frozenset({
    "na", "ya", "wa", "kwa", "ni", "au", "la", "za",
    "cha", "vya", "kwenye", "kuwa", "dalili", "hizi",
    "nina", "ninapata", "ninazopata", "zifuatazo",
    "ana", "una", "yangu", "wangu", "yake", "wake",
    "pia", "mtoto", "mgonjwa",
}) | EN_FILLER_WORDS


# An unassessed input must not be presented as a genuine LOW result.
UNASSESSED_SEVERITY = "HIGH"


class LogisticRegressionClassifier(BaseClassifier):

    name = "logistic_regression"

    def __init__(self, model_path=None):
        super().__init__()

        self.model_path = model_path
        self.pipeline = None
        self.label_encoder = None
        self.is_trained = False

    def _load_data(self, filepath):
        """Load and clean the training dataset."""

        if not os.path.exists(filepath):
            raise FileNotFoundError(
                f"Data file not found: {filepath}"
            )

        df = pd.read_csv(filepath)

        df = df.dropna(
            subset=[
                "symptom_text",
                "severity"
            ]
        )

        df["symptom_text"] = (
            df["symptom_text"]
            .astype(str)
            .str.lower()
            .str.strip()
        )

        df["severity"] = (
            df["severity"]
            .astype(str)
            .str.upper()
            .str.strip()
        )

        return df

    def train(self, train_path=None):
        """Train the Logistic Regression model."""

        if train_path is None:
            train_path = DEFAULT_TRAIN_PATH

        print(
            f"[LogisticRegression] "
            f"Loading training data from {train_path}..."
        )

        df = self._load_data(train_path)

        X = df["symptom_text"].values
        y = df["severity"].values

        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)

        self.pipeline = Pipeline([
            (
                "vectorizer",
                CountVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    stop_words="english",
                    max_features=500,
                    min_df=2,
                    max_df=0.8
                )
            ),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    max_iter=1000,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=42
                )
            )
        ])

        print(
            f"[LogisticRegression] "
            f"Training on {len(X)} samples..."
        )

        self.pipeline.fit(X, y_encoded)
        self.is_trained = True

        unique, counts = np.unique(
            y,
            return_counts=True
        )

        print(
            "[LogisticRegression] "
            "Training class distribution:"
        )

        for label, count in zip(unique, counts):
            print(f"  - {label}: {count} samples")

        print(
            "[LogisticRegression] "
            "Training complete."
        )

    def classify(self, symptom_text: str) -> dict:
        """Classify symptoms and return the predicted severity."""

        # Handle empty input without running the model.
        if not symptom_text or not symptom_text.strip():
            result = self.build_result(
                "LOW",
                [],
                "Hakuna dalili zilizoingizwa — "
                "tafadhali ingiza dalili za mgonjwa."
            )

            result.update(
                assessed=False,
                unrecognised=[]
            )

            return result

        if not self.is_trained:
            self.train()

        cleaned_text = symptom_text.lower().strip()

        # Convert English and Swahili input into recognised symptom codes.
        codes, unrecognised = self._read_input(cleaned_text)

        # Do not assess input when no known symptom was recognised.
        if not codes:
            return self._unassessed(
                symptoms=[],
                unrecognised=unrecognised,
                reason=(
                    "Hakuna dalili iliyotambulika. "
                    "Tafadhali muone mtoa huduma wa afya. "
                    "/ No known symptom was recognised, so no "
                    "severity was assessed. Please see a health worker."
                )
            )

        # Predict using the recognised symptom codes.
        X = [" ".join(codes)]

        pred_encoded = self.pipeline.predict(X)[0]
        proba = self.pipeline.predict_proba(X)[0]

        severity = self.label_encoder.inverse_transform(
            [pred_encoded]
        )[0]

        confidence = float(np.max(proba))

        # A logistic regression adds up the evidence, so several strong danger signs push the top probability
        # towards 1.0. Showing "100.0%" would overstate it, so anything from 99% up is written as ">99%".
        confidence_text = (
            ">99%" if confidence >= 0.99 else f"{confidence * 100:.1f}%"
        )

        reason = (
            f"Model predicted {severity} "
            f"with {confidence_text} confidence"
        )

        allowed = {
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW"
        }

        if severity not in allowed:
            severity = "LOW"

        # Prevent non-specific symptoms alone from receiving
        # a HIGH or CRITICAL result.
        if (
            RANK[severity] > RANK["MEDIUM"]
            and only_nonspecific(codes)
        ):
            reason = (
                "Only non-specific symptoms reported, "
                f"so the result is capped at MEDIUM "
                f"(model alone predicted {severity})"
            )

            severity = "MEDIUM"
            confidence = None

        # Red-flag rules can raise severity but never lower it.
        floor, rule_ids = red_flag_floor(codes)

        if (
            floor is not None
            and RANK[floor] > RANK[severity]
        ):
            reason = (
                f"Red-flag rule {', '.join(rule_ids)} "
                f"raised the result to {floor} "
                f"(model alone predicted {severity})"
            )

            severity = floor
            confidence = None

        # Never return LOW if some input words were not understood.
        if severity == "LOW" and unrecognised:
            return self._unassessed(
                symptoms=codes,
                unrecognised=unrecognised,
                reason=(
                    "Maneno mengine hayakueleweka: "
                    + ", ".join(unrecognised)
                    + ". Tafadhali muone mtoa huduma wa afya. "
                    "/ Some words were not understood, so a LOW "
                    "result was not given. Please see a health worker."
                )
            )

        result = self.build_result(
            severity=severity,
            symptoms=codes,
            reason=reason,
            confidence=confidence
        )

        result.update(
            assessed=True,
            unrecognised=unrecognised,
            red_flag_rules=rule_ids
        )

        return result

    def _read_input(self, cleaned_text):
        """
        Return recognised symptom codes and unrecognised input.

        Supports symptom codes, English phrases and Swahili phrases.
        """

        vectorizer = self.pipeline.named_steps["vectorizer"]
        vocabulary = vectorizer.vocabulary_

        reading = read_input(cleaned_text)

        tokens = [
            token
            for token in vectorizer.build_analyzer()(
                reading.residual
            )
            if token not in SW_FUNCTION_WORDS
        ]

        codes = []

        for token in tokens + reading.codes:
            if token in vocabulary and token not in codes:
                codes.append(token)

        # Preserve the order in which symptoms appeared in the input.
        def position(code):
            if code in reading.positions:
                return reading.positions[code]

            index = cleaned_text.find(code)

            return index if index >= 0 else len(cleaned_text)

        codes.sort(key=position)

        unrecognised = [
            token
            for token in tokens
            if token not in vocabulary
        ]

        unrecognised += list(reading.unmapped)

        unrecognised += [
            code
            for code in reading.codes
            if code not in vocabulary
        ]

        # Remove duplicate unrecognised entries while preserving order.
        unrecognised = list(dict.fromkeys(unrecognised))

        return codes, unrecognised

    def _unassessed(self, symptoms, unrecognised, reason):
        """Return a result that explicitly indicates no reliable assessment."""

        result = self.build_result(
            severity=UNASSESSED_SEVERITY,
            symptoms=symptoms,
            reason=reason,
            confidence=None
        )

        result.update(
            assessed=False,
            unrecognised=unrecognised
        )

        return result


if __name__ == "__main__":

    print("=" * 60)
    print("SACA Logistic Regression Classifier")
    print("=" * 60)

    clf = LogisticRegressionClassifier()
    clf.train()

    test_cases = [
        "itching skin_rash high_fever",
        "chest_pain breathlessness",
        "headache fatigue nausea",
        "ana homa na degedege",
        "kukohoa damu",
    ]

    for symptoms in test_cases:
        result = clf.classify(symptoms)

        print(f"\nInput: '{symptoms}'")
        print(
            f"Severity: {result['severity']} "
            f"(assessed={result['assessed']})"
        )
        print(f"Reason: {result['reason']}")
