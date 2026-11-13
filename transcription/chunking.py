"""Chunking of long recordings, as in Handy v0.10.0 (src-tauri/src/audio_toolkit/chunking.rs).

Up to 40 s: a single chunk. Beyond: cuts in the middle of pauses, chunks of at least 5 s, 30 s targeted;
without a usable pause, a hard cut at 40 s (or halfway if the rest would be shorter than 5 s).
No overlap: each chunk is transcribed alone, then the texts are joined with a space.
"""
RATE = 16000
SINGLE = 40 * RATE
MINIMUM = 5 * RATE
TARGET = 30 * RATE
MAXIMUM = 40 * RATE


def pauses(segments, length):
    """Pauses (start, end) in samples, between the speech segments given by Silero."""
    result, prev_end = [], 0
    for s in segments:
        if s.start_sample > prev_end:
            result.append((prev_end, s.start_sample))
        prev_end = max(prev_end, s.end_sample)
    if prev_end < length:
        result.append((prev_end, length))
    return result


def _score(pause_samples, position):
    """Long pause (capped at 1 s) preferred; penalty according to the distance from 30 s."""
    duration = min(pause_samples / RATE, 1.0)
    pos = position / RATE
    return duration - (0.05 * (30 - pos) if pos < 30 else 0.1 * (pos - 30))


def cuts(length, pause_list):
    """Cut positions (in samples) for a recording of `length` samples."""
    if length <= SINGLE:
        return []
    result, start = [], 0
    while length - start > SINGLE:
        best, max_score = None, float("-inf")
        for p0, p1 in pause_list:
            middle = (p0 + p1) // 2
            size = middle - start
            if size < MINIMUM or size > MAXIMUM or length - middle < MINIMUM:
                continue
            s = _score(p1 - p0, size)
            if s > max_score:
                best, max_score = middle, s
        if best is None:
            best = start + MAXIMUM
            if length - best < MINIMUM:
                best = start + (length - start) // 2
        result.append(best)
        start = best
    return result
