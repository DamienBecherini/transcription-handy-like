from transcription import timestamps
from transcription.timestamps import Word

S = 16000


def test_group_merges_neighbouring_segments():
    seg = [(1 * S, 5 * S), (6 * S, 20 * S), (21 * S, 35 * S)]
    assert timestamps.group(seg, 40 * S, margin=0) == [(1 * S, 35 * S)]


def test_group_cuts_at_40_s():
    seg = [(0, 30 * S), (31 * S, 45 * S), (46 * S, 60 * S)]
    m = timestamps.group(seg, 60 * S, margin=0)
    assert m == [(0, 30 * S), (31 * S, 60 * S)]
    assert all(b - a <= timestamps.MAXIMUM for a, b in m)


def test_group_hard_cuts_a_segment_that_is_too_long():
    m = timestamps.group([(0, 100 * S)], 100 * S, margin=0)
    assert m[0] == (0, 30 * S)
    assert m[-1][1] == 100 * S
    assert all(b - a <= timestamps.MAXIMUM for a, b in m)


def test_group_margin_does_not_overlap_the_neighbour():
    seg = [(1 * S, 20 * S), (int(20.1 * S), 50 * S)]
    (a1, b1), (a2, b2) = timestamps.group(seg, 60 * S)
    assert a1 == 1 * S - timestamps.MARGIN
    assert b1 <= a2                        # no overlap
    assert b2 == 50 * S + timestamps.MARGIN


def test_group_recording_bounds():
    assert timestamps.group([(0, 3 * S)], 3 * S) == [(0, 3 * S)]
    assert timestamps.group([], 3 * S) == []


def test_clean_words():
    words = [Word("Bonjour", 0.0, 0.5), Word("euh", 0.5, 0.7), Word("", 0.7, 0.8), Word("tous,", 0.4, 0.4)]
    r = timestamps.clean_words(words, "fr")
    assert [w.text for w in r] == ["Bonjour", "tous,"]
    assert r[1].start >= r[0].end and r[1].end > r[1].start


def test_fillers_depend_on_language():
    assert timestamps.is_filler("Euh,", "fr")
    assert not timestamps.is_filler("euh", "en")
    assert timestamps.is_filler("Uh", None)
