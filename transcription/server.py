"""HTTP server compatible with OpenAI's transcription API (POST /v1/audio/transcriptions).

Two modes depending on response_format:
  json / text            dictation (Handy's chain: silences removed, custom words, "euh");
  verbose_json           subtitles: timestamped words on the original timeline ("words" field,
                         like timestamp_granularities=word at OpenAI) and one "segment" per transcribed chunk.

Environment variables:
  TRANSCRIPTION_API_KEY        if set, required as "Authorization: Bearer …" on /v1/*
  TRANSCRIPTION_ALLOWED_ORIGINS  web origins allowed to call /v1/* from a browser, comma-separated (none by default)
  TRANSCRIPTION_CUSTOM_WORDS   file of custom words (one per line), reloaded when it changes
  TRANSCRIPTION_LANGUAGE       language assumed when the request gives none (used to remove "euh")
  TRANSCRIPTION_THREADS        compute threads for Parakeet (0 = automatic)
Transcribed text is never written to the log, only durations.

Browsers: a web page can send a multipart upload to any address without asking the server first, so any site
open in a browser of the network could make this server work. Clients of this API are programs, which send no
Origin header; requests to /v1/* that carry one are refused unless the origin is allowed.

Cancellation: the OpenAI API has no cancel request; a client that no longer wants the answer closes its connection.
The server notices it and stops between two chunks, so the next request does not wait behind work nobody will read.
"""
import asyncio
import hmac
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from . import audio
from .engine import RATE, Cancelled, Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("transcription")

MODEL_NAME = "parakeet-ultra"
API_KEY = os.environ.get("TRANSCRIPTION_API_KEY", "")
LANGUAGE = os.environ.get("TRANSCRIPTION_LANGUAGE", "") or None
ALLOWED_ORIGINS = {o.strip().rstrip("/") for o in os.environ.get("TRANSCRIPTION_ALLOWED_ORIGINS", "").split(",")
                   if o.strip()}
engine: Engine | None = None


@asynccontextmanager
async def lifespan(_app):
    global engine
    engine = await run_in_threadpool(Engine, os.environ.get("TRANSCRIPTION_CUSTOM_WORDS"),
                                     int(os.environ.get("TRANSCRIPTION_THREADS", "0")))
    yield


app = FastAPI(title="transcription-handy-like", lifespan=lifespan)


class RefuseForeignPages:
    """Plain ASGI middleware (not @app.middleware, whose wrapper hides the disconnection of the client from
    request.is_disconnected(), on which cancellation depends)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/v1/"):
            origin = dict(scope.get("headers") or []).get(b"origin")
            if origin is not None and origin.decode("latin-1").rstrip("/") not in ALLOWED_ORIGINS:
                refusal = JSONResponse({"detail": "requests from web pages are refused (TRANSCRIPTION_ALLOWED_ORIGINS)"},
                                       status_code=403)
                return await refusal(scope, receive, send)
        await self.app(scope, receive, send)


app.add_middleware(RefuseForeignPages)


def check_key(authorization: str | None):
    if API_KEY and not hmac.compare_digest((authorization or "").encode(), f"Bearer {API_KEY}".encode()):
        raise HTTPException(401, "invalid API key")


@app.get("/health")
async def health():
    return {"state": "ready" if engine else "loading"}


@app.get("/v1/models")
async def list_models(authorization: str | None = Header(None)):
    check_key(authorization)
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "local"}]}


DISCONNECT_CHECK_S = 0.5
CLIENT_GONE = 499                      # status of a request whose client left (nobody reads it)


async def _watch_client(request: Request, gone: threading.Event):
    while not gone.is_set():
        if await request.is_disconnected():
            gone.set()
            return
        await asyncio.sleep(DISCONNECT_CHECK_S)


async def run_watched(request: Request, work, *args):
    """Runs `work(*args, cancelled)` in a thread while watching the connection: `cancelled()` becomes true when the
    client leaves, and the engine then raises Cancelled between two chunks."""
    gone = threading.Event()
    watcher = asyncio.create_task(_watch_client(request, gone))
    try:
        return await run_in_threadpool(work, *args, gone.is_set)
    finally:
        watcher.cancel()


@app.post("/v1/audio/transcriptions")
async def transcriptions(request: Request, file: UploadFile = File(...), model: str = Form(MODEL_NAME),
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
    try:
        return await _transcribe(request, pcm, language, response_format, t0, t_decode)
    except Cancelled:
        log.info("cancelled: the client left after %.1f s (audio %.1f s)", time.perf_counter() - t0, len(pcm) / RATE)
        return Response(status_code=CLIENT_GONE)


async def _transcribe(request: Request, pcm, language: str | None, response_format: str, t0: float, t_decode: float):
    lang = language or LANGUAGE
    if response_format == "verbose_json":
        h = await run_watched(request, engine.transcribe_timestamped, pcm, language or None)
        total = time.perf_counter() - t0
        log.info("timestamped: audio %.1f s, %s chunk(s), %d words | decode %.2f s, vad %.2f s, asr %.2f s, total %.2f s",
                 h.audio_duration, h.times.get("chunks", 0), len(h.words), t_decode, h.times.get("vad", 0),
                 h.times.get("asr", 0), total)
        return {"task": "transcribe", "language": h.language or "", "duration": h.audio_duration, "text": h.text,
                "segments": [{"id": i, "start": round(a, 3), "end": round(b, 3), "text": t}
                             for i, (a, b, t) in enumerate(h.chunks)],
                "words": [{"word": w.text, "start": w.start, "end": w.end} for w in h.words]}
    r = await run_watched(request, engine.transcribe, pcm, lang)
    total = time.perf_counter() - t0
    log.info("audio %.1f s, speech %.1f s, %s chunk(s) | decode %.2f s, vad %.2f s, asr %.2f s, total %.2f s",
             r.audio_duration, r.speech_duration, r.times.get("chunks", 0), t_decode,
             r.times.get("vad", 0), r.times.get("asr", 0), total)

    if response_format == "text":
        return PlainTextResponse(r.text)
    if response_format in ("srt", "vtt"):
        raise HTTPException(400, "srt/vtt formats are not supported: request verbose_json and build the subtitles on the client side")
    return {"text": r.text}
