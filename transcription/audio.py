"""Décodage de l'audio reçu (WebM/Opus du navigateur, WAV, MP3, M4A…) en PCM float32 16 kHz mono, par ffmpeg."""
import os
import subprocess
import tempfile

import numpy as np

TAUX = 16000


class AudioInvalide(ValueError):
    pass


def decoder(donnees: bytes, delai_s: float | None = None) -> np.ndarray:
    """Le fichier passe par le disque et non par un tube : ffmpeg doit pouvoir y revenir en arrière
    (MP4/MOV dont l'index « moov » est à la fin, sinon il ne sort rien sans se plaindre)."""
    if delai_s is None:
        delai_s = 60 + len(donnees) / 1_000_000   # une seconde de plus par Mo (une heure d'audio ≈ 60 Mo)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(donnees)
        chemin = f.name
    try:
        r = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", chemin,
             "-vn", "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(TAUX), "pipe:1"],
            capture_output=True, timeout=delai_s, check=False)
    except subprocess.TimeoutExpired as e:
        raise AudioInvalide("décodage trop long") from e
    finally:
        os.unlink(chemin)
    if r.returncode != 0:
        raise AudioInvalide(r.stderr.decode(errors="replace").strip()[-300:] or "ffmpeg a échoué")
    pcm = np.frombuffer(r.stdout, dtype=np.float32).copy()
    if len(pcm) == 0:
        raise AudioInvalide("aucune piste audio lisible")
    return pcm
