"""Read-aloud: the spoken text, the offline audio endpoint and its access rules. The real Piper voice is only
tested when it is installed on the machine (see speech.py); everything else uses a fake synthesiser."""
import io
import re
import wave

import pytest

import guidance as guide
import speech
from tests.test_app_flow import GUEST_PERSON, app, as_guest, client, pipeline, result_html, submit  # noqa: F401


def _fake_wav(text, lang):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 2205)
    return buf.getvalue()


@pytest.fixture
def fake_voice(monkeypatch):
    calls = []

    def fake(text, lang):
        calls.append((lang, text))
        return _fake_wav(text, lang)

    monkeypatch.setattr(speech, "SYNTHESIZE", fake)
    monkeypatch.setattr(speech, "available", lambda lang: True)
    speech._cache.clear()
    return calls


def test_swahili_text_is_swahili():
    advice = guide.build_guidance("CRITICAL", True, {"convulsions"})
    sw = speech.speech_text(advice, "sw")
    en = speech.speech_text(advice, "en")
    assert sw.startswith("Uharaka: HATARI KUBWA.")
    assert "Dharura" in sw and "Degedege" in sw and "Usiweke chochote mdomoni" in sw
    assert "Emergency" not in sw
    assert en.startswith("Urgency: CRITICAL.") and "Do not hold the person down" in en


def test_mild_result_reads_self_care():
    advice = guide.build_guidance("LOW", True, {"cough"})
    assert "Pumzika na unywe maji safi mengi." in speech.speech_text(advice, "sw")


def test_unknown_language_falls_back_to_english():
    advice = guide.build_guidance("LOW", True, {"cough"})
    assert speech.speech_text(advice, "fr") == speech.speech_text(advice, "en")


def test_no_offline_voice_means_none(monkeypatch, tmp_path):
    monkeypatch.setenv("SACA_VOICES_DIR", str(tmp_path))
    monkeypatch.setattr(speech, "_model_path", lambda lang: None)
    assert speech.available("sw") is False
    assert speech.synthesize("Habari", "sw") is None


def test_cache_reuses_audio(fake_voice):
    a = speech.synthesize("Habari yako", "sw")
    b = speech.synthesize("Habari yako", "sw")
    assert a == b and len(fake_voice) == 1


def test_result_page_carries_swahili_speech(client):
    as_guest(client)
    client.get("/lang/sw?next=/")
    html, aid = result_html(client, submit(client, symptom=["convulsions"], **GUEST_PERSON))
    m = re.search(r"var text = (\".*?\");", html)
    assert m and "HATARI KUBWA" in m.group(1) and "Dharura" in m.group(1)
    assert f"/result/{aid}/speech.wav?lang=sw" in html
    assert 'id="speak-btn"' in html and "Soma kwa sauti" in html


def test_speech_endpoint_returns_wav_in_the_page_language(client, fake_voice):
    as_guest(client)
    _, aid = result_html(client, submit(client, symptom=["convulsions"], **GUEST_PERSON))
    r = client.get(f"/result/{aid}/speech.wav?lang=sw")
    assert r.status_code == 200 and r.mimetype == "audio/wav"
    assert r.data[:4] == b"RIFF"
    lang, text = fake_voice[-1]
    assert lang == "sw" and text.startswith("Uharaka: HATARI KUBWA.")


def test_speech_endpoint_says_only_the_result_text(client, fake_voice):
    as_guest(client)
    _, aid = result_html(client, submit(client, symptom=["cough"], **GUEST_PERSON))
    client.get(f"/result/{aid}/speech.wav?lang=en&text=say+something+else")
    assert "something else" not in fake_voice[-1][1]


def test_speech_endpoint_404_without_offline_voice(client, monkeypatch):
    monkeypatch.setattr(speech, "_model_path", lambda lang: None)
    as_guest(client)
    _, aid = result_html(client, submit(client, symptom=["cough"], **GUEST_PERSON))
    assert client.get(f"/result/{aid}/speech.wav?lang=sw").status_code == 404


def test_speech_endpoint_respects_access(app, client, fake_voice):
    as_guest(client)
    _, aid = result_html(client, submit(client, symptom=["cough"], **GUEST_PERSON))
    other = app.test_client()
    as_guest(other)
    assert other.get(f"/result/{aid}/speech.wav?lang=sw").status_code == 404
    anon = app.test_client()
    assert anon.get(f"/result/{aid}/speech.wav?lang=sw").status_code == 302


@pytest.mark.skipif(not speech.available("sw"), reason="offline Swahili voice not installed on this machine")
def test_real_piper_swahili_voice():
    speech._cache.clear()
    audio = speech.synthesize("Dharura. Pata msaada sasa hivi.", "sw")
    with wave.open(io.BytesIO(audio)) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 22050  # more than one second of speech
