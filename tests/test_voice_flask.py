"""
Voice input on the Flask dashboard (voice_flask.py). The speech-to-text service is always faked.
"""
import io

import pytest
from flask import Flask

import voice_core
from voice_flask import voice_bp

AUDIO = b"\x1aE\xdf\xa3" + b"\x00" * 2000


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(voice_bp)
    return app.test_client()


def post(client, data=AUDIO, ctype="audio/webm", language="auto", name="voice.webm"):
    return client.post("/transcribe", data={"audio": (io.BytesIO(data), name, ctype), "language": language},
                       content_type="multipart/form-data")


def test_returns_transcript_with_language_and_extension(client, monkeypatch):
    seen = {}

    def fake(audio, filename, language):
        seen.update(filename=filename, language=language)
        return "I have a high fever"

    monkeypatch.setattr(voice_core, "transcribe_audio", fake)
    r = post(client, language="en")
    assert r.status_code == 200 and r.get_json() == {"text": "I have a high fever"}
    assert seen == {"filename": "voice.webm", "language": "en"}


def test_auto_language_sends_no_hint_and_codec_suffix_ok(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(voice_core, "transcribe_audio", lambda a, f, language: seen.setdefault("l", language) or "x")
    assert post(client, ctype="audio/webm;codecs=opus").status_code == 200
    assert seen["l"] is None


@pytest.mark.parametrize("kwargs,status", [
    (dict(language="fr"), 422),
    (dict(ctype="text/html", name="x.html"), 415),
    (dict(data=b""), 400),
    (dict(data=b"abc"), 400),
])
def test_rejections(client, kwargs, status):
    assert post(client, **kwargs).status_code == status


def test_oversized_clip_is_413(client, monkeypatch):
    monkeypatch.setattr(voice_core, "MAX_AUDIO_BYTES", 5000)
    assert post(client, data=b"\x00" * 6000).status_code == 413


def test_missing_file_is_422(client):
    assert client.post("/transcribe", data={"language": "en"}).status_code == 422


def test_stt_failure_is_friendly_503_and_leaks_nothing(client, monkeypatch):
    def boom(a, f, l):
        raise TimeoutError("secret gsk_123")
    monkeypatch.setattr(voice_core, "transcribe_audio", boom)
    r = post(client)
    assert r.status_code == 503 and "type your symptoms" in r.get_json()["detail"]
    assert "gsk_123" not in r.get_data(as_text=True)


def test_no_api_key_fails_politely(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(voice_core, "_client", None)
    assert post(client).status_code == 503


def test_serves_the_button_script(client):
    r = client.get("/voice.js")
    assert r.status_code == 200 and "javascript" in r.content_type
    assert b"/transcribe" in r.data