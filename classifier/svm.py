"""
SACA - SVM classifier (BaseClassifier wrapper)

Wraps the SVM approach (TF-IDF + LinearSVC, one symptom per token) as
a BaseClassifier subclass so score_classifiers.py's auto-discovery and
the comparison dashboard can pick it up like every other approach.
Same vectorizer and model config as Azzam's original svm_classifier.py
- this is a restructure to fit the shared interface, not a model change.

Place this file at classifier/svm.py (must live inside the classifier
package, and the class must be defined directly in this module - not
imported from svm_classifier.py - or discover_classifiers() won't
pick it up, since it checks obj.__module__ == module.__name__).

Trains on saca_train.csv at construction time - there's no saved
model file, so every score_classifiers.py run retrains from scratch.
Run this only against the corrected saca_train.csv / saca_test.csv
(post data-leakage fix) - training on the old files will just relearn
the same memorization problem.

confidence is left as None for now. LinearSVC has no predict_proba by
default, and per base.py's own convention (see its docstring) we
don't fabricate a number just to have one - rule-based classifiers
follow the same rule. Adding real calibrated confidence is Sprint 5
task AZ4 and needs its own verification (e.g. via
CalibratedClassifierCV) before the hybrid ensemble trusts it.
"""

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

from classifier.base import BaseClassifier

TRAIN_FILE = "saca_train.csv"


class SVMClassifier(BaseClassifier):
    name = "svm"

    def __init__(self):
        train = pd.read_csv(TRAIN_FILE)
        X_train = train["symptom_text"]
        y_train = train["severity"]

        self.vectorizer = TfidfVectorizer(
            tokenizer=lambda s: s.split(),
            lowercase=False,
        )
        X_train_tfidf = self.vectorizer.fit_transform(X_train)

        self.model = LinearSVC(class_weight="balanced")
        self.model.fit(X_train_tfidf, y_train)

    def classify(self, symptom_text: str) -> dict:
        X = self.vectorizer.transform([symptom_text])
        severity = str(self.model.predict(X)[0])

        return self.build_result(
            severity=severity,
            symptoms=symptom_text.split(),
            reason=f"SVM (TF-IDF + LinearSVC) predicted {severity} from the reported symptoms.",
            confidence=None,
        )