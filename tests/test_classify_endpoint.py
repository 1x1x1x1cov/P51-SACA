"""
Integration tests for the /classify endpoint in main.py

Updated 2026-09-15: main.py's active_classifier switched from
RuleBasedClassifier (Swahili keyword matching) to LogisticRegressionClassifier
(English, trained on saca_train.csv), per the team's 2026-09-11 decision
(see the project handoff doc's "TEAM AND SCOPE CHANGE" section) -- SVM
dropped, Random Forest cancelled, rule_based.py retired entirely from
the app, LR is the sole classifier. This file's assertions were written
against rule_based's behavior and needed rewriting to match, not
patching around:

- rule_based.py only ever reports symptoms it recognises from a fixed
  Swahili vocabulary (keywords.py) -- unrecognised input, in Swahili or
  any other language, always came back as symptoms=[]. LR has no such
  filter: `symptoms` is just symptom_text.split(), so it always reflects
  whatever was actually typed, recognised or not. Tests below assert
  against that, not against [].
- rule_based.py's CRITICAL_OVERRIDE_KEYWORDS gave a deterministic
  Swahili-keyword safety net independent of model confidence. LR has no
  equivalent -- that's a real, deliberate tradeoff the team accepted
  (see the handoff doc), not an oversight here. "CRITICAL input returns
  CRITICAL" below is tested against a real saca_test.csv row the trained
  model actually predicts CRITICAL on (verified directly, not assumed),
  not against a hardcoded keyword.
- Swahili input is not meaningfully classifiable by LR at all (it's
  untrained vocabulary) -- tests use English input, matching what LR
  was actually trained on.

Covers:
- Valid symptom input returns a correct classification
- Empty input is handled gracefully
- Gibberish/unrecognised input is handled gracefully (LOW, but with its
  actual tokens in `symptoms` -- see note above)
- DB writes actually happen after a classification request
"""

import pytest
import database
import main
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """
    Fresh isolated temp database per test, so tests don't pollute
    each other or the real saca.db.

    main.py imports save_session/get_all_sessions directly from
    database at import time, so those names in main's namespace also
    need patching, not just database.DB_PATH itself. Patching only
    the module attribute isn't enough because "from database import x"
    already bound x to the old module-level default at import time.
    """
    db_file = tmp_path / "test_saca.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database.init_db()

    return TestClient(main.app)


# A real saca_test.csv row (leak-free test set) that the trained LR
# model actually predicts CRITICAL on, verified directly (0.9874
# confidence) rather than assumed -- see module docstring for why this
# replaces the old hardcoded-Swahili-keyword approach.
REAL_CRITICAL_TEXT = (
    "skin_rash chills vomiting fatigue high_fever headache nausea "
    "loss_of_appetite pain_behind_the_eyes back_pain malaise muscle_pain "
    "red_spots_over_body"
)


class TestClassifyEndpointValidInput:
    def test_valid_symptom_text_returns_200(self, client):
        response = client.post("/classify", json={"symptom_text": "fever cough breathlessness"})
        assert response.status_code == 200

    def test_valid_symptom_text_returns_expected_shape(self, client):
        response = client.post("/classify", json={"symptom_text": "fever headache"})
        data = response.json()
        expected_keys = {
            "severity", "severity_sw", "symptoms", "reason", "disclaimer",
            "classifier", "confidence",
        }
        assert expected_keys.issubset(set(data.keys()))

    def test_high_confidence_critical_input_returns_critical(self, client):
        """See REAL_CRITICAL_TEXT above: a real test-set row the trained
        model predicts CRITICAL on with 0.9874 confidence, not a
        deterministic keyword rule -- LR has no keyword safety net
        (deliberate, see module docstring), so this only demonstrates the
        model getting a clear-cut real case right, not a guarantee."""
        response = client.post("/classify", json={"symptom_text": REAL_CRITICAL_TEXT})
        data = response.json()
        assert data["severity"] == "CRITICAL"

    def test_symptoms_returned_are_the_input_tokens(self, client):
        """Unlike rule_based.py, LR doesn't map input to a recognised
        symptom vocabulary -- `symptoms` is just the input, tokenised."""
        response = client.post("/classify", json={"symptom_text": "fever cough breathlessness"})
        data = response.json()
        assert data["symptoms"] == ["fever", "cough", "breathlessness"]


