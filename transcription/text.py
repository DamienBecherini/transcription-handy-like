"""Cleanup of the transcribed text, as in Handy v0.10.0 (src-tauri/src/audio_toolkit/text.rs).

Order: custom words (fuzzy correction), filler words, stutters, spaces.
"""
import re

WORD_THRESHOLD = 0.18   # Handy's default word_correction_threshold

# Never words in any language: always removed.
UNIVERSAL_FILLERS = ("uh", "uhm", "umm", "uhh", "uhhh", "ehh", "ehm", "ahm", "hmm", "hm", "mmm", "хм", "ммм")
# Removed only when the language of the text is known.
FILLERS_BY_LANGUAGE = {"en": ("um", "ah", "eh"), "de": ("äh", "ähm"), "fr": ("euh",)}


# --- Custom words ---------------------------------------------------------------------------------

def key(word: str) -> str:
    """Comparison key: lowercase, letters and digits only. As in Handy, an accented word gives a
    non-ASCII key, which the correction ignores. Tried and dropped: removing accents made
    "gîte" and "gâteau" get replaced by "Gitea"."""
    return "".join(c for c in word.lower() if c.isalnum())


def _ascii_alnum(s: str) -> bool:
    return bool(s) and s.isascii() and s.isalnum()


def _ascii_alpha(s: str) -> bool:
    return bool(s) and s.isascii() and s.isalpha()


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


_SOUNDEX = {**dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"), **dict.fromkeys("dt", "3"),
            "l": "4", **dict.fromkeys("mn", "5"), "r": "6"}


def soundex(word: str) -> str:
    """American Soundex (h and w do not separate two identical codes, vowels do)."""
    word = word.lower()
    code = word[0].upper()
    prev = _SOUNDEX.get(word[0], "")
    for c in word[1:]:
        digit = _SOUNDEX.get(c, "")
        if digit and digit != prev:
            code += digit
        if c not in "hw":
            prev = digit
    return (code + "000")[:4]


def _word_keys(words):
    keys = []
    for i, word in enumerate(words):
        k = key(word)
        if _ascii_alnum(k):
            keys.append((i, k))
        if "&" in word:
            k2 = key(word.replace("&", " and "))
            if _ascii_alnum(k2) and k2 != k:
                keys.append((i, k2))
    return keys


def _best(candidate, words, keys, threshold):
    if not _ascii_alnum(candidate) or len(candidate) > 50:
        return None
    best, min_score = None, float("inf")
    for i, k in keys:
        gap = abs(len(candidate) - len(k))
        lmax = max(len(candidate), len(k))
        if gap > max(lmax * 0.25, 2.0):
            continue
        score = levenshtein(candidate, k) / lmax if lmax else 1.0
        if _ascii_alpha(candidate) and _ascii_alpha(k) and soundex(candidate) == soundex(k):
            score *= 0.3
        if score < threshold and score < min_score:
            best, min_score = words[i], score
    return (best, min_score) if best is not None else None


def _punctuation(word: str):
    start = next((i for i, c in enumerate(word) if c.isalnum()), len(word))
    end = next((i + 1 for i in range(len(word) - 1, -1, -1) if word[i].isalnum()), 0)
    return word[:start], word[end:] if end < len(word) else ""


def _case(original: str, replacement: str) -> str:
    if original and all(c.isupper() for c in original):
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def apply_custom_words(text: str, words, threshold: float = WORD_THRESHOLD) -> str:
    """Replaces the n-grams (1 to 3 words) close to a custom word (Levenshtein + Soundex)."""
    if not words:
        return text
    keys = _word_keys(words)
    tokens = text.split()
    out, i = [], 0
    while i < len(tokens):
        found = None
        for n in (3, 2, 1):
            if i + n > len(tokens):
                continue
            ngram = tokens[i:i + n]
            if any(_punctuation(t)[1] for t in ngram[:-1]):
                continue  # do not cross a punctuation mark
            r = _best("".join(key(t) for t in ngram), words, keys, threshold)
            if r and (found is None or r[1] < found[2]):
                found = (n, r[0], r[1])
        if found:
            n, replacement, _ = found
            prefix, _ = _punctuation(tokens[i])
            _, suffix = _punctuation(tokens[i + n - 1])
            out.append(prefix + _case(tokens[i], replacement) + suffix)
            i += n
        else:
            out.append(tokens[i])
            i += 1
    return " ".join(out)


# --- Filler words ---------------------------------------------------------------------------------

def _opens_sentence(kept: str) -> bool:
    end = kept.rstrip()
    return not end or end[-1] in ".!?…"


def _remove(text: str, pattern: re.Pattern) -> str:
    kept, resume, capital_due = "", 0, False

    def append(segment):
        nonlocal kept, capital_due
        if capital_due:
            for j, c in enumerate(segment):
                if c.isalnum():
                    capital_due = False
                    kept += segment[:j] + c.upper() + segment[j + 1:]
                    return
        kept += segment

    for m in pattern.finditer(text):
        append(text[resume:m.start()])
        capital_due |= m.group(0)[:1].isupper() and _opens_sentence(kept)
        resume = m.end()
    append(text[resume:])
    return kept


def remove_fillers(text: str, language: str | None) -> str:
    fillers = UNIVERSAL_FILLERS + FILLERS_BY_LANGUAGE.get((language or "").split("-")[0].split("_")[0], ())
    for word in fillers:
        text = _remove(text, re.compile(rf"(?i)\b{re.escape(word)}\b[,.]?"))
    return text


# --- Normalization --------------------------------------------------------------------------------

def collapse_stutters(text: str) -> str:
    """An alphabetic word repeated 3 times or more in a row (case ignored) is kept only once."""
    words = text.split()
    out, i = [], 0
    while i < len(words):
        w = words[i]
        n = 1
        if w.isalpha():
            while i + n < len(words) and words[i + n].lower() == w.lower():
                n += 1
        out.append(w)
        i += n if n >= 3 else 1
    return " ".join(out)


def clean(text: str, language: str | None, custom_words=()) -> str:
    text = apply_custom_words(text, list(custom_words))
    text = remove_fillers(text, language)
    text = collapse_stutters(text)
    return re.sub(r"\s{2,}", " ", text).strip()
