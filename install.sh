#!/usr/bin/env bash
# Installs transcription-handy-like with Docker: asks a few questions, writes .env, starts the service, checks it.
#   ./install.sh                  interactive; values from an existing .env are offered as defaults
#   ./install.sh --config FILE    no questions; FILE has the same format as .env.example
set -euo pipefail
cd "$(dirname "$0")"

CONF=""
while [ $# -gt 0 ]; do
  case "$1" in
    --config) CONF="${2:?--config needs a file}"; shift 2 ;;
    -h|--help) sed -n '2,4p' "$0" | cut -c3-; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done

TRANSCRIPTION_HOTE=127.0.0.1
TRANSCRIPTION_PORT=8000
TRANSCRIPTION_CLE_API=
TRANSCRIPTION_MEMOIRE=4g
TRANSCRIPTION_FILS=0
TRANSCRIPTION_LANGUE=
TRANSCRIPTION_MODELES=modeles

erreur() { echo "Error: $*" >&2; exit 1; }

lire_conf() {  # the file is parsed, never executed
  local k v
  while IFS='=' read -r k v || [ -n "$k" ]; do
    v="${v%$'\r'}"
    case "$k" in
      TRANSCRIPTION_HOTE|TRANSCRIPTION_PORT|TRANSCRIPTION_CLE_API|TRANSCRIPTION_MEMOIRE|TRANSCRIPTION_FILS|TRANSCRIPTION_LANGUE|TRANSCRIPTION_MODELES)
        printf -v "$k" '%s' "$v" ;;
    esac
  done < "$1"
}

demander() {  # demander "question" default : the answer goes to REPONSE
  local r=""
  read -r -p "$1 [$2]: " r || true
  REPONSE="${r:-$2}"
}

nouvelle_cle() {
  if command -v openssl >/dev/null; then openssl rand -hex 32
  else od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; fi
}

poser_questions() {
  echo "transcription-handy-like setup. Press Enter to keep the value in brackets."
  demander "Port" "$TRANSCRIPTION_PORT"; TRANSCRIPTION_PORT=$REPONSE

  local acces=1
  [ "$TRANSCRIPTION_HOTE" = 127.0.0.1 ] || acces=2
  echo "Who can reach the server?"
  echo "  1) This machine only (recommended, also right behind a reverse proxy on this machine)"
  echo "  2) Other machines: an API key is mandatory, and audio should travel over HTTPS"
  demander "Choice" "$acces"
  if [ "$REPONSE" = 2 ]; then
    [ "$TRANSCRIPTION_HOTE" != 127.0.0.1 ] || TRANSCRIPTION_HOTE=0.0.0.0
    demander "Listen address" "$TRANSCRIPTION_HOTE"; TRANSCRIPTION_HOTE=$REPONSE
    [ -n "$TRANSCRIPTION_CLE_API" ] || TRANSCRIPTION_CLE_API=$(nouvelle_cle)
  else
    TRANSCRIPTION_HOTE=127.0.0.1
    local avec=n
    [ -z "$TRANSCRIPTION_CLE_API" ] || avec=y
    demander "Require an API key? (y/n)" "$avec"
    case "$REPONSE" in
      y|Y) [ -n "$TRANSCRIPTION_CLE_API" ] || TRANSCRIPTION_CLE_API=$(nouvelle_cle) ;;
      *) TRANSCRIPTION_CLE_API= ;;
    esac
  fi

  demander "Memory limit" "$TRANSCRIPTION_MEMOIRE"; TRANSCRIPTION_MEMOIRE=$REPONSE
  demander "CPU threads (0 = automatic)" "$TRANSCRIPTION_FILS"; TRANSCRIPTION_FILS=$REPONSE
  demander "Models: Docker volume name or absolute path" "$TRANSCRIPTION_MODELES"; TRANSCRIPTION_MODELES=$REPONSE
}

valider() {
  [[ "$TRANSCRIPTION_PORT" =~ ^[0-9]+$ ]] && [ "$TRANSCRIPTION_PORT" -ge 1 ] && [ "$TRANSCRIPTION_PORT" -le 65535 ] || erreur "invalid port: $TRANSCRIPTION_PORT"
  [[ "$TRANSCRIPTION_HOTE" =~ ^[0-9a-fA-F.:]+$ ]] || erreur "invalid listen address: $TRANSCRIPTION_HOTE"
  [[ "$TRANSCRIPTION_MEMOIRE" =~ ^[0-9]+[mMgG]$ ]] || erreur "invalid memory limit (examples: 2g, 1500m): $TRANSCRIPTION_MEMOIRE"
  [[ "$TRANSCRIPTION_FILS" =~ ^[0-9]+$ ]] || erreur "invalid thread count: $TRANSCRIPTION_FILS"
  [[ "$TRANSCRIPTION_LANGUE" =~ ^[a-z]{0,3}$ ]] || erreur "invalid language code: $TRANSCRIPTION_LANGUE"
  [[ "$TRANSCRIPTION_MODELES" =~ ^[A-Za-z0-9._/-]+$ ]] || erreur "invalid models location: $TRANSCRIPTION_MODELES"
  [[ -z "$TRANSCRIPTION_CLE_API" || "$TRANSCRIPTION_CLE_API" =~ ^[A-Za-z0-9._~-]+$ ]] || erreur "the API key may only contain letters, digits and . _ ~ -"
  case "$TRANSCRIPTION_HOTE" in
    127.*|::1) ;;
    *) [ -n "$TRANSCRIPTION_CLE_API" ] || erreur "listening on $TRANSCRIPTION_HOTE requires an API key (TRANSCRIPTION_CLE_API)" ;;
  esac
}

