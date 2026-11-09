from transcription import horodatage
from transcription.horodatage import Mot

S = 16000


def test_regrouper_reunit_les_segments_voisins():
    seg = [(1 * S, 5 * S), (6 * S, 20 * S), (21 * S, 35 * S)]
    assert horodatage.regrouper(seg, 40 * S, marge=0) == [(1 * S, 35 * S)]


def test_regrouper_coupe_a_40_s():
    seg = [(0, 30 * S), (31 * S, 45 * S), (46 * S, 60 * S)]
    m = horodatage.regrouper(seg, 60 * S, marge=0)
    assert m == [(0, 30 * S), (31 * S, 60 * S)]
    assert all(b - a <= horodatage.MAXIMUM for a, b in m)


def test_regrouper_segment_trop_long_coupe_franchement():
    m = horodatage.regrouper([(0, 100 * S)], 100 * S, marge=0)
    assert m[0] == (0, 30 * S)
    assert m[-1][1] == 100 * S
    assert all(b - a <= horodatage.MAXIMUM for a, b in m)


def test_regrouper_marge_sans_mordre_sur_le_voisin():
    seg = [(1 * S, 20 * S), (int(20.1 * S), 50 * S)]
    (a1, b1), (a2, b2) = horodatage.regrouper(seg, 60 * S)
    assert a1 == 1 * S - horodatage.MARGE
    assert b1 <= a2                        # pas de chevauchement
    assert b2 == 50 * S + horodatage.MARGE


def test_regrouper_bornes_de_l_enregistrement():
    assert horodatage.regrouper([(0, 3 * S)], 3 * S) == [(0, 3 * S)]
    assert horodatage.regrouper([], 3 * S) == []


def test_nettoyer_mots():
    mots = [Mot("Bonjour", 0.0, 0.5), Mot("euh", 0.5, 0.7), Mot("", 0.7, 0.8), Mot("tous,", 0.4, 0.4)]
    r = horodatage.nettoyer_mots(mots, "fr")
    assert [m.texte for m in r] == ["Bonjour", "tous,"]
    assert r[1].debut >= r[0].fin and r[1].fin > r[1].debut


def test_remplissage_selon_langue():
    assert horodatage.est_remplissage("Euh,", "fr")
    assert not horodatage.est_remplissage("euh", "en")
    assert horodatage.est_remplissage("Uh", None)
