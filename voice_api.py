# voice_api.py
"""FastAPI wrapper for voice input: POST /transcribe. See voice_core.py for the logic and privacy notes."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

import voice_core

router = APIRouter()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form("auto")):
    data = await audio.read(voice_core.MAX_AUDIO_BYTES + 1)
    try:
        text = await run_in_threadpool(voice_core.handle_audio, data, audio.content_type, audio.filename, language)
    except voice_core.VoiceError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
    return {"text": text}