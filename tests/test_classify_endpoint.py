"""
Integration tests for the /classify endpoint in main.py

Covers:
- Valid symptom input returns a correct classification
- Empty input is handled gracefully
- Gibberish/unrecognised input is handled gracefully
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


class TestClassifyEndpointValidInput:
    def test_valid_symptom_text_returns_200(self, client):
        response = client.post("/classify", json={"symptom_text": "mgonjwa ana homa na degedege"})
        assert response.status_code == 200

    def test_valid_symptom_text_returns_expected_shape(self, client):
        response = client.post("/classify", json={"symptom_text": "ana homa"})
        data = response.json()
        expected_keys = {"severity", "severity_sw", "symptoms", "reason", "disclaimer", "classifier"}
        assert expected_keys.issubset(set(data.keys()))

    def test_critical_override_keyword_returns_critical(self, client):
        """Convulsions is a CRITICAL_OVERRIDE_KEYWORDS entry, should
        always return CRITICAL regardless of what else is in the text."""
        response = client.post("/classify", json={"symptom_text": "ana degedege"})
        data = response.json()
        assert data["severity"] == "CRITICAL"

    def test_symptoms_detected_are_returned(self, client):
        response = client.post("/classify", json={"symptom_text": "ana homa na kikohozi"})
        data = response.json()
        assert "fever" in data["symptoms"]
        assert "cough" in data["symptoms"]


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

    def test_gibberish_text_returns_low_severity_no_symptoms(self, client):
        response = client.post("/classify", json={"symptom_text": "random gibberish text here"})
        data = response.json()
        assert data["severity"] == "LOW"
        assert data["symptoms"] == []

    def test_non_swahili_text_handled_without_crashing(self, client):
        """English or other unrecognised language input shouldn't crash,
        even though the classifier is only built for Swahili keywords."""
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
        client.post("/classify", json={"symptom_text": "ana degedege"})
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