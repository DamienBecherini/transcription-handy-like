"""Transcription horodatée (pour des sous-titres) : les positions d'origine sont conservées.

Contrairement à la dictée (vad.py : les silences sont retirés puis la parole est recollée), on garde la
ligne de temps de l'enregistrement : les segments de parole trouvés par Silero sont regroupés en morceaux
de 40 s au plus (comme la dictée longue), chaque morceau est transcrit avec les horodatages de mots de
Parakeet (timestamps="word"), et le décalage du morceau est ajouté à chaque mot.
"""
from dataclasses import dataclass

from . import texte

TAUX = 16000
MAXIMUM = 40 * TAUX          # un morceau : 40 s au plus (comme decoupage.UN_SEUL)
CIBLE = 30 * TAUX            # coupe franche d'un segment de parole trop long sans pause
MARGE = int(0.2 * TAUX)      # silence gardé de part et d'autre d'un morceau (bornes des mots plus justes)


@dataclass
class Mot:
    texte: str
    debut: float   # secondes depuis le début de l'enregistrement
    fin: float


def regrouper(segments, longueur, maximum=MAXIMUM, cible=CIBLE, marge=MARGE):
    """Morceaux (début, fin) en échantillons à transcrire, à partir des segments de parole (début, fin).

    Des segments voisins sont réunis tant que le morceau ne dépasse pas `maximum` ; un segment plus long
    que `maximum` à lui seul est coupé franchement par tranches de `cible`. Chaque morceau est élargi de
    `marge` dans le silence qui l'entoure, sans mordre sur le voisin ni sortir de l'enregistrement.
    """
    morceaux = []
    for a, b in segments:
        a, b = max(0, a), min(b, longueur)
        if b <= a:
            continue
        while b - a > maximum:
            morceaux.append((a, a + cible))
            a += cible
        if morceaux and b - morceaux[-1][0] <= maximum:
            morceaux[-1] = (morceaux[-1][0], b)
        else:
            morceaux.append((a, b))
    elargis = []
    for i, (a, b) in enumerate(morceaux):
        prec = morceaux[i - 1][1] if i else 0
        suiv = morceaux[i + 1][0] if i + 1 < len(morceaux) else longueur
        a2 = max(a - marge, (a + prec) // 2 if i else 0)
        b2 = min(b + marge, (b + suiv) // 2 if i + 1 < len(morceaux) else longueur)
        elargis.append((a2, b2))
    return elargis


def est_remplissage(mot: str, langue: str | None) -> bool:
    """Mot de remplissage (« euh », « uh »…) à retirer, selon la même liste que la dictée."""
    base = texte.cle(mot)
    if not base:
        return False
    liste = texte.REMPLISSAGE_UNIVERSEL + texte.REMPLISSAGE_PAR_LANGUE.get((langue or "").split("-")[0].split("_")[0], ())
    return base in {texte.cle(m) for m in liste}


def nettoyer_mots(mots: list[Mot], langue: str | None) -> list[Mot]:
    """Retire les mots de remplissage et les mots vides ; garantit fin > début et l'ordre chronologique."""
    sortie: list[Mot] = []
    for m in mots:
        t = m.texte.strip()
        if not t or est_remplissage(t, langue):
            continue
        debut = max(m.debut, sortie[-1].fin if sortie else 0.0)
        fin = max(m.fin, debut + 0.05)
        sortie.append(Mot(t, round(debut, 3), round(fin, 3)))
    return sortie
