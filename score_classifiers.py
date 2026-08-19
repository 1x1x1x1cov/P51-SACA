"""
SACA - Comparison scoring script

Runs every available classifier (any BaseClassifier subclass found in
classifier/) against the shared saca_test.csv, computes accuracy,
precision, recall, and F1 per classifier, and writes the results to
comparison_results.json for the dashboard (comparison_dashboard.html)
to read.

This is designed to work with however many classifiers currently
exist - right now that's just rule-based, but it will automatically
pick up random_forest.py, svm.py, logistic_regression.py, and
hybrid.py once those files exist, with no changes needed here.

Run from the repo root:
    python3 score_classifiers.py
"""

import json
import importlib
import inspect
import pkgutil
import pandas as pd
from datetime import datetime
from sklearn.metrics import precision_recall_fscore_support, accuracy_score

import classifier as classifier_pkg
from classifier.base import BaseClassifier

TEST_FILE = "saca_test.csv"
OUTPUT_FILE = "comparison_results.json"


def discover_classifiers():
    """
    Find every concrete BaseClassifier subclass in the classifier/
    package automatically, so this script never needs manual editing
    as new classifier files are added.
    """
    found = []
    for _, module_name, _ in pkgutil.iter_modules(classifier_pkg.__path__):
        if module_name == "base":
            continue
        module = importlib.import_module(f"classifier.{module_name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseClassifier)
                and obj is not BaseClassifier
                and obj.__module__ == module.__name__
            ):
                found.append(obj)
    return found


def score_classifier(cls, test_df):
    """
    Run one classifier against every row in the test set and compute
    standard classification metrics. Returns None (with an error
    logged) if the classifier crashes, rather than letting one broken
    classifier take down the whole scoring run.
    """
    instance = cls()
    y_true = []
    y_pred = []
    errors = 0

    for _, row in test_df.iterrows():
        try:
            result = instance.classify(row["symptom_text"])
            y_true.append(row["severity"])
            y_pred.append(result["severity"])
        except Exception as e:
            errors += 1

    if not y_true:
        return {
            "name": instance.name,
            "status": "failed",
            "error": "Classifier raised an error on every test row",
        }

    accuracy = accuracy_score(y_true, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )

    # Per-class breakdown, useful for spotting where a classifier is
    # weak (e.g. good on MEDIUM but bad on CRITICAL, which matters a
    # lot more for a clinical triage tool than overall accuracy alone)
    labels = sorted(set(y_true) | set(y_pred))
    per_class_precision, per_class_recall, per_class_f1, per_class_support = (
        precision_recall_fscore_support(
            y_true, y_pred, labels=labels, zero_division=0
        )
    )
    per_class = {
        label: {
            "precision": round(float(p), 4),
            "recall": round(float(r), 4),
            "f1": round(float(f), 4),
            "support": int(s),
        }
        for label, p, r, f, s in zip(
            labels, per_class_precision, per_class_recall, per_class_f1, per_class_support
        )
    }

    return {
        "name": instance.name,
        "status": "ok",
        "accuracy": round(float(accuracy), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "rows_tested": len(y_true),
        "rows_errored": errors,
        "per_class": per_class,
    }


def main():
    test_df = pd.read_csv(TEST_FILE)
    print(f"Loaded {len(test_df)} test rows from {TEST_FILE}")

    classifiers = discover_classifiers()
    print(f"Found {len(classifiers)} classifier(s): {[c.__name__ for c in classifiers]}")

    results = []
    for cls in classifiers:
        print(f"Scoring {cls.__name__}...")
        result = score_classifier(cls, test_df)
        results.append(result)
        if result["status"] == "ok":
            print(f"  accuracy={result['accuracy']} f1={result['f1']}")
        else:
            print(f"  FAILED: {result.get('error')}")

    output = {
        "generated_at": datetime.now().isoformat(),
        "test_rows": len(test_df),
        "results": results,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote results to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
