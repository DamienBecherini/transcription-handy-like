import numpy as np

from transcription import chunking, vad


def test_silence_only():
    assert vad.kept_frames([0.0] * 50) == []


def test_single_voiced_frame_does_not_trigger():
    assert vad.kept_frames([0.0] * 10 + [0.9] + [0.0] * 10) == []


def test_preroll_onset_hangover():
    probs = [0.0] * 30 + [0.9] * 5 + [0.0] * 30
    kept = vad.kept_frames(probs)
    # pre-roll: 15 frames before the 2nd voiced frame (frame 31), so from 31 - 15 = 16
    assert kept[0] == 16
    # hangover: 15 frames after the last voiced frame (34)
    assert kept[-1] == 34 + 15
    assert kept == sorted(set(kept))


def test_pad_short_clip():
    short = np.ones(8000, dtype=np.float32)
    assert len(vad.pad(short)) == 20000
    assert len(vad.pad(np.ones(20000, dtype=np.float32))) == 20000
    assert len(vad.pad(np.zeros(0, dtype=np.float32))) == 0


def test_no_chunking_under_40_s():
    assert chunking.cuts(39 * 16000, []) == []


def test_chunking_in_a_pause_close_to_30_s():
    length = 70 * 16000
    pauses = [(10 * 16000, int(10.5 * 16000)), (29 * 16000, 30 * 16000), (50 * 16000, int(50.4 * 16000))]
    c = chunking.cuts(length, pauses)
    assert c[0] == int(29.5 * 16000)
    assert all(b - a >= chunking.MINIMUM for a, b in zip([0, *c], [*c, length]))


def test_chunking_without_pause():
    c = chunking.cuts(90 * 16000, [])
    assert c == [40 * 16000, 80 * 16000] or all(b - a >= chunking.MINIMUM for a, b in zip([0, *c], [*c, 90 * 16000]))
