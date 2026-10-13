"""
Logistic Regression Classifier for SACA.
"""

import os
import sys
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
import joblib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier.base import BaseClassifier


# Swahili function / template words that sit in the CountVectorizer
# vocabulary only because the Swahili training rows are built from three
# sentence templates ("Nina dalili hizi: ...", "Ninapata dalili zifuatazo: ...",
# "Dalili ninazopata ni ..."). They carry no symptom meaning, so they must not
# count as "recognised symptoms" -- otherwise "na" or "dalili" alone would pass
# the input guard in classify().
SW_FUNCTION_WORDS = frozenset({
    "na", "ya", "wa", "kwa", "ni", "au", "la", "za", "cha", "vya", "kwenye",
    "kuwa", "dalili", "hizi", "nina", "ninapata", "ninazopata", "zifuatazo",
    "ana", "una", "yangu", "wangu",
})

# Severity returned when the input could not be assessed. build_result() only
# accepts the four real severities (and ammu_api.py indexes its replies by
# them), so an unassessed input is reported as HIGH -- the safe direction: it
# tells the user to see a health worker -- with assessed=False so every caller
# can tell it apart from a real model prediction.
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
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")

        df = pd.read_csv(filepath)
        df = df.dropna(subset=['symptom_text', 'severity'])
        df['symptom_text'] = df['symptom_text'].astype(str).str.lower().str.strip()
        df['severity'] = df['severity'].astype(str).str.upper().str.strip()
        return df

    def train(self, train_path="saca_train.csv"):
        print(f"[LogisticRegression] Loading training data from {train_path}...")
        df = self._load_data(train_path)

        X = df['symptom_text'].values
        y = df['severity'].values

        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)

        self.pipeline = Pipeline([
            ('vectorizer', CountVectorizer(
                lowercase=True,
                strip_accents='unicode',
                stop_words='english',
                max_features=500,
                min_df=2,
                max_df=0.8
            )),
            ('classifier', LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight='balanced',
                solver='lbfgs',
                random_state=42
            ))
        ])

        print(f"[LogisticRegression] Training on {len(X)} samples...")
        self.pipeline.fit(X, y_encoded)
        self.is_trained = True

        unique, counts = np.unique(y, return_counts=True)
        print("[LogisticRegression] Training class distribution:")
        for label, count in zip(unique, counts):
            print(f"  - {label}: {count} samples")

        print("[LogisticRegression] Training complete.")

    def classify(self, symptom_text: str) -> dict:
        # Empty/whitespace-only input: same convention as rule_based.py
        # and classifier/svm.py -- don't run the model on nothing, just
        # report LOW with no detected symptoms.
        if not symptom_text or not symptom_text.strip():
            result = self.build_result(
                "LOW", [], "Hakuna dalili zilizoingizwa — tafadhali ingiza dalili za mgonjwa."
            )
            result.update(assessed=False, unrecognised=[])
            return result

        if not self.is_trained:
            self.train()

        cleaned_text = symptom_text.lower().strip()

        # --- Input guard -------------------------------------------------
        # The model was trained on a fixed vocabulary (symptom codes such as
        # "high_fever" plus Swahili symptom phrases). A word outside it adds
        # nothing to the feature vector, and an all-zero vector is predicted
        # LOW at ~95%. So "I cannot breathe and have crushing chest pain" or
        # "ana homa na degedege" used to come back as LOW. Two rules:
        #   1. no recognised symptom word at all  -> not assessed
        #   2. some words not understood AND the model says LOW -> not assessed
        #      (LOW is the "safe to wait" claim; never make it while ignoring
        #      part of what the person said. MEDIUM and above still pass, with
        #      the unread words returned in `unrecognised` for the UI to show.)
        recognised, unrecognised = self._read_input(cleaned_text)

        if not recognised:
            return self._unassessed(
                symptoms=[],
                unrecognised=unrecognised,
                reason=(
                    "Hakuna dalili iliyotambulika. Tafadhali muone mtoa huduma wa afya. "
                    "/ No known symptom was recognised, so no severity was assessed. "
                    "Please see a health worker."
                ),
            )

        X = [cleaned_text]
        pred_encoded = self.pipeline.predict(X)[0]
        proba = self.pipeline.predict_proba(X)[0]

        severity = self.label_encoder.inverse_transform([pred_encoded])[0]
        confidence = float(np.max(proba))  # 0.0-1.0, as base.py's build_result() requires
        reason = f"Model predicted {severity} with {confidence * 100:.1f}% confidence"

        allowed = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        if severity not in allowed:
            severity = "LOW"

        if severity == "LOW" and unrecognised:
            return self._unassessed(
                symptoms=recognised,
                unrecognised=unrecognised,
                reason=(
                    "Maneno mengine hayakueleweka: " + ", ".join(unrecognised) + ". "
                    "Tafadhali muone mtoa huduma wa afya. "
                    "/ Some words were not understood, so a LOW result was not given. "
                    "Please see a health worker."
                ),
            )

        result = self.build_result(
            severity=severity,
            symptoms=symptom_text.split(),
            reason=reason,
            confidence=confidence
        )
        result.update(assessed=True, unrecognised=unrecognised)
        return result

    def _read_input(self, cleaned_text):
        """Split the input into (recognised, unrecognised) content words.

        Uses the fitted vectorizer's own analyzer, so tokenisation, accent
        stripping and English stop-word removal match training exactly.
        Swahili function words are ignored on both sides.
        """
        vectorizer = self.pipeline.named_steps["vectorizer"]
        vocabulary = vectorizer.vocabulary_
        tokens = [t for t in vectorizer.build_analyzer()(cleaned_text)
                  if t not in SW_FUNCTION_WORDS]
        recognised = [t for t in tokens if t in vocabulary]
        unrecognised = [t for t in tokens if t not in vocabulary]
        return recognised, unrecognised

    def _unassessed(self, symptoms, unrecognised, reason):
        result = self.build_result(
            severity=UNASSESSED_SEVERITY,
            symptoms=symptoms,
            reason=reason,
            confidence=None,
        )
        result.update(assessed=False, unrecognised=unrecognised)
        return result


if __name__ == "__main__":
    print("=" * 60)
    print("SACA Logistic Regression Classifier")
    print("=" * 60)

    clf = LogisticRegressionClassifier()
    clf.train("saca_train.csv")

    test_cases = [
        "itching skin rash fever",
        "shortness of breath chest pain cough",
        "headache fatigue nausea"
    ]

    for symptoms in test_cases:
        result = clf.classify(symptoms)
        print(f"\nInput: '{symptoms}'")
        print(f"Severity: {result['severity']}")
        print(f"Reason: {result['reason']}")