class TestClassifyEndpointEmptyInput:
    def test_empty_string_returns_200_not_error(self, client):
        """Empty input should be handled gracefully by the classifier,
        not crash the endpoint."""
        response = client.post("/classify", json={"symptom_text": ""})
        assert response.status_code == 200

    def test_empty_string_returns_low_severity(self, client):
        response = client.post("/classify", json={"symptom_text": ""})
        data = response.json()
        assert data["severity"] == "LOW"
        assert data["symptoms"] == []

    def test_whitespace_only_input_handled_gracefully(self, client):
        response = client.post("/classify", json={"symptom_text": "   "})
        assert response.status_code == 200
        assert response.json()["severity"] == "LOW"

    def test_missing_symptom_text_field_returns_422(self, client):
        """Pydantic validation should reject a request missing the
        required field, with a 422, not a 500 crash."""
        response = client.post("/classify", json={})
        assert response.status_code == 422


class TestClassifyEndpointGibberishInput:
    def test_gibberish_text_returns_200_not_error(self, client):
        response = client.post("/classify", json={"symptom_text": "asdkjfh qlwkejr zzzxxx"})
        assert response.status_code == 200

    def test_gibberish_text_returns_low_severity(self, client):
        """Verified directly: the trained model predicts LOW (0.9198
        confidence) on this input. `symptoms` is NOT expected to be []
        here -- see module docstring: unlike rule_based.py, LR reports
        whatever was typed, recognised or not, it doesn't filter to a
        known vocabulary."""
        response = client.post("/classify", json={"symptom_text": "random gibberish text here zzxxqq"})
        data = response.json()
        assert data["severity"] == "LOW"
        assert data["symptoms"] == ["random", "gibberish", "text", "here", "zzxxqq"]

    def test_unrecognised_text_handled_without_crashing(self, client):
        """Input the model wasn't trained on shouldn't crash the endpoint,
        whatever severity it happens to predict."""
        response = client.post("/classify", json={"symptom_text": "the patient has a headache"})
        assert response.status_code == 200


class TestClassifyEndpointDatabaseWrites:
    def test_classification_is_saved_to_database(self, client):
        client.post("/classify", json={"symptom_text": "ana homa"})
        response = client.get("/sessions")
        sessions = response.json()
        assert len(sessions) == 1
        assert sessions[0]["symptom_text"] == "ana homa"

    def test_multiple_classifications_all_saved(self, client):
        client.post("/classify", json={"symptom_text": "ana homa"})
        client.post("/classify", json={"symptom_text": "ana kikohozi"})
        client.post("/classify", json={"symptom_text": "ana degedege"})

        response = client.get("/sessions")
        sessions = response.json()
        assert len(sessions) == 3

    def test_saved_session_has_correct_severity(self, client):
        client.post("/classify", json={"symptom_text": REAL_CRITICAL_TEXT})
        response = client.get("/sessions")
        sessions = response.json()
        assert sessions[0]["severity"] == "CRITICAL"

    def test_new_sessions_are_unsynced_by_default(self, client):
        """Offline-first requirement: every new session should start
        as unsynced until an explicit sync process marks it synced."""
        client.post("/classify", json={"symptom_text": "ana homa"})
        response = client.get("/sessions")
        sessions = response.json()
        assert sessions[0]["synced"] is False
        assert sessions[0]["synced_at"] is None

    def test_sessions_returned_most_recent_first(self, client):
        client.post("/classify", json={"symptom_text": "first request"})
        client.post("/classify", json={"symptom_text": "second request"})

        response = client.get("/sessions")
        sessions = response.json()
        assert sessions[0]["symptom_text"] == "second request"
        assert sessions[1]["symptom_text"] == "first request"