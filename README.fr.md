<div align="center">

# transcription-handy-like

**Transcription auto-hébergée sur le processeur, derrière une API compatible OpenAI, avec les mots horodatés.**

[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)](compose.yaml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![OpenAI-compatible API](https://img.shields.io/badge/API-OpenAI--compatible-412991)](#utiliser-lapi)
[![Parakeet](https://img.shields.io/badge/model-Parakeet%20Ultra-76B900?logo=nvidia&logoColor=white)](THIRD_PARTY_NOTICES.md)
[![CPU only](https://img.shields.io/badge/GPU-not%20needed-2EA043)](#démarrage-rapide-sur-votre-ordinateur)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Français** · [English](README.md)

</div>

---

Serveur de transcription auto-hébergé, compatible avec l'API d'OpenAI (`POST /v1/audio/transcriptions`). Il tourne sur le processeur avec le modèle **Parakeet Ultra** (25 langues européennes) et renvoie les mots horodatés.

C'est le serveur recommandé pour **[auto-generate-subtitles](https://github.com/DamienBecherini/auto-generate-subtitles)**, qui produit les sous-titres de vos vidéos. Il fonctionne aussi seul avec tout client compatible OpenAI, comme Open WebUI.

Il reproduit la chaîne de [Handy](https://github.com/cjpais/Handy), l'application de dictée pour ordinateur. Handy n'a pas d'API HTTP et ne peut donc pas jouer ce rôle.

## Démarrage rapide sur votre ordinateur

Il faut [Docker Desktop](https://www.docker.com/products/docker-desktop/) sous Windows ou macOS, ou Docker sous Linux.

```
git clone https://github.com/DamienBecherini/transcription-handy-like.git
cd transcription-handy-like
docker compose up -d
```

Le premier démarrage télécharge environ 1 Go de modèles. Pour vérifier que le serveur est prêt :

```
curl http://127.0.0.1:8000/health
```

La réponse est `{"etat":"chargement"}` pendant le chargement, puis `{"etat":"pret"}`. Le serveur n'accepte que les connexions de votre ordinateur et ne demande pas de clé.

**Ensuite :** [installez auto-generate-subtitles](https://github.com/DamienBecherini/auto-generate-subtitles/blob/main/README.fr.md#démarrage-rapide). Il cherche ce serveur sur `http://127.0.0.1:8000` par défaut.

## Installation sur un serveur ou un VPS

```
git clone https://github.com/DamienBecherini/transcription-handy-like.git
cd transcription-handy-like
./install.sh
```

Le script demande le port, qui peut joindre le serveur, la clé API, la limite de mémoire et l'emplacement des modèles. Sous Linux, il propose d'installer Docker si besoin, écrit vos réponses dans `.env`, démarre le service et attend qu'il soit prêt.

Pour installer sans questions, copiez `.env.example`, remplissez-le, puis lancez `./install.sh --config mes-reglages.env`.

Prévoyez 3 Go de mémoire et 4 Go de disque. Un enregistrement de 31 minutes a été testé avec une limite de 2 Go, presque atteinte.

**Si d'autres machines peuvent le joindre :** le script refuse de démarrer sans clé API et en génère une, gardée dans `.env`. L'audio circule en clair en HTTP : placez HTTPS devant le serveur (Caddy, nginx, Traefik) et limitez l'accès au port par votre pare-feu.

Pour mettre à jour : `git pull`, puis de nouveau `./install.sh`. Pour arrêter : `docker compose down`.

## Utiliser l'API

```
curl http://127.0.0.1:8000/v1/audio/transcriptions -F file=@audio.mp3
curl http://127.0.0.1:8000/v1/audio/transcriptions -F file=@audio.mp3 -F response_format=verbose_json
```

Avec une clé API, ajoutez `-H "Authorization: Bearer <clé>"`.

## Sans Docker

Python 3.12 et `ffmpeg` dans le `PATH` :

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt       # Windows : .venv/Scripts/pip
.venv/bin/python -m uvicorn transcription.serveur:app --port 8000
```

Sous Windows, le contrôle intelligent des applications peut bloquer les bibliothèques natives non signées (`WinError 4551`). Utilisez alors Docker.

Variables : `TRANSCRIPTION_CLE_API`, `TRANSCRIPTION_MOTS`, `TRANSCRIPTION_LANGUE`, `TRANSCRIPTION_FILS` (voir `transcription/serveur.py`). Le texte transcrit n'est jamais journalisé.

## Chaîne (comme Handy)

1. Décodage par ffmpeg (WebM/Opus du navigateur, WAV, MP3, M4A…) en PCM 16 kHz mono (`audio.py`).
2. Détection de voix Silero VAD v6.2 : seuil 0,3, pré-roll 450 ms, démarrage 2 trames, maintien 450 ms ; seule la parole est gardée, silences du milieu compris ; aucune parole → texte vide ; moins de 1 s → complété jusqu'à 1,25 s (`vad.py`).
3. Au-delà de 40 s : découpage au milieu des pauses, morceaux de 5 à 40 s, 30 s visés (`decoupage.py`).
4. Parakeet Ultra Q8_0 par transcribe.cpp, langue détectée par le modèle : le paramètre `language` n'a pas d'effet sur Ultra (documentation de transcribe.cpp) ; il sert seulement au point 5.
5. Nettoyage du texte (`texte.py`) : mots personnalisés (Levenshtein + Soundex, seuil 0,18), mots de remplissage (universels, plus « euh » si la langue est le français), mot répété 3 fois ou plus, espaces.

Modèles épinglés (dépôt, révision, sha256) comme dans le catalogue de Handy (`modeles.py`), téléchargés au premier démarrage puis vérifiés.

## Mode sous-titres : mots horodatés (`response_format=verbose_json`)

Pour les sous-titres (projet `auto-generate-subtitles`), la chaîne de dictée ne convient pas : elle retire les
silences et recolle la parole, les temps sont perdus. En `verbose_json`, le serveur garde la ligne de temps de
l'enregistrement (`horodatage.py`) : segments de parole de Silero (seuil 0,5, pauses de 100 ms) regroupés en
morceaux de 40 s au plus, élargis de 0,2 s dans le silence voisin ; chaque morceau transcrit avec
`timestamps="word"` (Parakeet Ultra donne des horodatages par jeton), décalage du morceau ajouté. Réponse au
format d'OpenAI : `language`, `duration`, `text`, `segments` (un par morceau), `words` (`word`, `start`, `end`).
Mots de remplissage retirés ; pas de mots personnalisés dans ce mode (ils réécrivent des groupes de mots).
Le fichier reçu passe par le disque avant ffmpeg (un MP4 dont l'index est à la fin ne se lit pas par un tube).
Le modèle ne renvoie pas la langue (`language` vide) : le client la devine. Mesuré sur le PC : 22 s d'audio
en 1,3 s, mots datés à 40 ms près.

## Mots personnalisés

Fichier `TRANSCRIPTION_MOTS`, un mot par ligne, relu à chaud. La méthode de Handy remplace aussi des mots français courants (« projet » → Parakeet, « git » → Gitea) : n'ajouter un mot qu'après une erreur constatée, puis vérifier la liste sur un corpus en français :

```
.venv/bin/python -m transcription.verifier_mots <mots.txt> <dossier de notes en français>
```

## Mesures (03/11/2026, PC Core Ultra 9 285H, processeur seul)

Dictées réelles de Handy, envoyées en WebM/Opus comme par un navigateur : texte identique à Handy.

| Audio | Total serveur | dont transcription (C++) | dont décodage + VAD (Python, ffmpeg) |
|---|---|---|---|
| 2,4 s | 0,17 s | 0,14 s | 0,03 s |
| 21,6 s | 1,19 s | 1,11 s | 0,08 s |
| 14,2 s avec 7,7 s de silences | 0,41 s | 0,35 s | 0,06 s |
| 54,7 s (2 morceaux) | 2,77 s | 2,61 s | 0,16 s |

L'essentiel du temps est dans transcribe.cpp : une réécriture en Rust ne gagnerait que la part Python/ffmpeg (quelques %).

Sur un i5-4570 (4 cœurs) avec Q8_0 : 2,4 s → 0,32 s ; 21,6 s → 2,9 s ; 54,7 s → 6,9 s.

### Quantifications (03/11/2026, i5-4570, `python -m transcription.banc`, médiane de 3)

| Version | Taille | 2,4 s | 21,6 s | 54,7 s | Texte (7 enregistrements) |
|---|---|---|---|---|---|
| **Q8_0** (retenue, celle de Handy) | 740 Mo | 0,32 s | 2,89 s | 6,92 s | référence |
| Q6_K | 611 Mo | 0,32 s | 2,59 s | 6,08 s | 1 écart |
| Q5_K_M | 550 Mo | 0,31 s | 2,53 s | 6,23 s | 2 écarts, dont un mot ajouté (« beaucoup plus longue ») |
| Q4_K_M | 486 Mo | 0,30 s | 2,59 s | 6,20 s | 2 écarts |

Gain de 10 à 12 % sur les dictées longues seulement, au prix d'erreurs : Q8_0 reste la valeur par défaut.

## Écarts connus avec Handy

- Handy calcule la détection de voix pendant l'enregistrement ; ici sur l'enregistrement entier, avec le même automate.
- Pas de détection de langue par VoxLingua107 ni whatlang : sans effet sur la transcription par Parakeet Ultra chez Handy aussi.

## Tests

```
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q tests
```

## Licence

MIT, voir [LICENSE](LICENSE). Code d'origine et modèles : [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
