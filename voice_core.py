# voice_core.py
"""
Voice input for SACA -- the part that does not depend on a web framework.

Speech in, TEXT out. The two web layers (voice_flask.py for the Flask dashboard,
voice_api.py for the FastAPI app) are thin wrappers around handle_audio().

PRIVACY: the audio is health information. It is held in memory, sent to the
speech-to-text service, and discarded. It is never written to disk or logged.
With the default (hosted Whisper on Groq) the audio leaves the device -- say so in
your privacy notes. To run fully offline later, replace transcribe_audio() with a
local engine (e.g. faster-whisper); nothing else needs to change.

The model defaults to whisper-large-v3, which Groq's docs recommend when accuracy
and multilingual support matter. Override with the SACA_STT_MODEL environment variable.
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("saca.voice")

MODEL = os.environ.get("SACA_STT_MODEL", "whisper-large-v3")
TIMEOUT_SECONDS = 30.0
MAX_AUDIO_BYTES = 5 * 1024 * 1024   # ~60 s of browser audio is well under 1 MB
MIN_AUDIO_BYTES = 1000              # smaller than this is a click, not speech
LANGUAGES = {"en": "en", "sw": "sw", "auto": None}   # Whisper's auto-detect is unreliable for Swahili

# file extension Groq needs to recognise the format
_EXT_BY_TYPE = {
    "webm": "webm", "ogg": "ogg", "mp4": "mp4", "m4a": "m4a",
    "wav": "wav", "x-wav": "wav", "wave": "wav", "mpeg": "mp3", "mp3": "mp3", "flac": "flac",
}

_client = None


class VoiceError(Exception):
    """A problem to report to the user: carries an HTTP status and a friendly message."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def asset_path(relative_path: str) -> str:
    """Path to a bundled file; works from source and inside a PyInstaller .exe."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def _get_client():
    """Created on first use, so the app still starts when GROQ_API_KEY is not set."""
    global _client
    if _client is None:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set")
        from groq import Groq
        _client = Groq(api_key=key, timeout=TIMEOUT_SECONDS)
    return _client


def transcribe_audio(audio: bytes, filename: str, language) -> str:
    """Audio bytes -> text. This is the one function to swap for an offline engine."""
    kwargs = dict(file=(filename, audio), model=MODEL, response_format="text", temperature=0)
    if language:
        kwargs["language"] = language
    resp = _get_client().audio.transcriptions.create(**kwargs)
    text = resp if isinstance(resp, str) else getattr(resp, "text", "")
    return (text or "").strip()


def _extension(content_type, filename) -> str:
    """Work out the file extension, or raise 415 if this is not audio we accept."""
    ctype = (content_type or "").split(";")[0].strip().lower()
    subtype = ctype.split("/")[-1]
    if ctype.startswith("audio/") or ctype in ("video/webm", "video/mp4", "application/ogg"):
        if subtype in _EXT_BY_TYPE:
            return _EXT_BY_TYPE[subtype]
    name = (filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext in set(_EXT_BY_TYPE.values()) and ctype in ("", "application/octet-stream"):
        return ext
    raise VoiceError(415, "Unsupported audio format.")


def handle_audio(data: bytes, content_type, filename, language: str) -> str:
    """Validate an uploaded clip and return its transcript. Raises VoiceError."""
    if language not in LANGUAGES:
        raise VoiceError(422, "language must be 'en', 'sw' or 'auto'.")
    ext = _extension(content_type, filename)
    if len(data) > MAX_AUDIO_BYTES:
        raise VoiceError(413, "Recording is too long. Please keep it under a minute.")
    if len(data) < MIN_AUDIO_BYTES:
        raise VoiceError(400, "No audio was received. Please try again.")
    try:
        return transcribe_audio(data, f"voice.{ext}", LANGUAGES[language])
    except Exception as e:
        # Log the kind of failure only -- never the audio or any transcript.
        log.warning("transcription failed: %s", type(e).__name__)
        raise VoiceError(503, "Voice input is not available right now. Please type your symptoms instead.")