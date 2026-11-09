"""Repère les faux remplacements d'une liste de mots personnalisés, sur un corpus de textes en français.

    python -m transcription.verifier_mots <mots.txt> <dossier ou fichiers .md/.txt>...

Chaque mot du corpus (et chaque suite de 2 ou 3 mots) passe par la correction des mots personnalisés ;
tout ce qui serait remplacé alors que ce n'est pas déjà le mot personnalisé est listé, avec son nombre
d'occurrences. Un mot qui provoque des remplacements de mots courants est à retirer de la liste.
"""
import re
import sys
from collections import Counter
from pathlib import Path

from .texte import appliquer_mots_personnalises, cle


def lire_mots(chemin):
    lignes = Path(chemin).read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lignes if l.strip() and not l.lstrip().startswith("#")]


def fichiers(chemins):
    for c in map(Path, chemins):
        if c.is_dir():
            yield from (f for f in c.rglob("*") if f.suffix in (".md", ".txt") and ".git" not in f.parts)
        else:
            yield c


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    mots = lire_mots(sys.argv[1])
    cles_mots = {cle(m) for m in mots}
    groupes = Counter()
    for f in fichiers(sys.argv[2:]):
        elements = re.findall(r"[\w'’-]+", f.read_text(encoding="utf-8", errors="ignore"))
        for n in (1, 2, 3):
            for i in range(len(elements) - n + 1):
                groupes[" ".join(elements[i:i + n])] += 1
    faux = Counter()
    par_mot = {m: Counter() for m in mots}
    for g, nb in groupes.items():
        if cle(g.replace(" ", "")) in cles_mots:
            continue  # déjà le mot personnalisé (casse ou tiret près)
        r = appliquer_mots_personnalises(g, mots)
        if r == g:
            continue
        faux[(g, r)] += nb
        for m in mots:
            if m in r and m not in g:
                par_mot[m][g] += nb

    print("Par mot personnalisé (occurrences remplacées à tort, exemples) :")
    for m, c in sorted(par_mot.items(), key=lambda x: -sum(x[1].values())):
        exemples = ", ".join(f"« {g} »" for g, _ in c.most_common(4))
        print(f"  {sum(c.values()):6}  {m:15} {exemples}")
    print(f"{len(faux)} remplacement(s) douteux sur {len(groupes)} groupes de mots")
    return 0


if __name__ == "__main__":
    sys.exit(main())
