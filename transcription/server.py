"""HTTP server compatible with OpenAI's transcription API (POST /v1/audio/transcriptions).

Two modes depending on response_format:
  json / text            dictation (Handy's chain: silences removed, custom words, "euh");
  verbose_json           subtitles: timestamped words on the original timeline ("words" field,
                         like timestamp_granularities=word at OpenAI) and one "segment" per transcribed chunk.

Environment variables:
  TRANSCRIPTION_API_KEY        if set, required as "Authorization: Bearer …" on /v1/*
  TRANSCRIPTION_CUSTOM_WORDS   file of custom words (one per line), reloaded when it changes
  TRANSCRIPTION_LANGUAGE       language assumed when the request gives none (used to remove "euh")
  TRANSCRIPTION_THREADS        compute threads for Parakeet (0 = automatic)
Transcribed text is never written to the log, only durations.
"""
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from . import audio
from .engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("transcription")

MODEL_NAME = "parakeet-ultra"
API_KEY = os.environ.get("TRANSCRIPTION_API_KEY", "")
LANGUAGE = os.environ.get("TRANSCRIPTION_LANGUAGE", "") or None
engine: Engine | None = None


@asynccontextmanager
async def lifespan(_app):
    global engine
    engine = await run_in_threadpool(Engine, os.environ.get("TRANSCRIPTION_CUSTOM_WORDS"),
                                     int(os.environ.get("TRANSCRIPTION_THREADS", "0")))
    yield


app = FastAPI(title="transcription-handy-like", lifespan=lifespan)


def check_key(authorization: str | None):
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "invalid API key")


@app.get("/health")
async def health():
    return {"state": "ready" if engine else "loading"}


@app.get("/v1/models")
async def list_models(authorization: str | None = Header(None)):
    check_key(authorization)
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "local"}]}


@app.post("/v1/audio/transcriptions")
async def transcriptions(file: UploadFile = File(...), model: str = Form(MODEL_NAME),
                         language: str | None = Form(None), prompt: str | None = Form(None),
                         response_format: str = Form("json"), temperature: float | None = Form(None),
                         authorization: str | None = Header(None)):
    check_key(authorization)
    if engine is None:
        raise HTTPException(503, "models are loading")
    t0 = time.perf_counter()
    data = await file.read()
    try:
        pcm = await run_in_threadpool(audio.decode, data)
    except audio.InvalidAudio as e:
        raise HTTPException(400, f"unreadable audio: {e}") from e
    t_decode = time.perf_counter() - t0
    lang = language or LANGUAGE
    if response_format == "verbose_json":
        h = await run_in_threadpool(engine.transcribe_timestamped, pcm, language or None)
        total = time.perf_counter() - t0
        log.info("timestamped: audio %.1f s, %s chunk(s), %d words | decode %.2f s, vad %.2f s, asr %.2f s, total %.2f s",
                 h.audio_duration, h.times.get("chunks", 0), len(h.words), t_decode, h.times.get("vad", 0),
                 h.times.get("asr", 0), total)
        return {"task": "transcribe", "language": h.language or "", "duration": h.audio_duration, "text": h.text,
                "segments": [{"id": i, "start": round(a, 3), "end": round(b, 3), "text": t}
                             for i, (a, b, t) in enumerate(h.chunks)],
                "words": [{"word": w.text, "start": w.start, "end": w.end} for w in h.words]}
    r = await run_in_threadpool(engine.transcribe, pcm, lang)
    total = time.perf_counter() - t0
    log.info("audio %.1f s, speech %.1f s, %s chunk(s) | decode %.2f s, vad %.2f s, asr %.2f s, total %.2f s",
             r.audio_duration, r.speech_duration, r.times.get("chunks", 0), t_decode,
             r.times.get("vad", 0), r.times.get("asr", 0), total)

    if response_format == "text":
        return PlainTextResponse(r.text)
    if response_format in ("srt", "vtt"):
        raise HTTPException(400, "srt/vtt formats are not supported: request verbose_json and build the subtitles on the client side")
    return {"text": r.text}
