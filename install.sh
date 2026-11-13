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

TRANSCRIPTION_HOST=127.0.0.1
TRANSCRIPTION_PORT=8000
TRANSCRIPTION_API_KEY=
TRANSCRIPTION_MEMORY=4g
TRANSCRIPTION_THREADS=0
TRANSCRIPTION_LANGUAGE=
TRANSCRIPTION_MODELS=models

fail() { echo "Error: $*" >&2; exit 1; }

read_conf() {  # the file is parsed, never executed
  local k v
  while IFS='=' read -r k v || [ -n "$k" ]; do
    v="${v%$'\r'}"
    case "$k" in
      TRANSCRIPTION_HOST|TRANSCRIPTION_PORT|TRANSCRIPTION_API_KEY|TRANSCRIPTION_MEMORY|TRANSCRIPTION_THREADS|TRANSCRIPTION_LANGUAGE|TRANSCRIPTION_MODELS)
        printf -v "$k" '%s' "$v" ;;
    esac
  done < "$1"
}

ask() {  # ask "question" default : the answer goes to ANSWER
  local r=""
  read -r -p "$1 [$2]: " r || true
  ANSWER="${r:-$2}"
}

new_key() {
  if command -v openssl >/dev/null; then openssl rand -hex 32
  else od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; fi
}

ask_questions() {
  echo "transcription-handy-like setup. Press Enter to keep the value in brackets."
  ask "Port" "$TRANSCRIPTION_PORT"; TRANSCRIPTION_PORT=$ANSWER

  local access=1
  [ "$TRANSCRIPTION_HOST" = 127.0.0.1 ] || access=2
  echo "Who can reach the server?"
  echo "  1) This machine only (recommended, also right behind a reverse proxy on this machine)"
  echo "  2) Other machines: an API key is mandatory, and audio should travel over HTTPS"
  ask "Choice" "$access"
  if [ "$ANSWER" = 2 ]; then
    [ "$TRANSCRIPTION_HOST" != 127.0.0.1 ] || TRANSCRIPTION_HOST=0.0.0.0
    ask "Listen address" "$TRANSCRIPTION_HOST"; TRANSCRIPTION_HOST=$ANSWER
    [ -n "$TRANSCRIPTION_API_KEY" ] || TRANSCRIPTION_API_KEY=$(new_key)
  else
    TRANSCRIPTION_HOST=127.0.0.1
    local with_key=n
    [ -z "$TRANSCRIPTION_API_KEY" ] || with_key=y
    ask "Require an API key? (y/n)" "$with_key"
    case "$ANSWER" in
      y|Y) [ -n "$TRANSCRIPTION_API_KEY" ] || TRANSCRIPTION_API_KEY=$(new_key) ;;
      *) TRANSCRIPTION_API_KEY= ;;
    esac
  fi

  ask "Memory limit" "$TRANSCRIPTION_MEMORY"; TRANSCRIPTION_MEMORY=$ANSWER
  ask "CPU threads (0 = automatic)" "$TRANSCRIPTION_THREADS"; TRANSCRIPTION_THREADS=$ANSWER
  ask "Models: Docker volume name or absolute path" "$TRANSCRIPTION_MODELS"; TRANSCRIPTION_MODELS=$ANSWER
}

validate() {
  [[ "$TRANSCRIPTION_PORT" =~ ^[0-9]+$ ]] && [ "$TRANSCRIPTION_PORT" -ge 1 ] && [ "$TRANSCRIPTION_PORT" -le 65535 ] || fail "invalid port: $TRANSCRIPTION_PORT"
  [[ "$TRANSCRIPTION_HOST" =~ ^[0-9a-fA-F.:]+$ ]] || fail "invalid listen address: $TRANSCRIPTION_HOST"
  [[ "$TRANSCRIPTION_MEMORY" =~ ^[0-9]+[mMgG]$ ]] || fail "invalid memory limit (examples: 2g, 1500m): $TRANSCRIPTION_MEMORY"
  [[ "$TRANSCRIPTION_THREADS" =~ ^[0-9]+$ ]] || fail "invalid thread count: $TRANSCRIPTION_THREADS"
  [[ "$TRANSCRIPTION_LANGUAGE" =~ ^[a-z]{0,3}$ ]] || fail "invalid language code: $TRANSCRIPTION_LANGUAGE"
  [[ "$TRANSCRIPTION_MODELS" =~ ^[A-Za-z0-9._/-]+$ ]] || fail "invalid models location: $TRANSCRIPTION_MODELS"
  [[ -z "$TRANSCRIPTION_API_KEY" || "$TRANSCRIPTION_API_KEY" =~ ^[A-Za-z0-9._~-]+$ ]] || fail "the API key may only contain letters, digits and . _ ~ -"
  case "$TRANSCRIPTION_HOST" in
    127.*|::1) ;;
    *) [ -n "$TRANSCRIPTION_API_KEY" ] || fail "listening on $TRANSCRIPTION_HOST requires an API key (TRANSCRIPTION_API_KEY)" ;;
  esac
}

