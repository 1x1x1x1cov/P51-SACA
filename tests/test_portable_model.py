"""
The Android app has no scikit-learn, so it loads the trained model from dataset_v2/saca_v2_model.json
(classifier/portable_model.py). These tests prove the portable copy gives the same answers as scikit-learn.
If one fails after retraining, regenerate the file:  python -m classifier.portable_model
"""
import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

from classifier import portable_model
from classifier.logistic_regression import LogisticRegressionClassifier

ROOT = Path(__file__).resolve().parent.parent
TEST_CSV = ROOT / "dataset_v2" / "saca_v2_test.csv"
PHRASES = ["ana homa na degedege", "kikohozi na mafua", "nina maumivu ya meno", "asdfgh", "chest_pain breathlessness",
           "headache fatigue nausea", "kukohoa damu", "fever and chills", "kuungua wakati wa kukojoa", "no fever",
           "Fièvre élevée", "high_fever chills", "kifua kinauma", ""]


@pytest.fixture(scope="module")
def both():
    sk = LogisticRegressionClassifier()
    sk.train()
    port = LogisticRegressionClassifier()
    port.pipeline, port.label_encoder = portable_model.load()
    port.is_trained = True
    return sk, port


def test_model_file_matches_the_current_training_data(both):
    sk, port = both
    assert port.label_encoder.classes_ == [str(c) for c in sk.label_encoder.classes_]
    assert port.pipeline.named_steps["vectorizer"].vocabulary_ == {
        k: int(v) for k, v in sk.pipeline.named_steps["vectorizer"].vocabulary_.items()}


def test_same_probabilities_on_every_held_out_row(both):
    sk, port = both
    with open(TEST_CSV, newline="", encoding="utf-8") as f:
        texts = [r["symptom_text"].lower().strip() for r in csv.DictReader(f)]
    assert len(texts) == 1655
    a = sk.pipeline.predict_proba(texts)
    b = port.pipeline.predict_proba(texts)
    worst = max(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra, rb))
    assert worst < 1e-9
    assert list(sk.pipeline.predict(texts)) == port.pipeline.predict(texts)


def test_same_analyzer_tokens(both):
    sk, port = both
    for p in PHRASES:
        assert sk.pipeline.named_steps["vectorizer"].build_analyzer()(p) == \
            port.pipeline.named_steps["vectorizer"].build_analyzer()(p)


@pytest.mark.parametrize("text", PHRASES)
def test_same_full_classification(both, text):
    sk, port = both
    assert sk.classify(text) == port.classify(text)


def test_classifier_works_with_no_numpy_pandas_or_sklearn():
    """Run the classifier in a fresh Python where those imports fail, as on the phone."""
    code = (
        "import sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('numpy', 'pandas', 'sklearn', 'scipy'):\n"
        "            raise ImportError('blocked: ' + name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "from classifier.logistic_regression import LogisticRegressionClassifier, HAVE_SKLEARN\n"
        "assert not HAVE_SKLEARN\n"
        "c = LogisticRegressionClassifier(); c.train()\n"
        "r = c.classify('ana homa na degedege')\n"
        "assert r['severity'] == 'CRITICAL', r\n"
        "print('ok')\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": str(ROOT)})
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout
