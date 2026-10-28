"""
Voice input: POST /transcribe. The speech-to-text service is always faked here --
the real Groq API is never called.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import voice_api
import voice_core

AUDIO = b"\x1aE\xdf\xa3" + b"\x00" * 2000     # > MIN_AUDIO_BYTES; contents don't matter (STT is faked)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(voice_api.router)
    return TestClient(app)


def post(client, data=AUDIO, ctype="audio/webm", language="auto", name="voice.webm"):
    return client.post("/transcribe", files={"audio": (name, data, ctype)}, data={"language": language})


def test_returns_transcript_and_passes_language_and_extension(client, monkeypatch):
    seen = {}

    def fake(audio, filename, language):
        seen.update(filename=filename, language=language, size=len(audio))
        return "nina homa na maumivu ya kichwa"

    monkeypatch.setattr(voice_core, "transcribe_audio", fake)
    r = post(client, language="sw")
    assert r.status_code == 200 and r.json() == {"text": "nina homa na maumivu ya kichwa"}
    assert seen == {"filename": "voice.webm", "language": "sw", "size": len(AUDIO)}


def test_auto_language_sends_no_language_hint(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(voice_core, "transcribe_audio", lambda a, f, language: seen.setdefault("lang", language) or "x")
    post(client, language="auto")
    assert seen["lang"] is None


def test_codec_suffix_in_content_type_is_accepted(client, monkeypatch):
    monkeypatch.setattr(voice_core, "transcribe_audio", lambda a, f, l: "ok")
    assert post(client, ctype="audio/webm;codecs=opus").status_code == 200
    assert post(client, ctype="audio/mp4", name="voice.mp4").status_code == 200


def test_rejects_bad_language(client):
    assert post(client, language="fr").status_code == 422


def test_rejects_non_audio(client):
    assert post(client, ctype="text/html", name="x.html").status_code == 415


def test_rejects_empty_or_tiny_clip(client):
    assert post(client, data=b"").status_code == 400
    assert post(client, data=b"abc").status_code == 400


def test_rejects_oversized_clip(client, monkeypatch):
    monkeypatch.setattr(voice_core, "MAX_AUDIO_BYTES", 5000)
    assert post(client, data=b"\x00" * 6000).status_code == 413


def test_missing_file_is_422(client):
    assert client.post("/transcribe", data={"language": "en"}).status_code == 422


def test_stt_failure_gives_friendly_503_and_leaks_nothing(client, monkeypatch):
    def boom(a, f, l):
        raise TimeoutError("secret internal detail gsk_123")
    monkeypatch.setattr(voice_core, "transcribe_audio", boom)
    r = post(client)
    assert r.status_code == 503
    assert "type your symptoms" in r.json()["detail"]
    assert "gsk_123" not in r.text


def test_works_without_api_key_until_used(client, monkeypatch):
    # no key: the app must still import/start, and /transcribe fails politely
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(voice_core, "_client", None)
    assert post(client).status_code == 503


def test_empty_transcript_returns_empty_text(client, monkeypatch):
    monkeypatch.setattr(voice_core, "transcribe_audio", lambda a, f, l: "")
    assert post(client).json() == {"text": ""}


def test_main_app_serves_the_button_script_and_route():
    import main
    c = TestClient(main.app)
    js = c.get("/voice.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert "/transcribe" in js.text
    # /transcribe is registered on the real app: a tiny clip is a 400 ("no audio"), not a 404
    r = c.post("/transcribe", files={"audio": ("v.webm", b"x", "audio/webm")}, data={"language": "en"})
    assert r.status_code == 400