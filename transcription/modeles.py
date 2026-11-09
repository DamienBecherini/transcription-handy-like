"""Modèles GGUF utilisés, épinglés comme dans le catalogue de Handy v0.10.0 (dépôt, révision, empreinte sha256).

Téléchargés au premier démarrage dans le cache Hugging Face (volume persistant dans Docker),
puis vérifiés par leur empreinte à chaque démarrage.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import hf_hub_download


@dataclass(frozen=True)
class Fichier:
    depot: str
    revision: str
    nom: str
    sha256: str


_ULTRA = ("handy-computer/parakeet-ultra-gguf", "39eeb55181f0d354fd934f06e92fd8d5037fed8e")
# Quantifications publiées (catalogue de Handy) ; Q8_0 est celle de Handy et la valeur par défaut.
ASR_VARIANTES = {
    "Q8_0": Fichier(*_ULTRA, "parakeet-ultra-Q8_0.gguf", "007a59761e9258779f189df396b50d12b83bb5b79e66df4b955c230d2f2a0a59"),
    "Q6_K": Fichier(*_ULTRA, "parakeet-ultra-Q6_K.gguf", "ba146253d9b5eb7c729dfa897174cb5bad0a7d05129863805e0caf7d571c7493"),
    "Q5_K_M": Fichier(*_ULTRA, "parakeet-ultra-Q5_K_M.gguf", "f6e3d8172547a3bb468e92ff395696e6d2e0371a9e52690a27741b4e8561c997"),
    "Q4_K_M": Fichier(*_ULTRA, "parakeet-ultra-Q4_K_M.gguf", "c69b7a5f9071a7afd8a1818ef7ae542c386c4b01ed0cac380c19a99947646bf9"),
}
ASR = ASR_VARIANTES["Q8_0"]
LANGID = Fichier("handy-computer/lang-id-voxlingua107-ecapa-gguf", "41cf26039e317c6b8883bf0a61b0785dc663fc26",
                 "lang-id-voxlingua107-ecapa-F16.gguf", "1f4f1a8279a3bf6eef63ff1fe2b6e5328adb184d43cacab55557592b6197530e")
VAD = Fichier("handy-computer/silero-vad-v6.2-gguf", "97bbd75179f535e4708bccdf61e9278b8b60dfc7",
              "silero-vad-v6.2-F32.gguf", "0d871a800c420fdd5d1b17a3aea4296d1c39608f0ff4a9295eb76457eb1c88e6")


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def obtenir(fichier: Fichier) -> Path:
    """Chemin local du fichier, téléchargé s'il manque ; refuse un fichier dont l'empreinte ne correspond pas."""
    chemin = Path(hf_hub_download(fichier.depot, fichier.nom, revision=fichier.revision))
    if empreinte(chemin) != fichier.sha256:
        raise RuntimeError(f"{fichier.nom} : empreinte sha256 inattendue ({chemin})")
    return chemin
