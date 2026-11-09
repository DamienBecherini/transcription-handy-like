"""Nettoyage du texte transcrit, comme Handy v0.10.0 (src-tauri/src/audio_toolkit/text.rs).

Ordre : mots personnalisés (correction floue), mots de remplissage, bégaiements, espaces.
"""
import re

SEUIL_MOTS = 0.18   # word_correction_threshold par défaut de Handy

# Jamais des mots dans aucune langue : retirés toujours.
REMPLISSAGE_UNIVERSEL = ("uh", "uhm", "umm", "uhh", "uhhh", "ehh", "ehm", "ahm", "hmm", "hm", "mmm", "хм", "ммм")
# Retirés seulement quand la langue du texte est connue.
REMPLISSAGE_PAR_LANGUE = {"en": ("um", "ah", "eh"), "de": ("äh", "ähm"), "fr": ("euh",)}


# --- Mots personnalisés -------------------------------------------------------------------------

def cle(mot: str) -> str:
    """Clé de comparaison : minuscules, lettres et chiffres seulement. Comme Handy, un mot accentué donne une
    clé non ASCII, que la correction ignore. Essayé et abandonné : retirer les accents faisait remplacer
    « gîte » et « gâteau » par « Gitea »."""
    return "".join(c for c in mot.lower() if c.isalnum())


def _ascii_alnum(s: str) -> bool:
    return bool(s) and s.isascii() and s.isalnum()


def _ascii_alpha(s: str) -> bool:
    return bool(s) and s.isascii() and s.isalpha()


def levenshtein(a: str, b: str) -> int:
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cour = [i]
        for j, cb in enumerate(b, 1):
            cour.append(min(prec[j] + 1, cour[j - 1] + 1, prec[j - 1] + (ca != cb)))
        prec = cour
    return prec[-1]


_SOUNDEX = {**dict.fromkeys("bfpv", "1"), **dict.fromkeys("cgjkqsxz", "2"), **dict.fromkeys("dt", "3"),
            "l": "4", **dict.fromkeys("mn", "5"), "r": "6"}


def soundex(mot: str) -> str:
    """Soundex américain (h et w ne séparent pas deux codes identiques, les voyelles si)."""
    mot = mot.lower()
    code = mot[0].upper()
    prec = _SOUNDEX.get(mot[0], "")
    for c in mot[1:]:
        chiffre = _SOUNDEX.get(c, "")
        if chiffre and chiffre != prec:
            code += chiffre
        if c not in "hw":
            prec = chiffre
    return (code + "000")[:4]


def _cles_mots(mots):
    cles = []
    for i, mot in enumerate(mots):
        k = cle(mot)
        if _ascii_alnum(k):
            cles.append((i, k))
        if "&" in mot:
            k2 = cle(mot.replace("&", " and "))
            if _ascii_alnum(k2) and k2 != k:
                cles.append((i, k2))
    return cles


def _meilleur(candidat, mots, cles, seuil):
    if not _ascii_alnum(candidat) or len(candidat) > 50:
        return None
    meilleur, score_min = None, float("inf")
    for i, k in cles:
        ecart = abs(len(candidat) - len(k))
        lmax = max(len(candidat), len(k))
        if ecart > max(lmax * 0.25, 2.0):
            continue
        score = levenshtein(candidat, k) / lmax if lmax else 1.0
        if _ascii_alpha(candidat) and _ascii_alpha(k) and soundex(candidat) == soundex(k):
            score *= 0.3
        if score < seuil and score < score_min:
            meilleur, score_min = mots[i], score
    return (meilleur, score_min) if meilleur is not None else None


def _ponctuation(mot: str):
    debut = next((i for i, c in enumerate(mot) if c.isalnum()), len(mot))
    fin = next((i + 1 for i in range(len(mot) - 1, -1, -1) if mot[i].isalnum()), 0)
    return mot[:debut], mot[fin:] if fin < len(mot) else ""


def _casse(original: str, remplacement: str) -> str:
    if original and all(c.isupper() for c in original):
        return remplacement.upper()
    if original[:1].isupper():
        return remplacement[:1].upper() + remplacement[1:]
    return remplacement


def appliquer_mots_personnalises(texte: str, mots, seuil: float = SEUIL_MOTS) -> str:
    """Remplace les n-grammes (1 à 3 mots) proches d'un mot personnalisé (Levenshtein + Soundex)."""
    if not mots:
        return texte
    cles = _cles_mots(mots)
    elements = texte.split()
    sortie, i = [], 0
    while i < len(elements):
        trouve = None
        for n in (3, 2, 1):
            if i + n > len(elements):
                continue
            groupe = elements[i:i + n]
            if any(_ponctuation(m)[1] for m in groupe[:-1]):
                continue  # ne pas franchir une ponctuation
            r = _meilleur("".join(cle(m) for m in groupe), mots, cles, seuil)
            if r and (trouve is None or r[1] < trouve[2]):
                trouve = (n, r[0], r[1])
        if trouve:
            n, remplacement, _ = trouve
            prefixe, _ = _ponctuation(elements[i])
            _, suffixe = _ponctuation(elements[i + n - 1])
            sortie.append(prefixe + _casse(elements[i], remplacement) + suffixe)
            i += n
        else:
            sortie.append(elements[i])
            i += 1
    return " ".join(sortie)


# --- Mots de remplissage --------------------------------------------------------------------------

def _ouvre_phrase(garde: str) -> bool:
    fin = garde.rstrip()
    return not fin or fin[-1] in ".!?…"


def _retirer(texte: str, motif: re.Pattern) -> str:
    garde, reprise, majuscule_due = "", 0, False

    def ajouter(segment):
        nonlocal garde, majuscule_due
        if majuscule_due:
            for j, c in enumerate(segment):
                if c.isalnum():
                    majuscule_due = False
                    garde += segment[:j] + c.upper() + segment[j + 1:]
                    return
        garde += segment

    for m in motif.finditer(texte):
        ajouter(texte[reprise:m.start()])
        majuscule_due |= m.group(0)[:1].isupper() and _ouvre_phrase(garde)
        reprise = m.end()
    ajouter(texte[reprise:])
    return garde


def retirer_remplissage(texte: str, langue: str | None) -> str:
    mots = REMPLISSAGE_UNIVERSEL + REMPLISSAGE_PAR_LANGUE.get((langue or "").split("-")[0].split("_")[0], ())
    for mot in mots:
        texte = _retirer(texte, re.compile(rf"(?i)\b{re.escape(mot)}\b[,.]?"))
    return texte


# --- Normalisation ------------------------------------------------------------------------------

def reduire_begaiements(texte: str) -> str:
    """Un mot alphabétique répété 3 fois ou plus d'affilée (même casse ignorée) n'est gardé qu'une fois."""
    mots = texte.split()
    sortie, i = [], 0
    while i < len(mots):
        m = mots[i]
        n = 1
        if m.isalpha():
            while i + n < len(mots) and mots[i + n].lower() == m.lower():
                n += 1
        sortie.append(m)
        i += n if n >= 3 else 1
    return " ".join(sortie)


def nettoyer(texte: str, langue: str | None, mots_personnalises=()) -> str:
    texte = appliquer_mots_personnalises(texte, list(mots_personnalises))
    texte = retirer_remplissage(texte, langue)
    texte = reduire_begaiements(texte)
    return re.sub(r"\s{2,}", " ", texte).strip()
