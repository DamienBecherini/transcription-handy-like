"""Compares Parakeet Ultra quantizations on recordings: time and text.

    python -m transcription.bench [--quantizations Q8_0 Q5_K_M …] [--repetitions 3] <audio files>…

Each file goes through the server's whole chain (ffmpeg, voice detection, Parakeet, cleanup).
Prints the median transcription time and the text, flagging what differs from the first
quantization in the list (the reference, Q8_0 by default).
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

from . import audio, models
from .engine import Engine


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quantizations", nargs="+", default=list(models.ASR_VARIANTS),
                   choices=list(models.ASR_VARIANTS))
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--language", default="fr")
    p.add_argument("files", nargs="+")
    a = p.parse_args()

    sounds = {Path(f).name: audio.decode(Path(f).read_bytes()) for f in a.files}
    reference = {}
    for q in a.quantizations:
        t = time.perf_counter()
        engine = Engine(quantization=q)
        size = models.fetch(models.ASR_VARIANTS[q]).stat().st_size / 1e6
        print(f"\n=== {q} ({size:.0f} MB, ready in {time.perf_counter() - t:.1f} s)", flush=True)
        for name, pcm in sounds.items():
            times, r = [], None
            engine.transcribe(pcm, a.language)  # warm-up run
            for _ in range(a.repetitions):
                t = time.perf_counter()
                r = engine.transcribe(pcm, a.language)
                times.append(time.perf_counter() - t)
            reference.setdefault(name, r.text)
            mark = "=" if r.text == reference[name] else "≠"
            print(f"  {name:28} {r.audio_duration:5.1f} s  {statistics.median(times):5.2f} s  {mark} {r.text}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
