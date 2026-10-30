"""
Read-aloud for the SACA result screen, including Swahili.

Two ways to speak, tried in this order by the page (templates/result.html):
  1. The browser's own voice for the language (Web Speech API). English works in every browser. Swahili works in
     Microsoft Edge, which offers "Microsoft Daudi/Rehema Online (Natural) - Swahili (Tanzania)" and Kenya voices,
     but only with internet. Chrome on Windows has no Swahili voice.
  2. An OFFLINE voice on this computer, made here with Piper (piper-tts, MIT licence) and its Swahili voice
     sw_CD-lanfrica-medium (63 MB, trained on the Lanfrica Kiswahili TTS dataset; Congo Swahili accent).
     Install once, with internet:
         python -m pip install piper-tts
         python -m piper.download_voices sw_CD-lanfrica-medium --download-dir "%LOCALAPPDATA%\\SACA\\voices"
     After that, Swahili read-aloud works with no internet in any browser.

The audio is made from the result's own advice text on the server. The endpoint never speaks text sent by the
browser, so it cannot be used to make the app say something else.
"""
import io
import os
import threading
import wave
from collections import OrderedDict

import saca_store as store

VOICES = {
    "sw": "sw_CD-lanfrica-medium",
    "en": "en_US-lessac-medium",   # optional; English normally uses the browser's voice
}
LENGTH_SCALE = {"sw": 1.1, "en": 1.0}   # a little slower than default, easier to follow
MAX_CHARS = 1500
CACHE_SIZE = 40

_lock = threading.Lock()
_voices = {}
_cache = OrderedDict()


def voices_dir():
    return os.environ.get("SACA_VOICES_DIR") or os.path.join(store.data_dir(), "voices")


def _model_path(lang):
    name = VOICES.get(lang)
    if not name:
        return None
    for folder in (voices_dir(), os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")):
        path = os.path.join(folder, name + ".onnx")
        if os.path.exists(path) and os.path.exists(path + ".json"):
            return path
    return None


def engine_installed():
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def available(lang):
    """True when this computer can make speech for lang without internet."""
    return _model_path(lang) is not None and engine_installed()


def _load(lang):
    if lang not in _voices:
        from piper import PiperVoice
        _voices[lang] = PiperVoice.load(_model_path(lang))
    return _voices[lang]


def _synthesize_piper(text, lang):
    from piper import SynthesisConfig
    voice = _load(lang)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=LENGTH_SCALE.get(lang, 1.0)))
    return buf.getvalue()


# Replaced in tests, so the endpoint can be tested without the 63 MB voice.
SYNTHESIZE = _synthesize_piper


def synthesize(text, lang):
    """WAV bytes for text, or None when no offline voice is installed for lang."""
    text = (text or "").strip()[:MAX_CHARS]
    if not text or (SYNTHESIZE is _synthesize_piper and not available(lang)):
        return None
    key = (lang, text)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
        audio = SYNTHESIZE(text, lang)
        _cache[key] = audio
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
        return audio


def _say(pair, lang):
    text = (pair or {}).get(lang) or (pair or {}).get("en") or ""
    return text.strip()


def _end(sentence):
    return sentence if sentence.endswith((".", "!", "?", ":")) else sentence + "."


def speech_text(advice, lang):
    """
    What read-aloud says for one result: the level, what to do and how soon, then the most important first-aid
    steps (serious results) or self-care steps (mild results). Plain sentences, short enough to listen to.
    """
    lang = lang if lang in ("en", "sw") else "en"
    label = {"en": "Urgency", "sw": "Uharaka"}[lang]
    parts = [f"{label}: {_say(advice['level'], lang)}.", _end(_say(advice["headline"], lang)),
             _end(_say(advice["timeframe"], lang))]
    topics = advice.get("topics") or []
    if topics:
        topic = topics[0]
        parts.append(_end(_say(topic["title"], lang)))
        parts.extend(_end(_say(step, lang)) for step in topic["do"][:3])
        parts.extend(_end(_say(step, lang)) for step in (topic.get("dont") or [])[:2])
    else:
        steps = (advice.get("self_care") or {}).get("steps") or []
        parts.extend(_end(_say(step, lang)) for step in steps[:2])
    return " ".join(p for p in parts if p and p != ".")
