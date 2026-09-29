import os
import csv

os.environ["GROQ_API_KEY"] = "test-key"

import main
from classifier.logistic_regression import LogisticRegressionClassifier


def test_active_classifier_is_logistic_regression():
    assert isinstance(main.active_classifier, LogisticRegressionClassifier)


def test_no_symptom_text_overlap_between_train_and_test():
    with open("saca_train.csv", newline="", encoding="utf-8") as train_file:
        train_rows = csv.DictReader(train_file)
        train_symptoms = {
            row["symptom_text"].strip()
            for row in train_rows
        }

    with open("saca_test.csv", newline="", encoding="utf-8") as test_file:
        test_rows = csv.DictReader(test_file)
        test_symptoms = {
            row["symptom_text"].strip()
            for row in test_rows
        }

    overlap = train_symptoms & test_symptoms

    assert overlap == set(), (
        f"Found {len(overlap)} overlapping symptom_text values: "
        f"{list(overlap)[:10]}"
    )
