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
from classifier.symptom_codes import read_swahili, red_flag_floor, RANK

# v2 training data: symptom codes only, labelled by red-flag rules + disease
# urgency (see dataset_v2/README_v2.md). The old saca_train.csv labelled by
# symptom-count and is no longer used by the app.
DEFAULT_TRAIN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dataset_v2", "saca_v2_train.csv",
)


# Swahili filler words. They carry no symptom meaning, so they are ignored
# when deciding which words of the input were "not understood" (otherwise
# "ana homa na ..." would always report "ana" and "na"). Keep this list to
# words that cannot change a severity.
SW_FUNCTION_WORDS = frozenset({
    "na", "ya", "wa", "kwa", "ni", "au", "la", "za", "cha", "vya", "kwenye",
    "kuwa", "dalili", "hizi", "nina", "ninapata", "ninazopata", "zifuatazo",
    "ana", "una", "yangu", "wangu", "yake", "wake", "pia",
    "mtoto", "mgonjwa",
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

    def train(self, train_path=None):
        if train_path is None:
            train_path = DEFAULT_TRAIN_PATH
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

        # --- Input reading + guard ---------------------------------------
        # The model only knows symptom CODES ("high_fever", "chest_pain", ...).
        # Input can arrive as codes (from the LLM extractor) or as Swahili
        # text; read_swahili() turns Swahili phrases into codes first. A word
        # that is neither a code nor a known phrase adds nothing to the
        # feature vector, and an all-zero vector is predicted LOW. So:
        #   1. no recognised symptom at all  -> not assessed
        #   2. some words not understood AND the final severity is LOW
        #      -> not assessed (LOW is the "safe to wait" claim; never make it
        #      while ignoring part of what the person said. MEDIUM and above
        #      still pass, with the unread words returned in `unrecognised`.)
        codes, unrecognised = self._read_input(cleaned_text)

        if not codes:
            return self._unassessed(
                symptoms=[],
                unrecognised=unrecognised,
                reason=(
                    "Hakuna dalili iliyotambulika. Tafadhali muone mtoa huduma wa afya. "
                    "/ No known symptom was recognised, so no severity was assessed. "
                    "Please see a health worker."
                ),
            )

        X = [" ".join(codes)]
        pred_encoded = self.pipeline.predict(X)[0]
        proba = self.pipeline.predict_proba(X)[0]

        severity = self.label_encoder.inverse_transform([pred_encoded])[0]
        confidence = float(np.max(proba))  # 0.0-1.0, as base.py's build_result() requires
        reason = f"Model predicted {severity} with {confidence * 100:.1f}% confidence"

        allowed = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        if severity not in allowed:
            severity = "LOW"

        # --- Red-flag floor ------------------------------------------------
        # Deterministic safety net (dataset_v2/red_flags.csv): a danger sign
        # can raise the severity, never lower it. The model alone misses some
        # combinations (e.g. stiff_neck + high_fever + headache -> MEDIUM).
        floor, rule_ids = red_flag_floor(codes)
        if floor is not None and RANK[floor] > RANK[severity]:
            reason = (
                f"Red-flag rule {', '.join(rule_ids)} raised the result to {floor} "
                f"(model alone predicted {severity})"
            )
            severity = floor
            confidence = None  # the model's probability no longer describes this result

        if severity == "LOW" and unrecognised:
            return self._unassessed(
                symptoms=codes,
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
            symptoms=codes,
            reason=reason,
            confidence=confidence
        )
        result.update(assessed=True, unrecognised=unrecognised, red_flag_rules=rule_ids)
        return result

    def _read_input(self, cleaned_text):
        """Split the input into (codes, unrecognised).

        codes         symptom codes the model knows: code tokens typed or
                      extracted directly, plus codes mapped from Swahili
                      phrases (order of appearance, no duplicates).
        unrecognised  content words that are neither -- including Swahili
                      phrases that are known but have no v2 code (e.g. snake
                      bite), which the model cannot rate.
        Uses the fitted vectorizer's own analyzer on the text left over after
        Swahili phrases are consumed, so tokenisation, accent stripping and
        English stop-word removal match training exactly.
        """
        vectorizer = self.pipeline.named_steps["vectorizer"]
        vocabulary = vectorizer.vocabulary_

        reading = read_swahili(cleaned_text)
        tokens = [t for t in vectorizer.build_analyzer()(reading.residual)
                  if t not in SW_FUNCTION_WORDS]

        codes = []
        for t in tokens + reading.codes:
            if t in vocabulary and t not in codes:
                codes.append(t)
        unrecognised = [t for t in tokens if t not in vocabulary]
        unrecognised += list(reading.unmapped)
        unrecognised += [c for c in reading.codes if c not in vocabulary]
        return codes, unrecognised

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
        print(f"Severity: {result['severity']}  (assessed={result['assessed']})")
        print(f"Reason: {result['reason']}")