ecrire_env() {
  ( umask 077
    cat > .env <<EOF
TRANSCRIPTION_HOTE=$TRANSCRIPTION_HOTE
TRANSCRIPTION_PORT=$TRANSCRIPTION_PORT
TRANSCRIPTION_CLE_API=$TRANSCRIPTION_CLE_API
TRANSCRIPTION_MEMOIRE=$TRANSCRIPTION_MEMOIRE
TRANSCRIPTION_FILS=$TRANSCRIPTION_FILS
TRANSCRIPTION_LANGUE=$TRANSCRIPTION_LANGUE
TRANSCRIPTION_MODELES=$TRANSCRIPTION_MODELES
EOF
  )
}

installer_docker() {
  [ "$(uname -s)" = Linux ] || erreur "Docker is required: install Docker Desktop from https://www.docker.com/products/docker-desktop/"
  [ -z "$CONF" ] || erreur "Docker is required: install it, then run this script again"
  demander "Docker is not installed. Install it now with Docker's official script (get.docker.com)? (y/n)" n
  case "$REPONSE" in y|Y) ;; *) erreur "Docker is required: https://docs.docker.com/engine/install/" ;; esac
  command -v curl >/dev/null || erreur "curl is required to install Docker"
  local sudo=""
  [ "$(id -u)" = 0 ] || sudo=sudo
  curl -fsSL https://get.docker.com | $sudo sh
}

verifier_docker() {
  command -v docker >/dev/null || installer_docker
  docker info >/dev/null 2>&1 || erreur "the Docker daemon is not reachable. Start Docker, or add your user to the docker group, then run this script again"
  docker compose version >/dev/null 2>&1 || erreur "the Docker Compose plugin is required: https://docs.docker.com/compose/install/"
}

verifier_ressources() {
  local libre
  libre=$(df -Pm . | awk 'NR==2 {print $4}')
  [ "${libre:-0}" -ge 4000 ] || echo "Warning: ${libre:-0} MB free on disk; the image and models need about 4000 MB."
  if [ -r /proc/meminfo ]; then
    libre=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    [ "${libre:-0}" -ge 2000 ] || echo "Warning: ${libre:-0} MB of memory available; the server needs about 2000 MB."
  fi
}

attendre() {  # the first start downloads about 1 GB of models
  local i
  echo "Waiting for the server (the first start downloads the models, about 1 GB)..."
  for i in $(seq 1 360); do
    if docker compose exec -T transcription python -c "import json,urllib.request as u; raise SystemExit(json.load(u.urlopen('http://127.0.0.1:8000/health', timeout=3))['etat'] != 'pret')" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  docker compose logs --tail 30 transcription >&2
  erreur "the server was not ready after 30 minutes (logs above)"
}

if [ -n "$CONF" ]; then
  [ -r "$CONF" ] || erreur "cannot read $CONF"
  lire_conf "$CONF"
else
  [ ! -r .env ] || lire_conf .env
  poser_questions
fi
valider
verifier_docker
verifier_ressources
ecrire_env

docker compose build
if [[ "$TRANSCRIPTION_MODELES" == */* ]]; then  # a host folder must belong to the unprivileged user of the image
  mkdir -p "$TRANSCRIPTION_MODELES"
  docker run --rm --user 0 -v "$TRANSCRIPTION_MODELES:/modeles" --entrypoint chown transcription-handy-like:local 1000:1000 /modeles
fi
docker compose up -d
attendre

case "$TRANSCRIPTION_HOTE" in
  0.0.0.0|::) ADRESSE="http://<this-server>:$TRANSCRIPTION_PORT" ;;
  *) ADRESSE="http://$TRANSCRIPTION_HOTE:$TRANSCRIPTION_PORT" ;;
esac
echo
echo "Ready: $ADRESSE"
[ -z "$TRANSCRIPTION_CLE_API" ] || echo "API key: stored in .env (TRANSCRIPTION_CLE_API), send it as 'Authorization: Bearer <key>'."
case "$TRANSCRIPTION_HOTE" in
  127.*|::1) ;;
  *) echo "Reachable from other machines: put HTTPS in front of it and restrict the port with your firewall." ;;
esac
echo "Stop: docker compose down    Logs: docker compose logs -f transcription"
echo "Subtitles: https://github.com/DamienBecherini/auto-generate-subtitles"
