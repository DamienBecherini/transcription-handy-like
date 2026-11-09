"""Serveur HTTP compatible avec l'API de transcription d'OpenAI (POST /v1/audio/transcriptions).

Deux modes selon response_format :
  json / text            dictée (chaîne de Handy : silences retirés, mots personnalisés, « euh ») ;
  verbose_json           sous-titres : mots horodatés sur la ligne de temps d'origine (champ « words »,
                         comme timestamp_granularities=word chez OpenAI) et un « segment » par morceau transcrit.

Variables d'environnement :
  TRANSCRIPTION_CLE_API     si définie, exigée en « Authorization: Bearer … » sur /v1/*
  TRANSCRIPTION_MOTS        fichier des mots personnalisés (un par ligne), relu s'il change
  TRANSCRIPTION_LANGUE      langue supposée quand la requête n'en donne pas (sert au retrait de « euh »)
  TRANSCRIPTION_FILS        fils de calcul pour Parakeet (0 = automatique)
Le texte transcrit n'est jamais écrit dans le journal, seulement les durées.
"""
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from . import audio
from .moteur import Moteur

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("transcription")

NOM_MODELE = "parakeet-ultra"
CLE_API = os.environ.get("TRANSCRIPTION_CLE_API", "")
LANGUE = os.environ.get("TRANSCRIPTION_LANGUE", "") or None
moteur: Moteur | None = None


@asynccontextmanager
async def cycle(_app):
    global moteur
    moteur = await run_in_threadpool(Moteur, os.environ.get("TRANSCRIPTION_MOTS"),
                                     int(os.environ.get("TRANSCRIPTION_FILS", "0")))
    yield


app = FastAPI(title="transcription-handy-like", lifespan=cycle)


def verifier_cle(authorization: str | None):
    if CLE_API and authorization != f"Bearer {CLE_API}":
        raise HTTPException(401, "clé API invalide")


@app.get("/health")
async def sante():
    return {"etat": "pret" if moteur else "chargement"}


@app.get("/v1/models")
async def modeles(authorization: str | None = Header(None)):
    verifier_cle(authorization)
    return {"object": "list", "data": [{"id": NOM_MODELE, "object": "model", "owned_by": "local"}]}


@app.post("/v1/audio/transcriptions")
async def transcriptions(file: UploadFile = File(...), model: str = Form(NOM_MODELE),
                         language: str | None = Form(None), prompt: str | None = Form(None),
                         response_format: str = Form("json"), temperature: float | None = Form(None),
                         authorization: str | None = Header(None)):
    verifier_cle(authorization)
    if moteur is None:
        raise HTTPException(503, "modèles en cours de chargement")
    t0 = time.perf_counter()
    donnees = await file.read()
    try:
        pcm = await run_in_threadpool(audio.decoder, donnees)
    except audio.AudioInvalide as e:
        raise HTTPException(400, f"audio illisible : {e}") from e
    t_decodage = time.perf_counter() - t0
    langue = language or LANGUE
    if response_format == "verbose_json":
        h = await run_in_threadpool(moteur.transcrire_horodate, pcm, language or None)
        total = time.perf_counter() - t0
        log.info("horodaté : audio %.1f s, %s morceau(x), %d mots | décodage %.2f s, vad %.2f s, asr %.2f s, total %.2f s",
                 h.duree_audio, h.temps.get("morceaux", 0), len(h.mots), t_decodage, h.temps.get("vad", 0),
                 h.temps.get("asr", 0), total)
        return {"task": "transcribe", "language": h.langue or "", "duration": h.duree_audio, "text": h.texte,
                "segments": [{"id": i, "start": round(a, 3), "end": round(b, 3), "text": t}
                             for i, (a, b, t) in enumerate(h.morceaux)],
                "words": [{"word": m.texte, "start": m.debut, "end": m.fin} for m in h.mots]}
    r = await run_in_threadpool(moteur.transcrire, pcm, langue)
    total = time.perf_counter() - t0
    log.info("audio %.1f s, parole %.1f s, %s morceau(x) | décodage %.2f s, vad %.2f s, asr %.2f s, total %.2f s",
             r.duree_audio, r.duree_parole, r.temps.get("morceaux", 0), t_decodage,
             r.temps.get("vad", 0), r.temps.get("asr", 0), total)

    if response_format == "text":
        return PlainTextResponse(r.texte)
    if response_format in ("srt", "vtt"):
        raise HTTPException(400, "formats srt/vtt non pris en charge : demander verbose_json et construire les sous-titres côté client")
    return {"text": r.texte}
