"""Cases taken from Handy v0.10.0's tests (src-tauri/src/audio_toolkit/text.rs) and French cases."""
from transcription import text


def test_soundex():
    assert text.soundex("Robert") == text.soundex("Rupert") == "R163"
    assert text.soundex("Ashcraft") == "A261"
    assert text.soundex("Tymczak") == "T522"


def test_custom_words_exact_match():
    # Handy: test_apply_custom_words_exact_match (threshold 0.5)
    assert text.apply_custom_words("hello world", ["Hello", "World"], 0.5) == "Hello World"


def test_case():
    # Handy: test_preserve_case_pattern
    assert text._case("HELLO", "world") == "WORLD"
    assert text._case("Hello", "world") == "World"
    assert text._case("hello", "WORLD") == "WORLD"


def test_custom_words_close_match():
    assert text.apply_custom_words("pousse sur Gitee.", ["Gitea"]) == "pousse sur Gitea."


def test_accented_words_ignored_like_handy():
    assert text.apply_custom_words("un gîte, un gâteau", ["Gitea"]) == "un gîte, un gâteau"


def test_custom_words_ngram():
    assert text.apply_custom_words("I use Charge B daily", ["ChargeBee"]) == "I use ChargeBee daily"


def test_custom_words_do_not_cross_punctuation():
    # Handy: the comma closes the n-gram at "B,"
    r = text.apply_custom_words("il cui nome è Charge B, che permette", ["ChargeBee"], 0.5)
    assert "ChargeBee," in r and "Charge B" not in r


def test_custom_words_keep_case():
    assert text.apply_custom_words("Kubernetis est lancé", ["kubernetes"]) == "Kubernetes est lancé"


def test_universal_fillers_always_removed():
    assert text.clean("Uhm, je pense que oui", None) == "Je pense que oui"


def test_euh_removed_only_in_french():
    assert text.clean("Alors euh on commence", "fr") == "Alors on commence"
    assert text.clean("Alors euh on commence", None) == "Alors euh on commence"


def test_capital_moves_to_next_word():
    assert text.clean("Euh, peux-tu relancer ?", "fr") == "Peux-tu relancer ?"


def test_stutters():
    assert text.clean("je je je pense", "fr") == "je pense"
    assert text.clean("très très bien", "fr") == "très très bien"
    # separated by commas: not stutters (same rule as Handy)
    assert text.clean("beaucoup, beaucoup, beaucoup", "fr") == "beaucoup, beaucoup, beaucoup"
