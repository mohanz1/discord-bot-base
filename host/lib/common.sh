# shellcheck shell=bash
# Shared helpers for the host scripts in host/bin. Sourced, never run.
#
# Layout (see docs/hosting.md):
#   /srv/bots/host/          these scripts + compose.yaml   (root-owned, from install.sh)
#   /srv/bots/host.env       host settings: BACKUP_REMOTE, HOST_HEALTHCHECK_URL
#   /srv/bots/<bot>/
#     deploy.env             IMAGE=…, TAG=latest (pin a sha-… tag to roll back)
#     .env                   the bot's own BOT_* settings and secrets
#     compose.override.yaml  optional, admin-written per-bot tweaks
#     data/                  bind-mounted at /app/data (uid 10001)
#     backups/               pre-deploy DB snapshots (deploy user)

BOTS_ROOT="${BOTS_ROOT:-/srv/bots}"
HOST_DIR="$BOTS_ROOT/host"
# shellcheck disable=SC2034 # used by the scripts that source this file
BOT_UID=10001

die() {
  echo "${0##*/}: $*" >&2
  exit 1
}

# bot_dir <name> — validate a bot name and echo its directory.
bot_dir() {
  local name="${1:-}"
  [[ "$name" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || die "bad bot name '${name}' (lowercase letters, digits, dashes)"
  printf '%s/%s\n' "$BOTS_ROOT" "$name"
}

# bot_compose <name> <compose args…> — docker compose for one bot, with the shared
# compose file. deploy.env is the *interpolation* file (IMAGE / TAG / MEM_LIMIT); the
# bot's .env only reaches the container (env_file), never the compose file.
bot_compose() {
  local name="$1" dir
  shift
  dir="$(bot_dir "$name")"
  [[ -f "$dir/deploy.env" ]] || die "$name: no $dir/deploy.env — add it with add-bot"
  local files=(-f "$HOST_DIR/compose.yaml")
  [[ -f "$dir/compose.override.yaml" ]] && files+=(-f "$dir/compose.override.yaml")
  docker compose --project-name "$name" --project-directory "$dir" "${files[@]}" \
    --env-file "$dir/deploy.env" "$@"
}

# env_value <file> <KEY> — read KEY=value from a dotenv file without sourcing it.
# A missing file or key is just empty (callers decide whether that's an error).
env_value() {
  [[ -r "$1" ]] || return 0
  sed -n "s/^$2=//p" "$1" | tail -n 1 | tr -d '"'"'"
}
