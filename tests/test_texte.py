"""Cas repris des tests de Handy v0.10.0 (src-tauri/src/audio_toolkit/text.rs) et cas français."""
from transcription import texte


def test_soundex():
    assert texte.soundex("Robert") == texte.soundex("Rupert") == "R163"
    assert texte.soundex("Ashcraft") == "A261"
    assert texte.soundex("Tymczak") == "T522"


def test_mots_personnalises_correspondance_exacte():
    # Handy : test_apply_custom_words_exact_match (seuil 0.5)
    assert texte.appliquer_mots_personnalises("hello world", ["Hello", "World"], 0.5) == "Hello World"


def test_casse():
    # Handy : test_preserve_case_pattern
    assert texte._casse("HELLO", "world") == "WORLD"
    assert texte._casse("Hello", "world") == "World"
    assert texte._casse("hello", "WORLD") == "WORLD"


def test_mots_personnalises_proche():
    assert texte.appliquer_mots_personnalises("pousse sur Gitee.", ["Gitea"]) == "pousse sur Gitea."


def test_mots_accentues_ignores_comme_handy():
    assert texte.appliquer_mots_personnalises("un gîte, un gâteau", ["Gitea"]) == "un gîte, un gâteau"


def test_mots_personnalises_ngramme():
    assert texte.appliquer_mots_personnalises("I use Charge B daily", ["ChargeBee"]) == "I use ChargeBee daily"


def test_mots_personnalises_ne_franchit_pas_la_ponctuation():
    # Handy : la virgule ferme le n-gramme à « B, »
    r = texte.appliquer_mots_personnalises("il cui nome è Charge B, che permette", ["ChargeBee"], 0.5)
    assert "ChargeBee," in r and "Charge B" not in r


def test_mots_personnalises_casse_conservee():
    assert texte.appliquer_mots_personnalises("Kubernetis est lancé", ["kubernetes"]) == "Kubernetes est lancé"


def test_remplissage_universel_toujours_retire():
    assert texte.nettoyer("Uhm, je pense que oui", None) == "Je pense que oui"


def test_euh_retire_seulement_en_francais():
    assert texte.nettoyer("Alors euh on commence", "fr") == "Alors on commence"
    assert texte.nettoyer("Alors euh on commence", None) == "Alors euh on commence"


def test_majuscule_rendue_au_mot_suivant():
    assert texte.nettoyer("Euh, peux-tu relancer ?", "fr") == "Peux-tu relancer ?"


def test_begaiements():
    assert texte.nettoyer("je je je pense", "fr") == "je pense"
    assert texte.nettoyer("très très bien", "fr") == "très très bien"
    # séparés par des virgules : ce ne sont pas des bégaiements (même règle que Handy)
    assert texte.nettoyer("beaucoup, beaucoup, beaucoup", "fr") == "beaucoup, beaucoup, beaucoup"
