"""Transcription chain: 16 kHz PCM → voice detection → (chunking) → Parakeet Ultra → text cleanup."""
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import transcribe_cpp

from . import chunking, models, text, timestamps, vad

log = logging.getLogger("transcription")
RATE = 16000


@dataclass
class Result:
    text: str
    audio_duration: float       # seconds received
    speech_duration: float      # seconds kept after voice detection (before padding)
    times: dict = field(default_factory=dict)


@dataclass
class TimestampedResult:
    words: list[timestamps.Word]
    chunks: list[tuple[float, float, str]]   # (start, end, text) of each transcribed chunk
    language: str | None
    audio_duration: float
    times: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


class CustomWords:
    """Text file, one word or phrase per line (# for a comment); reloaded when it changes."""

    def __init__(self, path: str | None):
        self.path = Path(path) if path else None
        self._mtime = None
        self._words: list[str] = []

    def get(self) -> list[str]:
        if not self.path or not self.path.exists():
            return []
        mtime = self.path.stat().st_mtime
        if mtime != self._mtime:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            self._words = [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]
            self._mtime = mtime
            log.info("custom words: %d", len(self._words))
        return self._words


class Engine:
    def __init__(self, custom_words: str | None = None, threads: int = 0, quantization: str = "Q8_0"):
        cpu = next(d for d in transcribe_cpp.backends() if d.device_type == "cpu")
        t = time.perf_counter()
        self.asr = transcribe_cpp.Model(models.fetch(models.ASR_VARIANTS[quantization]), device=cpu)
        self.silero = transcribe_cpp.Model(models.fetch(models.VAD), device=cpu)
        self.session = self.asr.session(n_threads=threads)
        self.vad_session = self.silero.vad_session(n_threads=1)
        self.frame = self.silero.vad_info.frame_samples
        self.lock = threading.Lock()   # one transcription at a time: the CPU is already 100% busy
        self.words = CustomWords(custom_words)
        log.info("models loaded in %.1f s (VAD frame %d)", time.perf_counter() - t, self.frame)

    def transcribe(self, pcm: np.ndarray, language: str | None) -> Result:
        times = {}
        with self.lock:
            t = time.perf_counter()
            probs = self.vad_session.run(pcm).probs
            speech = vad.keep_speech(pcm, probs, self.frame)
            times["vad"] = time.perf_counter() - t
            res = Result("", len(pcm) / RATE, len(speech) / RATE, times)
            if len(speech) == 0:
                return res

            t = time.perf_counter()
            speech = vad.pad(speech)
            chunks = [speech]
            if len(speech) > chunking.SINGLE:
                seg = self.vad_session.run(speech, threshold=0.5, neg_threshold=0.35, min_speech_ms=250,
                                           min_silence_ms=100, speech_pad_ms=30).segments
                bounds = [0, *chunking.cuts(len(speech), chunking.pauses(seg, len(speech))), len(speech)]
                chunks = [speech[a:b] for a, b in zip(bounds, bounds[1:])]
            texts = [self.session.run(c).text.strip() for c in chunks]
            times["asr"] = time.perf_counter() - t
            times["chunks"] = len(chunks)

        t = time.perf_counter()
        res.text = text.clean(" ".join(x for x in texts if x), language, self.words.get())
        times["text"] = time.perf_counter() - t
        return res

    def transcribe_timestamped(self, pcm: np.ndarray, language: str | None) -> TimestampedResult:
        """Timestamped words on the original timeline (subtitles): see timestamps.py.
        No custom words here (they rewrite groups of words), only filler words."""
        times = {}
        with self.lock:
            t = time.perf_counter()
            seg = self.vad_session.run(pcm, threshold=0.5, neg_threshold=0.35, min_speech_ms=250,
                                       min_silence_ms=100, speech_pad_ms=30).segments
            chunks = timestamps.group([(x.start_sample, x.end_sample) for x in seg], len(pcm))
            times["vad"] = time.perf_counter() - t
            t = time.perf_counter()
            words, details, seen_language = [], [], None
            for a, b in chunks:
                r = self.session.run(pcm[a:b], timestamps="word")
                offset = a / RATE
                words.extend(timestamps.Word(w.text, offset + w.t0_ms / 1000, offset + w.t1_ms / 1000)
                             for w in r.words)
                details.append((a / RATE, b / RATE, r.text.strip()))
                seen_language = seen_language or getattr(r, "language", None)
            times["asr"] = time.perf_counter() - t
            times["chunks"] = len(chunks)
        final_language = language or seen_language or None
        return TimestampedResult(timestamps.clean_words(words, final_language), details, final_language,
                                 len(pcm) / RATE, times)
