"""Détection de voix comme Handy v0.10.0 : Silero VAD v6.2, puis lissage, et on ne garde que la parole.

Repris de Handy (src-tauri/src/audio_toolkit/vad/smoothed.rs, managers/audio.rs, audio/sink.rs) :
- trame de 512 échantillons (32 ms), parole si probabilité > 0,3 ;
- pré-roll 450 ms (15 trames), démarrage après 2 trames voisées, maintien 450 ms (15 trames) ;
- toutes les trames non retenues sont retirées, y compris au milieu de l'enregistrement ;
- moins de 1 s de parole : complété par des zéros jusqu'à 1,25 s.
Handy lit les probabilités au fil de l'enregistrement ; ici l'enregistrement est entier, on les calcule
d'une traite (même état récurrent, trame après trame) puis on applique le même automate.
"""
from collections import deque

import numpy as np

SEUIL = 0.3
PREROLL = 15
DEMARRAGE = 2
MAINTIEN = 15
TAUX = 16000
MIN_AVANT_COMPLEMENT = TAUX          # 1 s
LONGUEUR_COMPLEMENT = 20000          # 1,25 s


def trames_retenues(probs, seuil=SEUIL, preroll=PREROLL, demarrage=DEMARRAGE, maintien=MAINTIEN):
    """Indices des trames gardées, dans l'ordre (automate SmoothedVad de Handy)."""
    gardees = []
    tampon = deque()            # [indice, émise] des dernières trames, pré-roll compris
    en_parole = False
    compteur_demarrage = 0
    compteur_maintien = 0
    for i, p in enumerate(probs):
        tampon.append([i, False])
        while len(tampon) > preroll + 1:
            tampon.popleft()
        voix = p > seuil
        if not en_parole and voix:
            compteur_demarrage += 1
            if compteur_demarrage >= demarrage:
                en_parole = True
                compteur_maintien = maintien
                compteur_demarrage = 0
                for t in tampon:
                    if not t[1]:
                        gardees.append(t[0])
                        t[1] = True
        elif en_parole and voix:
            compteur_maintien = maintien
            tampon[-1][1] = True
            gardees.append(i)
        elif en_parole:
            if compteur_maintien > 0:
                compteur_maintien -= 1
                tampon[-1][1] = True
                gardees.append(i)
            else:
                en_parole = False
        else:
            compteur_demarrage = 0
    return gardees


def garder_parole(pcm: np.ndarray, probs, taille_trame: int) -> np.ndarray:
    """Concatène les trames retenues (la dernière trame incomplète n'a pas de probabilité : ignorée, comme Handy)."""
    indices = trames_retenues(probs)
    if not indices:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate([pcm[i * taille_trame:(i + 1) * taille_trame] for i in indices]).astype(np.float32)


def completer(pcm: np.ndarray) -> np.ndarray:
    """Parole de moins de 1 s : zéros jusqu'à 1,25 s (le modèle se trompe sur les extraits très courts)."""
    if 0 < len(pcm) < MIN_AVANT_COMPLEMENT:
        return np.concatenate([pcm, np.zeros(LONGUEUR_COMPLEMENT - len(pcm), dtype=np.float32)])
    return pcm
