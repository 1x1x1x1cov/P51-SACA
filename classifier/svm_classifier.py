
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

    # ---------------------------------------------------------
    # Swahili -> English symptom mapping
    # ---------------------------------------------------------
    #
    # The existing SVM was trained using English symptom terms.
    # These mappings allow Swahili input to be converted into
    # the English terms understood by the existing SVM model.
    #
    SWAHILI_SYMPTOMS = {
        "kutapika": "vomiting",
        "homa kali": "high_fever",
        "homa": "fever",
        "maumivu ya tumbo": "abdominal_pain",
        "maumivu ya viungo": "joint_pain",
        "uchovu": "fatigue",
        "kichefuchefu": "nausea",
        "ngozi ya manjano": "yellowish_skin",
        "mkojo mweusi": "dark_urine",
        "kukosa hamu ya kula": "loss_of_appetite",
        "macho ya manjano": "yellowing_of_eyes",
        "kushindwa kwa ini": "acute_liver_failure",
        "kukosa fahamu": "coma",
        "kutokwa na damu tumboni": "stomach_bleeding",

        # Additional common symptoms
        "maumivu ya kichwa": "headache",
        "kichwa kuuma": "headache",
        "kuhara": "diarrhoea",
        "kikohozi": "cough",
        "kupumua kwa shida": "difficulty_breathing",
        "maumivu ya kifua": "chest_pain",
        "kizunguzungu": "dizziness",
        "baridi": "chills",
        "jasho": "sweating",
        "maumivu": "pain",
        "udhaifu": "weakness",
        "uvimbe": "swelling",
        "homa": "fever",
        "kutetemeka": "shivering",
        "koo kuuma": "sore_throat",
        "maumivu ya misuli": "muscle_pain",
    }

    def __init__(self):
        """
        Initialise the SVM classifier.

        The model is trained when the classifier is created.
        """

        # Find the project root.
        #
        # svm_classifier.py is expected to be inside:
        #
        #     project/
        #         classifier/
        #             svm_classifier.py
        #
        self.project_root = Path(__file__).resolve().parent.parent

        self.train_path = self.project_root / "saca_train.csv"

        if not self.train_path.exists():
            raise FileNotFoundError(
                f"Training dataset not found: {self.train_path}"
            )

        # -----------------------------------------------------
        # Load training data
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Build SVM pipeline
        # -----------------------------------------------------
        #
        # TF-IDF converts the symptom text into numerical
        # features.
        #
        # LinearSVC then uses those features to classify
        # the severity.
        #

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

        # -----------------------------------------------------
        # Parameters to fine-tune
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Stratified cross-validation
        # -----------------------------------------------------

        cv = StratifiedKFold(
            n_splits=5,
            shuffle=True,
            random_state=42
        )

        # -----------------------------------------------------
        # Grid search
        # -----------------------------------------------------

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

        self.classes = list(
            self.model.named_steps["svm"].classes_
        )

    # ---------------------------------------------------------
    # Swahili translation / symptom mapping
    # ---------------------------------------------------------

    def translate_swahili_symptoms(self, symptom_text: str) -> str:
        """
        Convert recognised Swahili symptoms into the English
        symptom terms used by the existing SVM training dataset.

        This is a symptom mapping system rather than a general
        machine translation system.
        """

        text = symptom_text.lower().strip()

        # Replace longer phrases first.
        #
        # This is important because phrases such as:
        #
        #     "homa kali"
        #
        # should become:
        #
        #     "high_fever"
        #
        # before the individual word "homa" becomes "fever".
        #
        for swahili, english in sorted(
            self.SWAHILI_SYMPTOMS.items(),
            key=lambda item: len(item[0]),
            reverse=True
        ):
            text = text.replace(
                swahili,
                english
            )

        return text

    # ---------------------------------------------------------
    # Classification
    # ---------------------------------------------------------

    def classify(self, symptom_text: str) -> dict:
        """
        Classify a patient's symptoms.

        The method accepts English or recognised Swahili
        symptoms.

        Swahili symptoms are converted into the English
        symptom terms used by the trained SVM.

        Args:
            symptom_text:
                Patient symptoms as text.

        Returns:
            Result dictionary produced by
            BaseClassifier.build_result().
        """

        # -----------------------------------------------------
        # Handle empty input
        # -----------------------------------------------------

        if not symptom_text or not symptom_text.strip():
            return self.build_result(
                "LOW",
                [],
                "Hakuna dalili zilizoingizwa — tafadhali ingiza dalili za mgonjwa."
            )

        # -----------------------------------------------------
        # Convert input to string
        # -----------------------------------------------------

        symptom_text = str(symptom_text).strip()

        # -----------------------------------------------------
        # Convert recognised Swahili symptoms to English
        # -----------------------------------------------------

        translated_text = self.translate_swahili_symptoms(
            symptom_text
        )

        # Display the conversion in the terminal.
        #
        # Example:
        #
        # Original input:
        # kutapika homa kali maumivu ya tumbo
        #
        # SVM input:
        # vomiting high_fever abdominal_pain
        #
        print(
            f"Original input: {symptom_text}"
        )

        print(
            f"SVM input: {translated_text}"
        )

        # -----------------------------------------------------
        # Predict severity
        # -----------------------------------------------------

        prediction = self.model.predict(
            [translated_text]
        )[0]

        # -----------------------------------------------------
        # Convert original input into a list of symptoms
        # -----------------------------------------------------

        symptoms = symptom_text.split()

        # -----------------------------------------------------
        # Swahili explanations
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Return result
        # -----------------------------------------------------

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

    # ---------------------------------------------------------
    # Load datasets
    # ---------------------------------------------------------

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

    grid_search.fit(
        X_train,
        y_train
    )

    model = grid_search.best_estimator_

    # ---------------------------------------------------------
    # Display best configuration
    # ---------------------------------------------------------

    print("=" * 60)
    print("BEST SVM CONFIGURATION")
    print("=" * 60)

    print("Best parameters:")

    for parameter, value in grid_search.best_params_.items():
        print(
            f"  {parameter}: {value}"
        )

    print()

    print(
        f"Best cross-validation macro F1: "
        f"{grid_search.best_score_:.4f}"
    )

    # ---------------------------------------------------------
    # Test set
    # ---------------------------------------------------------

    predictions = model.predict(
        X_test
    )

    accuracy = accuracy_score(
        y_test,
        predictions
    )

    print()
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    print(
        f"Accuracy: {accuracy:.4f}"
    )

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

    plt.figure(
        figsize=(8, 6)
    )

    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        xticklabels=labels,
        yticklabels=labels
    )

    plt.xlabel(
        "Predicted"
    )

    plt.ylabel(
        "Actual"
    )

    plt.title(
        "SVM Severity Classification"
    )

    plt.tight_layout()

    plt.show()

    # ---------------------------------------------------------
    # Sample predictions
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("SAMPLE PREDICTIONS")
    print("=" * 60)

    number_of_samples = min(
        10,
        len(X_test)
    )

    for i in range(number_of_samples):

        print()

        print(
            f"Symptoms: {X_test.iloc[i]}"
        )

        print(
            f"Actual: {y_test.iloc[i]}"
        )

        print(
            f"Predicted: {predictions[i]}"
        )

        print(
            "-" * 40
        )

    return model, accuracy


if __name__ == "__main__":
    evaluate_model()

