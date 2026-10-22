# voice_flask.py
"""
Flask wrapper for voice input -- for the dashboard served by logistic_regression.app.py.

Adds two routes to the Flask app:
    POST /transcribe   audio clip + language  ->  {"text": "..."}
    GET  /voice.js     the microphone-button script
See voice_core.py for the logic and the privacy notes.

Use in the Flask app (two lines):
    from voice_flask import voice_bp
    app.register_blueprint(voice_bp)
"""

from flask import Blueprint, jsonify, request, send_file

import voice_core

voice_bp = Blueprint("voice", __name__)


@voice_bp.post("/transcribe")
def transcribe():
    clip = request.files.get("audio")
    if clip is None:
        return jsonify(detail="No audio file was sent."), 422
    data = clip.stream.read(voice_core.MAX_AUDIO_BYTES + 1)
    try:
        text = voice_core.handle_audio(data, clip.content_type, clip.filename, request.form.get("language", "auto"))
    except voice_core.VoiceError as e:
        return jsonify(detail=e.detail), e.status
    return jsonify(text=text)


@voice_bp.get("/voice.js")
def voice_js():
    return send_file(voice_core.asset_path("voice_input.js"), mimetype="application/javascript")