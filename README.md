<div align="center">

# transcription-handy-like

**Self-hosted speech-to-text on the CPU, behind an OpenAI-compatible API, with word timestamps.**

[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)](compose.yaml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![OpenAI-compatible API](https://img.shields.io/badge/API-OpenAI--compatible-412991)](#use-the-api)
[![Parakeet](https://img.shields.io/badge/model-Parakeet%20Ultra-76B900?logo=nvidia&logoColor=white)](THIRD_PARTY_NOTICES.md)
[![CPU only](https://img.shields.io/badge/GPU-not%20needed-2EA043)](#quick-start-on-your-computer)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**English** · [Français](README.fr.md)

</div>

---

Self-hosted speech-to-text server with an OpenAI-compatible API (`POST /v1/audio/transcriptions`). It runs on the CPU with the **Parakeet Ultra** model (25 European languages) and returns word timestamps.

It is the recommended transcription server for **[auto-generate-subtitles](https://github.com/DamienBecherini/auto-generate-subtitles)**, which turns videos into subtitle files. It also works alone with any OpenAI-compatible client, such as Open WebUI.

It reproduces the processing chain of [Handy](https://github.com/cjpais/Handy), the desktop dictation app. Handy itself has no HTTP API, so it cannot serve this role.

## Quick start on your computer

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) on Windows or macOS, or Docker on Linux.

```
git clone https://github.com/DamienBecherini/transcription-handy-like.git
cd transcription-handy-like
docker compose up -d
```

The first start downloads about 1 GB of models. Check that it is ready:

```
curl http://127.0.0.1:8000/health
```

The answer is `{"state":"loading"}` while it loads, then `{"state":"ready"}`. The server only accepts connections from your own computer, and no API key is needed.

**Next:** [install auto-generate-subtitles](https://github.com/DamienBecherini/auto-generate-subtitles#quick-start). It looks for this server at `http://127.0.0.1:8000` by default.

## Install on a server or VPS

```
git clone https://github.com/DamienBecherini/transcription-handy-like.git
cd transcription-handy-like
./install.sh
```

The script asks for the port, who can reach the server, the API key, the memory limit and where to keep the models. It offers to install Docker on Linux if needed, writes your answers to `.env`, starts the service and waits until it is ready.

To install without questions, copy `.env.example`, fill it in, then run `./install.sh --config my-settings.env`.

Allow 3 GB of memory and 4 GB of disk. A 31-minute recording was tested with a 2 GB limit, which it nearly reached.

**If other machines can reach it:** the script refuses to start without an API key and generates one for you, stored in `.env`. Audio is sent in clear over HTTP, so put HTTPS in front of the server (Caddy, nginx, Traefik) and restrict the port with your firewall.

To update, run `git pull`, then `./install.sh` again. To stop, run `docker compose down`.

## Use the API

```
curl http://127.0.0.1:8000/v1/audio/transcriptions -F file=@audio.mp3
curl http://127.0.0.1:8000/v1/audio/transcriptions -F file=@audio.mp3 -F response_format=verbose_json
```

With an API key, add `-H "Authorization: Bearer <key>"`.

**Cancel.** The OpenAI API has no cancel request: a client that no longer wants the answer closes its connection. The server notices it and stops between two chunks (about 30 s of speech), so the next request does not wait behind work nobody will read; the request ends with status 499.

**Dictation (`json`, `text`, the default).** Handy's chain: voice detection keeps speech only, long recordings are cut in the middle of pauses, then custom words, filler words and stutters are cleaned up.

**Subtitles (`verbose_json`).** Keeps the recording's timeline and returns OpenAI's format: `language`, `duration`, `text`, `segments`, `words` (`word`, `start`, `end`). The model does not report the language, so `language` is empty.

## Settings

Set these in `.env`, or as environment variables without Docker:

| Variable | Meaning |
| --- | --- |
| `TRANSCRIPTION_API_KEY` | if set, required as a Bearer token on `/v1/*` |
| `TRANSCRIPTION_ALLOWED_ORIGINS` | web origins allowed to call `/v1/*` from a browser, comma-separated; by default, requests from web pages (with an `Origin` header) are refused |
| `TRANSCRIPTION_LANGUAGE` | language assumed when a request gives none (used to remove French fillers) |
| `TRANSCRIPTION_THREADS` | CPU threads, 0 = automatic |
| `TRANSCRIPTION_CUSTOM_WORDS` | file of custom words, one per line, reloaded when it changes (without Docker) |

Docker settings: `TRANSCRIPTION_HOST`, `TRANSCRIPTION_PORT`, `TRANSCRIPTION_MEMORY`, `TRANSCRIPTION_MODELS`. Transcribed text is never logged.

Handy's custom-word matching can also replace common words, so add a word only after a real error, then check the list against a corpus with `python -m transcription.check_words <words.txt> <folder of notes>`.

## Without Docker

Python 3.12 and `ffmpeg` in the `PATH`:

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt       # Windows: .venv/Scripts/python -m pip
.venv/bin/python -m uvicorn transcription.server:app --port 8000
```

On Windows, Smart App Control can block the unsigned native libraries with `WinError 4551`. Use Docker in that case.

## Performance

Measured on a Core Ultra 9 285H, CPU only, Q8_0 quantization: 2.4 s of audio in 0.17 s, 21.6 s in 1.19 s, 54.7 s in 2.77 s. On an i5-4570: 0.32 s, 2.9 s and 6.9 s. Lower quantizations gain 10 to 12% on long recordings at the cost of text errors, so Q8_0 stays the default (`python -m transcription.bench` compares them).

## Tests

```
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q tests
```

## Known differences with Handy

- Handy runs voice detection while recording; here it runs on the whole recording, with the same state machine.
- No language detection through VoxLingua107 or whatlang. This has no effect on Parakeet Ultra in Handy either.

## License

MIT, see [LICENSE](LICENSE). Upstream code and models: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
