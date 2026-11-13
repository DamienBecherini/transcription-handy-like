"""Timestamped transcription (for subtitles): the original positions are kept.

Unlike dictation (vad.py: silences are removed, then speech is stitched back together), the recording's
timeline is kept: the speech segments found by Silero are grouped into chunks of 40 s at most (like long
dictation), each chunk is transcribed with Parakeet's word timestamps (timestamps="word"), and the chunk's
offset is added to every word.
"""
from dataclasses import dataclass

from . import text

RATE = 16000
MAXIMUM = 40 * RATE          # a chunk: 40 s at most (like chunking.SINGLE)
TARGET = 30 * RATE           # hard cut of a speech segment that is too long and has no pause
MARGIN = int(0.2 * RATE)     # silence kept on each side of a chunk (more accurate word boundaries)


@dataclass
class Word:
    text: str
    start: float   # seconds from the start of the recording
    end: float


def group(segments, length, maximum=MAXIMUM, target=TARGET, margin=MARGIN):
    """Chunks (start, end) in samples to transcribe, from the speech segments (start, end).

    Neighbouring segments are merged as long as the chunk does not exceed `maximum`; a segment longer
    than `maximum` on its own is hard-cut into slices of `target`. Each chunk is widened by `margin`
    into the surrounding silence, without overlapping its neighbour or leaving the recording.
    """
    chunks = []
    for a, b in segments:
        a, b = max(0, a), min(b, length)
        if b <= a:
            continue
        while b - a > maximum:
            chunks.append((a, a + target))
            a += target
        if chunks and b - chunks[-1][0] <= maximum:
            chunks[-1] = (chunks[-1][0], b)
        else:
            chunks.append((a, b))
    widened = []
    for i, (a, b) in enumerate(chunks):
        prev = chunks[i - 1][1] if i else 0
        nxt = chunks[i + 1][0] if i + 1 < len(chunks) else length
        a2 = max(a - margin, (a + prev) // 2 if i else 0)
        b2 = min(b + margin, (b + nxt) // 2 if i + 1 < len(chunks) else length)
        widened.append((a2, b2))
    return widened


def is_filler(word: str, language: str | None) -> bool:
    """Filler word ("euh", "uh"…) to remove, using the same list as dictation."""
    base = text.key(word)
    if not base:
        return False
    fillers = text.UNIVERSAL_FILLERS + text.FILLERS_BY_LANGUAGE.get((language or "").split("-")[0].split("_")[0], ())
    return base in {text.key(m) for m in fillers}


def clean_words(words: list[Word], language: str | None) -> list[Word]:
    """Removes filler words and empty words; guarantees end > start and chronological order."""
    out: list[Word] = []
    for w in words:
        t = w.text.strip()
        if not t or is_filler(t, language):
            continue
        start = max(w.start, out[-1].end if out else 0.0)
        end = max(w.end, start + 0.05)
        out.append(Word(t, round(start, 3), round(end, 3)))
    return out
