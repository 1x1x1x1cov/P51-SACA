"""
SACA - Support Vector Machine (SVM) classifier

Approach 2 of 5.

Uses TF-IDF feature extraction and a Linear Support Vector Machine
to classify patient symptoms into four severity tiers:

    LOW
    MEDIUM
    HIGH
    CRITICAL

The model is fine-tuned using stratified cross-validation over:
    - TF-IDF n-gram range
    - minimum document frequency
    - SVM regularisation parameter (C)
    - class weighting

The best configuration is selected using macro F1-score so that
each severity class is given equal importance.

This classifier is an ML-based approach and does not contain
manually written medical decision rules.
"""

from pathlib import Path

import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    classification_report,
)

import seaborn as sns
import matplotlib.pyplot as plt

from classifier.base import BaseClassifier


class SVMClassifier(BaseClassifier):
    name = "svm"

    def __init__(self):
        """
        Initialise the SVM classifier.

        The model is trained when the classifier is created.
        """

        # Find the project root.
        # svm.py is expected to be inside:
        #
        #     project/
        #         classifier/
        #             svm.py
        #
        self.project_root = Path(__file__).resolve().parent.parent

        self.train_path = self.project_root / "saca_train.csv"

        if not self.train_path.exists():
            raise FileNotFoundError(
                f"Training dataset not found: {self.train_path}"
            )

        # Load training data
        train = pd.read_csv(self.train_path)

        # Check required columns
        required_columns = {"symptom_text", "severity"}

        missing_columns = required_columns - set(train.columns)

        if missing_columns:
            raise ValueError(
                f"Training dataset is missing columns: {missing_columns}"
            )

        # Remove missing values
        train = train.dropna(
            subset=["symptom_text", "severity"]
        )

        X_train = train["symptom_text"].astype(str)
        y_train = train["severity"].astype(str)

        # Pipeline:
        # TF-IDF -> Linear SVM
        pipeline = Pipeline([
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=False,
                    sublinear_tf=True
                )
            ),
            (
                "svm",
                LinearSVC()
            )
        ])

        # Parameters to fine-tune
        parameters = {
            "tfidf__ngram_range": [
                (1, 1),
                (1, 2)
            ],

            "tfidf__min_df": [
                1,
                2
            ],

            "svm__C": [
                0.1,
                1,
                10
            ],

            "svm__class_weight": [
                None,
                "balanced"
            ]
        }

        # Stratified cross-validation ensures each fold contains
        # approximately the same proportion of severity classes.
        cv = StratifiedKFold(
            n_splits=5,
            shuffle=True,
            random_state=42
        )

        # Grid search
        self.grid_search = GridSearchCV(
            estimator=pipeline,
            param_grid=parameters,
            scoring="f1_macro",
            cv=cv,
            n_jobs=-1,
            refit=True
        )

        # Train and tune the model
        self.grid_search.fit(X_train, y_train)

        # Best trained model
        self.model = self.grid_search.best_estimator_

        # Store useful information about training
        self.best_params = self.grid_search.best_params_
        self.best_cv_score = self.grid_search.best_score_

        self.classes = list(self.model.named_steps["svm"].classes_)

    def classify(self, symptom_text: str) -> dict:
        """
        Classify a patient's symptoms.

        Args:
            symptom_text: Patient symptoms as text.

        Returns:
            Result dictionary produced by BaseClassifier.build_result().
        """

        # Handle empty input
        if not symptom_text or not symptom_text.strip():
            return self.build_result(
                "LOW",
                [],
                "Hakuna dalili zilizoingizwa — tafadhali ingiza dalili za mgonjwa."
            )

        # Convert input to string
        symptom_text = str(symptom_text).strip()

        # Predict severity
        prediction = self.model.predict([symptom_text])[0]

        # Convert prediction into a list of symptoms/tokens.
        # This is only for displaying the recognised input through
        # the common BaseClassifier interface.
        symptoms = symptom_text.split()

        # Generate a simple explanation.
        reasons = {
            "LOW": (
                "Mfano wa dalili unaonyesha kiwango cha chini cha hatari."
            ),

            "MEDIUM": (
                "Mfano wa dalili unaonyesha kiwango cha wastani cha hatari."
            ),

            "HIGH": (
                "Mfano wa dalili unaonyesha kiwango kikubwa cha hatari."
            ),

            "CRITICAL": (
                "Mfano wa dalili unaonyesha kiwango muhimu cha hatari."
            )
        }

        reason = reasons.get(
            prediction,
            "Dalili zimeainishwa kulingana na modeli ya SVM."
        )

        return self.build_result(
            prediction,
            symptoms,
            reason
        )


