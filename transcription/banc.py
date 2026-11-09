"""Compare les quantifications de Parakeet Ultra sur des enregistrements : temps et texte.

    python -m transcription.banc [--quantifications Q8_0 Q5_K_M …] [--repetitions 3] <fichiers audio>…

Chaque fichier passe par toute la chaîne du serveur (ffmpeg, détection de voix, Parakeet, nettoyage).
Affiche la médiane du temps de transcription et le texte, en signalant ce qui diffère de la première
quantification de la liste (la référence, Q8_0 par défaut).
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

from . import audio, modeles
from .moteur import Moteur


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--quantifications", nargs="+", default=list(modeles.ASR_VARIANTES),
                   choices=list(modeles.ASR_VARIANTES))
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--langue", default="fr")
    p.add_argument("fichiers", nargs="+")
    a = p.parse_args()

    sons = {Path(f).name: audio.decoder(Path(f).read_bytes()) for f in a.fichiers}
    reference = {}
    for q in a.quantifications:
        t = time.perf_counter()
        moteur = Moteur(quantification=q)
        taille = modeles.obtenir(modeles.ASR_VARIANTES[q]).stat().st_size / 1e6
        print(f"\n=== {q} ({taille:.0f} Mo, prêt en {time.perf_counter() - t:.1f} s)", flush=True)
        for nom, pcm in sons.items():
            temps, r = [], None
            moteur.transcrire(pcm, a.langue)  # tour de chauffe
            for _ in range(a.repetitions):
                t = time.perf_counter()
                r = moteur.transcrire(pcm, a.langue)
                temps.append(time.perf_counter() - t)
            reference.setdefault(nom, r.texte)
            marque = "=" if r.texte == reference[nom] else "≠"
            print(f"  {nom:28} {r.duree_audio:5.1f} s  {statistics.median(temps):5.2f} s  {marque} {r.texte}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
