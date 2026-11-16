#!/usr/bin/env bash
# install.sh — set up (or update) a bot host. Ubuntu 24.04+, as root, from a checkout:
#
#   git clone https://github.com/mohanz1/discord-bot-base /tmp/dbb && sudo /tmp/dbb/host/install.sh
#
# Safe to re-run: on a fresh machine it adds swap, Docker, the deploy user and the
# tools; every run (re)installs the host scripts, the shared compose file and the
# systemd units, so updating the host is the same command from a newer checkout.
# Per-bot setup is separate: add-bot. See docs/hosting.md.
set -euo pipefail

src="$(dirname "$(readlink -f "$0")")"
# shellcheck source=lib/common.sh
source "$src/lib/common.sh"
[[ $EUID -eq 0 ]] || die "run as root (sudo)"

step() { echo "install: $*"; }

# -- the machine (first run only) -------------------------------------------------
if ! swapon --show=NAME --noheadings | grep -q .; then
  # Small instances have no swap; 1 GB keeps an image pull or a spike from OOM-killing bots.
  step "adding 1 GB swap"
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

if ! command -v docker >/dev/null; then
  step "installing Docker"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi
if ! docker compose version >/dev/null 2>&1; then
  # e.g. Ubuntu's docker.io package, which ships without Compose v2.
  step "installing the Docker Compose plugin"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker-compose-v2 >/dev/null
fi

missing=()
for tool in sqlite3 rclone flock curl; do command -v "$tool" >/dev/null || missing+=("$tool"); done
if ((${#missing[@]})); then
  step "installing ${missing[*]}"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq sqlite3 rclone util-linux curl >/dev/null
fi

if ! id deploy >/dev/null 2>&1; then
  # CI logs in as deploy, but only through per-bot forced commands (add-bot --key).
  step "adding the deploy user"
  adduser --disabled-password --gecos "" deploy >/dev/null
fi
usermod -aG docker deploy
install -d -o deploy -g deploy -m 700 /home/deploy/.ssh
[[ -f /home/deploy/.ssh/authorized_keys ]] || install -o deploy -g deploy -m 600 /dev/null /home/deploy/.ssh/authorized_keys

# -- the host layer (every run) -------------------------------------------------------
# Root-owned: the deploy user (and so CI) can run these but never change them.
step "installing host scripts to $HOST_DIR"
install -d -o root -g root -m 755 "$BOTS_ROOT" "$HOST_DIR" "$HOST_DIR/bin" "$HOST_DIR/lib"
install -o root -g root -m 644 "$src/compose.yaml" "$HOST_DIR/compose.yaml"
install -o root -g root -m 644 "$src/lib/common.sh" "$HOST_DIR/lib/common.sh"
for script in "$src"/bin/*; do
  install -o root -g root -m 755 "$script" "$HOST_DIR/bin/"
  ln -sf "$HOST_DIR/bin/$(basename "$script")" "/usr/local/bin/$(basename "$script")"
done

if [[ ! -f "$BOTS_ROOT/host.env" ]]; then
  cat >"$BOTS_ROOT/host.env" <<'EOF'
# Host-wide settings, read by the host scripts (not by any bot).
# rclone remote + bucket for nightly DB backups; each bot goes under <remote>/<bot>/.
# Configure the remote first: sudo -u deploy rclone config
BACKUP_REMOTE=
# BACKUP_KEEP_DAYS=30
# healthchecks.io check for the whole host (disk, memory, Docker), pinged every 5 min.
HOST_HEALTHCHECK_URL=
EOF
  step "wrote $BOTS_ROOT/host.env — fill it in"
fi
chown root:deploy "$BOTS_ROOT/host.env" && chmod 640 "$BOTS_ROOT/host.env"

step "installing systemd units"
install -o root -g root -m 644 "$src"/systemd/* /etc/systemd/system/
if [[ -d /run/systemd/system ]]; then
  systemctl daemon-reload
  systemctl enable --now docker-prune.timer host-check.timer >/dev/null
else
  step "systemd isn't running here — enable docker-prune.timer and host-check.timer yourself"
fi

step "done. Next: fill in $BOTS_ROOT/host.env, log in to your registry as deploy, then add-bot."
