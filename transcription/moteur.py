"""Chaîne de transcription : PCM 16 kHz → détection de voix → (découpage) → Parakeet Ultra → nettoyage du texte."""
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import transcribe_cpp

from . import decoupage, horodatage, modeles, texte, vad

log = logging.getLogger("transcription")
TAUX = 16000


@dataclass
class Resultat:
    texte: str
    duree_audio: float          # secondes reçues
    duree_parole: float         # secondes gardées après détection de voix (avant complément)
    temps: dict = field(default_factory=dict)


@dataclass
class ResultatHorodate:
    mots: list[horodatage.Mot]
    morceaux: list[tuple[float, float, str]]   # (début, fin, texte) de chaque morceau transcrit
    langue: str | None
    duree_audio: float
    temps: dict = field(default_factory=dict)

    @property
    def texte(self) -> str:
        return " ".join(m.texte for m in self.mots)


class MotsPersonnalises:
    """Fichier texte, un mot ou une expression par ligne (# pour un commentaire) ; relu s'il change."""

    def __init__(self, chemin: str | None):
        self.chemin = Path(chemin) if chemin else None
        self._date = None
        self._mots: list[str] = []

    def liste(self) -> list[str]:
        if not self.chemin or not self.chemin.exists():
            return []
        date = self.chemin.stat().st_mtime
        if date != self._date:
            lignes = self.chemin.read_text(encoding="utf-8").splitlines()
            self._mots = [l.strip() for l in lignes if l.strip() and not l.lstrip().startswith("#")]
            self._date = date
            log.info("mots personnalisés : %d", len(self._mots))
        return self._mots


class Moteur:
    def __init__(self, mots_personnalises: str | None = None, fils: int = 0, quantification: str = "Q8_0"):
        cpu = next(d for d in transcribe_cpp.backends() if d.device_type == "cpu")
        t = time.perf_counter()
        self.asr = transcribe_cpp.Model(modeles.obtenir(modeles.ASR_VARIANTES[quantification]), device=cpu)
        self.silero = transcribe_cpp.Model(modeles.obtenir(modeles.VAD), device=cpu)
        self.session = self.asr.session(n_threads=fils)
        self.session_vad = self.silero.vad_session(n_threads=1)
        self.trame = self.silero.vad_info.frame_samples
        self.verrou = threading.Lock()   # une transcription à la fois : le processeur est déjà occupé à 100 %
        self.mots = MotsPersonnalises(mots_personnalises)
        log.info("modèles chargés en %.1f s (trame VAD %d)", time.perf_counter() - t, self.trame)

    def transcrire(self, pcm: np.ndarray, langue: str | None) -> Resultat:
        temps = {}
        with self.verrou:
            t = time.perf_counter()
            probs = self.session_vad.run(pcm).probs
            parole = vad.garder_parole(pcm, probs, self.trame)
            temps["vad"] = time.perf_counter() - t
            res = Resultat("", len(pcm) / TAUX, len(parole) / TAUX, temps)
            if len(parole) == 0:
                return res

            t = time.perf_counter()
            parole = vad.completer(parole)
            morceaux = [parole]
            if len(parole) > decoupage.UN_SEUL:
                seg = self.session_vad.run(parole, threshold=0.5, neg_threshold=0.35, min_speech_ms=250,
                                           min_silence_ms=100, speech_pad_ms=30).segments
                bornes = [0, *decoupage.coupes(len(parole), decoupage.pauses(seg, len(parole))), len(parole)]
                morceaux = [parole[a:b] for a, b in zip(bornes, bornes[1:])]
            textes = [self.session.run(m).text.strip() for m in morceaux]
            temps["asr"] = time.perf_counter() - t
            temps["morceaux"] = len(morceaux)

        t = time.perf_counter()
        res.texte = texte.nettoyer(" ".join(x for x in textes if x), langue, self.mots.liste())
        temps["texte"] = time.perf_counter() - t
        return res

    def transcrire_horodate(self, pcm: np.ndarray, langue: str | None) -> ResultatHorodate:
        """Mots horodatés sur la ligne de temps d'origine (sous-titres) : voir horodatage.py.
        Pas de mots personnalisés ici (ils réécrivent des groupes de mots), seulement les mots de remplissage."""
        temps = {}
        with self.verrou:
            t = time.perf_counter()
            seg = self.session_vad.run(pcm, threshold=0.5, neg_threshold=0.35, min_speech_ms=250,
                                       min_silence_ms=100, speech_pad_ms=30).segments
            morceaux = horodatage.regrouper([(x.start_sample, x.end_sample) for x in seg], len(pcm))
            temps["vad"] = time.perf_counter() - t
            t = time.perf_counter()
            mots, details, langue_vue = [], [], None
            for a, b in morceaux:
                r = self.session.run(pcm[a:b], timestamps="word")
                decalage = a / TAUX
                mots.extend(horodatage.Mot(w.text, decalage + w.t0_ms / 1000, decalage + w.t1_ms / 1000)
                            for w in r.words)
                details.append((a / TAUX, b / TAUX, r.text.strip()))
                langue_vue = langue_vue or getattr(r, "language", None)
            temps["asr"] = time.perf_counter() - t
            temps["morceaux"] = len(morceaux)
        langue_finale = langue or langue_vue or None
        return ResultatHorodate(horodatage.nettoyer_mots(mots, langue_finale), details, langue_finale,
                                len(pcm) / TAUX, temps)
