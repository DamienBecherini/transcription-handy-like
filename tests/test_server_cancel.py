"""Cancellation: a client that closes its connection stops the transcription between two chunks."""
import asyncio
import threading
import time
import unittest
from unittest import mock

import numpy as np

from transcription import server
from transcription.engine import Cancelled


class SlowEngine:
    """Works chunk by chunk like the real engine, checking `cancelled()` before each one."""

    def __init__(self, chunks=20, chunk_s=0.1):
        self.chunks, self.chunk_s, self.done = chunks, chunk_s, 0
        self.lock = threading.Lock()

    def _work(self, cancelled):
        with self.lock:
            for _ in range(self.chunks):
                if cancelled():
                    raise Cancelled()
                time.sleep(self.chunk_s)
                self.done += 1

    def transcribe_timestamped(self, pcm, language, cancelled):
        self._work(cancelled)
        return server.engine_result_for_tests

    def transcribe(self, pcm, language, cancelled):
        self._work(cancelled)
        return mock.Mock(text="ok", audio_duration=1.0, speech_duration=1.0, times={})


def multipart(fields: dict, boundary="b0undary") -> bytes:
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="a.wav"\r\n'
                 "Content-Type: application/octet-stream\r\n\r\n".encode() + b"RIFF" + b"\r\n")
    return b"".join(parts) + f"--{boundary}--\r\n".encode()


def post(body: bytes, leave_after_s: float | None):
    """POST /v1/audio/transcriptions through the ASGI app; the client disconnects after `leave_after_s` seconds."""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
             "path": "/v1/audio/transcriptions", "raw_path": b"/v1/audio/transcriptions", "query_string": b"", "root_path": "",
             "headers": [(b"content-type", b"multipart/form-data; boundary=b0undary"), (b"content-length", str(len(body)).encode())],
             "client": ("127.0.0.1", 50000), "server": ("127.0.0.1", 8000)}
    sent, start = [], time.monotonic()
    state = {"body_sent": False}

    async def receive():
        if not state["body_sent"]:
            state["body_sent"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        while leave_after_s is None or time.monotonic() - start < leave_after_s:
            await asyncio.sleep(0.02)
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    asyncio.run(server.app(scope, receive, send))
    return next(m for m in sent if m["type"] == "http.response.start")["status"], time.monotonic() - start


class Cancel(unittest.TestCase):
    def setUp(self):
        server.engine_result_for_tests = mock.Mock(words=[], chunks=[], language="fr", audio_duration=2.0, times={}, text="")
        patches = [mock.patch.object(server, "engine", SlowEngine()), mock.patch.object(server.audio, "decode", lambda _d: np.zeros(16000)),
                   mock.patch.object(server, "API_KEY", ""), mock.patch.object(server, "DISCONNECT_CHECK_S", 0.05)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_client_that_leaves_stops_the_work_between_two_chunks(self):
        status, seconds = post(multipart({"response_format": "verbose_json"}), leave_after_s=0.3)
        self.assertEqual(status, server.CLIENT_GONE)
        self.assertLess(server.engine.done, 10)          # 20 chunks of 0.1 s: stopped well before the end
        self.assertLess(seconds, 1.0)
        self.assertFalse(server.engine.lock.locked())    # the next request does not wait

    def test_dictation_mode_stops_too(self):
        status, _ = post(multipart({"response_format": "json"}), leave_after_s=0.3)
        self.assertEqual(status, server.CLIENT_GONE)

    def test_client_that_stays_gets_its_answer(self):
        server.engine.chunks = 3
        status, _ = post(multipart({"response_format": "verbose_json"}), leave_after_s=None)
        self.assertEqual(status, 200)
        self.assertEqual(server.engine.done, 3)