def evaluate_model():
    """
    Evaluate the fine-tuned SVM against the held-out test dataset.

    The test dataset is NOT used during hyperparameter tuning.
    """

    project_root = Path(__file__).resolve().parent.parent

    train_path = project_root / "saca_train.csv"
    test_path = project_root / "saca_test.csv"

    if not train_path.exists():
        raise FileNotFoundError(
            f"Training dataset not found: {train_path}"
        )

    if not test_path.exists():
        raise FileNotFoundError(
            f"Test dataset not found: {test_path}"
        )

    # Load datasets
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)

    # Remove missing values
    train = train.dropna(
        subset=["symptom_text", "severity"]
    )

    test = test.dropna(
        subset=["symptom_text", "severity"]
    )

    X_train = train["symptom_text"].astype(str)
    y_train = train["severity"].astype(str)

    X_test = test["symptom_text"].astype(str)
    y_test = test["severity"].astype(str)

    # ---------------------------------------------------------
    # Build and tune model
    # ---------------------------------------------------------

    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                lowercase=False,
                sublinear_tf=True
            )
        ),
        (
            "svm",
            LinearSVC()
        )
    ])

    parameters = {
        "tfidf__ngram_range": [
            (1, 1),
            (1, 2)
        ],

        "tfidf__min_df": [
            1,
            2
        ],

        "svm__C": [
            0.1,
            1,
            10
        ],

        "svm__class_weight": [
            None,
            "balanced"
        ]
    }

    cv = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=42
    )

    grid_search = GridSearchCV(
        pipeline,
        parameters,
        scoring="f1_macro",
        cv=cv,
        n_jobs=-1,
        refit=True
    )

    print("Training and fine-tuning SVM...")
    print()

    grid_search.fit(X_train, y_train)

    model = grid_search.best_estimator_

    # ---------------------------------------------------------
    # Display best configuration
    # ---------------------------------------------------------

    print("=" * 60)
    print("BEST SVM CONFIGURATION")
    print("=" * 60)

    print("Best parameters:")
    for parameter, value in grid_search.best_params_.items():
        print(f"  {parameter}: {value}")

    print()
    print(
        f"Best cross-validation macro F1: "
        f"{grid_search.best_score_:.4f}"
    )

    # ---------------------------------------------------------
    # Test set
    # ---------------------------------------------------------

    predictions = model.predict(X_test)

    accuracy = accuracy_score(
        y_test,
        predictions
    )

    print()
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    print(f"Accuracy: {accuracy:.4f}")

    # ---------------------------------------------------------
    # Classification report
    # ---------------------------------------------------------

    labels = [
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL"
    ]

    print()
    print("Classification Report:")
    print()

    print(
        classification_report(
            y_test,
            predictions,
            labels=labels,
            zero_division=0
        )
    )

    # ---------------------------------------------------------
    # Confusion matrix
    # ---------------------------------------------------------

    cm = confusion_matrix(
        y_test,
        predictions,
        labels=labels
    )

    plt.figure(figsize=(8, 6))

    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        xticklabels=labels,
        yticklabels=labels
    )

    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("SVM Severity Classification")

    plt.tight_layout()
    plt.show()

    # ---------------------------------------------------------
    # Sample predictions
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("SAMPLE PREDICTIONS")
    print("=" * 60)

    number_of_samples = min(10, len(X_test))

    for i in range(number_of_samples):

        print()
        print(f"Symptoms: {X_test.iloc[i]}")
        print(f"Actual: {y_test.iloc[i]}")
        print(f"Predicted: {predictions[i]}")
        print("-" * 40)

    return model, accuracy


if __name__ == "__main__":
    evaluate_model()

