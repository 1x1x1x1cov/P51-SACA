"""
Locks the triage classifier's measured behaviour on the held-out v2 test set, through the SAME path the app uses
(SACAPipeline without the online extractor). If a change moves these numbers, the test fails and the change must be
looked at, not waved through. Numbers match dataset_v2/eval_report_v2.txt (checked 2026-10-29).
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from classifier.pipeline import SACAPipeline  # noqa: E402

RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@pytest.fixture(scope="module")
def pipeline():
    p = SACAPipeline()
    p.classifier.train()
    return p


@pytest.fixture(scope="module")
def test_rows():
    df = pd.read_csv(os.path.join(ROOT, "dataset_v2", "saca_v2_test.csv")).dropna(subset=["symptom_text", "severity"])
    return [(t.lower().strip(), s.upper().strip()) for t, s in zip(df.symptom_text, df.severity)]


def test_app_path_metrics_on_held_out_test_set(pipeline, test_rows):
    preds = [pipeline.classify(t)["severity"] for t, _ in test_rows]
    truth = [s for _, s in test_rows]
    n = len(truth)
    accuracy = sum(p == s for p, s in zip(preds, truth)) / n
    critical_below_high = sum(1 for p, s in zip(preds, truth) if s == "CRITICAL" and RANK[p] < 2)
    dangerous = sum(1 for p, s in zip(preds, truth) if RANK[s] >= 2 and RANK[p] <= 1)
    under = sum(1 for p, s in zip(preds, truth) if RANK[p] < RANK[s]) / n
    assert n == 1655
    assert accuracy >= 0.905
    assert critical_below_high == 0
    assert dangerous <= 58
    assert under <= 0.0405


def test_confidence_is_not_saturated(pipeline, test_rows):
    """Most answers are NOT given at ~100 %: values near 100 % come from several strong signs together."""
    clf = pipeline.classifier
    proba = clf.pipeline.predict_proba([t for t, _ in test_rows])
    conf = proba.max(axis=1)
    pred = clf.label_encoder.inverse_transform(proba.argmax(axis=1))
    correct = pred == np.array([s for _, s in test_rows])
    assert (conf >= 0.99).mean() < 0.05
    assert 0.7 < conf.mean() < 0.9
    # calibration: expected calibration error over 10 bins stays small
    ece = 0.0
    edges = np.linspace(0, 1, 11)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += abs(conf[m].mean() - correct[m].mean()) * m.mean()
    assert ece < 0.12


def test_more_danger_signs_raise_confidence_never_lower_the_level(pipeline):
    one = pipeline.classify("breathlessness chest_pain")
    many = pipeline.classify("breathlessness chest_pain convulsions altered_sensorium")
    assert one["severity"] == many["severity"] == "CRITICAL"
    assert many["confidence"] > one["confidence"]
