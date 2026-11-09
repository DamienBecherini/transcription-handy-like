import numpy as np

from transcription import decoupage, vad


def test_silence_seul():
    assert vad.trames_retenues([0.0] * 50) == []


def test_une_seule_trame_voisee_ne_declenche_pas():
    assert vad.trames_retenues([0.0] * 10 + [0.9] + [0.0] * 10) == []


def test_preroll_demarrage_maintien():
    probs = [0.0] * 30 + [0.9] * 5 + [0.0] * 30
    gardees = vad.trames_retenues(probs)
    # pré-roll : 15 trames avant la 2e trame voisée (trame 31), donc à partir de 31 - 15 = 16
    assert gardees[0] == 16
    # maintien : 15 trames après la dernière trame voisée (34)
    assert gardees[-1] == 34 + 15
    assert gardees == sorted(set(gardees))


def test_completer_extrait_court():
    court = np.ones(8000, dtype=np.float32)
    assert len(vad.completer(court)) == 20000
    assert len(vad.completer(np.ones(20000, dtype=np.float32))) == 20000
    assert len(vad.completer(np.zeros(0, dtype=np.float32))) == 0


def test_pas_de_decoupage_sous_40_s():
    assert decoupage.coupes(39 * 16000, []) == []


def test_decoupage_dans_une_pause_proche_de_30_s():
    longueur = 70 * 16000
    pauses = [(10 * 16000, int(10.5 * 16000)), (29 * 16000, 30 * 16000), (50 * 16000, int(50.4 * 16000))]
    c = decoupage.coupes(longueur, pauses)
    assert c[0] == int(29.5 * 16000)
    assert all(b - a >= decoupage.MINIMUM for a, b in zip([0, *c], [*c, longueur]))


def test_decoupage_sans_pause():
    c = decoupage.coupes(90 * 16000, [])
    assert c == [40 * 16000, 80 * 16000] or all(b - a >= decoupage.MINIMUM for a, b in zip([0, *c], [*c, 90 * 16000]))