write_env() {
  ( umask 077
    cat > .env <<EOF
TRANSCRIPTION_HOST=$TRANSCRIPTION_HOST
TRANSCRIPTION_PORT=$TRANSCRIPTION_PORT
TRANSCRIPTION_API_KEY=$TRANSCRIPTION_API_KEY
TRANSCRIPTION_MEMORY=$TRANSCRIPTION_MEMORY
TRANSCRIPTION_THREADS=$TRANSCRIPTION_THREADS
TRANSCRIPTION_LANGUAGE=$TRANSCRIPTION_LANGUAGE
TRANSCRIPTION_MODELS=$TRANSCRIPTION_MODELS
EOF
  )
}

install_docker() {
  [ "$(uname -s)" = Linux ] || fail "Docker is required: install Docker Desktop from https://www.docker.com/products/docker-desktop/"
  [ -z "$CONF" ] || fail "Docker is required: install it, then run this script again"
  ask "Docker is not installed. Install it now with Docker's official script (get.docker.com)? (y/n)" n
  case "$ANSWER" in y|Y) ;; *) fail "Docker is required: https://docs.docker.com/engine/install/" ;; esac
  command -v curl >/dev/null || fail "curl is required to install Docker"
  local sudo=""
  [ "$(id -u)" = 0 ] || sudo=sudo
  curl -fsSL https://get.docker.com | $sudo sh
}

check_docker() {
  command -v docker >/dev/null || install_docker
  docker info >/dev/null 2>&1 || fail "the Docker daemon is not reachable. Start Docker, or add your user to the docker group, then run this script again"
  docker compose version >/dev/null 2>&1 || fail "the Docker Compose plugin is required: https://docs.docker.com/compose/install/"
}

check_resources() {
  local free
  free=$(df -Pm . | awk 'NR==2 {print $4}')
  [ "${free:-0}" -ge 4000 ] || echo "Warning: ${free:-0} MB free on disk; the image and models need about 4000 MB."
  if [ -r /proc/meminfo ]; then
    free=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    [ "${free:-0}" -ge 2000 ] || echo "Warning: ${free:-0} MB of memory available; the server needs about 2000 MB."
  fi
}

wait_ready() {  # the first start downloads about 1 GB of models
  local i
  echo "Waiting for the server (the first start downloads the models, about 1 GB)..."
  for i in $(seq 1 360); do
    if docker compose exec -T transcription python -c "import json,urllib.request as u; raise SystemExit(json.load(u.urlopen('http://127.0.0.1:8000/health', timeout=3))['state'] != 'ready')" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  docker compose logs --tail 30 transcription >&2
  fail "the server was not ready after 30 minutes (logs above)"
}

if [ -n "$CONF" ]; then
  [ -r "$CONF" ] || fail "cannot read $CONF"
  read_conf "$CONF"
else
  [ ! -r .env ] || read_conf .env
  ask_questions
fi
validate
check_docker
check_resources
write_env

docker compose build
if [[ "$TRANSCRIPTION_MODELS" == */* ]]; then  # a host folder must belong to the unprivileged user of the image
  mkdir -p "$TRANSCRIPTION_MODELS"
  docker run --rm --user 0 -v "$TRANSCRIPTION_MODELS:/models" --entrypoint chown transcription-handy-like:local 1000:1000 /models
fi
docker compose up -d
wait_ready

case "$TRANSCRIPTION_HOST" in
  0.0.0.0|::) ADDRESS="http://<this-server>:$TRANSCRIPTION_PORT" ;;
  *) ADDRESS="http://$TRANSCRIPTION_HOST:$TRANSCRIPTION_PORT" ;;
esac
echo
echo "Ready: $ADDRESS"
[ -z "$TRANSCRIPTION_API_KEY" ] || echo "API key: stored in .env (TRANSCRIPTION_API_KEY), send it as 'Authorization: Bearer <key>'."
case "$TRANSCRIPTION_HOST" in
  127.*|::1) ;;
  *) echo "Reachable from other machines: put HTTPS in front of it and restrict the port with your firewall." ;;
esac
echo "Stop: docker compose down    Logs: docker compose logs -f transcription"
echo "Subtitles: https://github.com/DamienBecherini/dl-sub-dub"
