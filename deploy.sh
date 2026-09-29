#!/usr/bin/env bash
# One-shot SoundBridge setup for a fresh Ubuntu 24.04 EC2 instance.
#
#   curl -fsSL https://raw.githubusercontent.com/jerrytope/soundbridge/master/deploy.sh | sudo bash
#
# Safe to re-run: secrets are generated only on the first run, and later runs pull
# the latest code, rebuild, migrate and restart. Any setting below can be passed as
# an environment variable, e.g.  sudo ADMIN_EMAIL=me@example.com bash deploy.sh
# Anything left unset that is needed is asked for interactively.
set -euo pipefail

SERVER_IP="${SERVER_IP:-13.63.126.14}"
APP_PORT="${APP_PORT:-8000}"
REPO_URL="${REPO_URL:-https://github.com/jerrytope/soundbridge.git}"
BRANCH="${BRANCH:-master}"
APP_DIR="${APP_DIR:-/srv/soundbridge}"

# First administrator account (created once, skipped if it already exists).
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

# Optional on the first run; edit $APP_DIR/.env.local later to change them.
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
OPENAI_MODEL="${OPENAI_MODEL:-gpt-4.1}"
SPOTIFY_CLIENT_ID="${SPOTIFY_CLIENT_ID:-}"
SPOTIFY_CLIENT_SECRET="${SPOTIFY_CLIENT_SECRET:-}"
EMAIL_HOST="${EMAIL_HOST:-}"
EMAIL_PORT="${EMAIL_PORT:-587}"
EMAIL_HOST_USER="${EMAIL_HOST_USER:-}"
EMAIL_HOST_PASSWORD="${EMAIL_HOST_PASSWORD:-}"
DEFAULT_FROM_EMAIL="${DEFAULT_FROM_EMAIL:-SoundBridge <noreply@localhost>}"

log()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARNING: %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# Prompts read from the terminal, so they work under `curl ... | sudo bash` too.
ask() {  # ask VAR "Prompt" [secret]
  local var=$1 prompt=$2 secret=${3:-} value
  [ -n "${!var}" ] && return
  [ -r /dev/tty ] || die "$var is not set and there is no terminal to ask on."
  if [ -n "$secret" ]; then
    read -rsp "$prompt: " value </dev/tty; echo >/dev/tty
  else
    read -rp "$prompt: " value </dev/tty
  fi
  printf -v "$var" '%s' "$value"
}

[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash deploy.sh"
. /etc/os-release
[ "${ID:-}" = ubuntu ] || warn "Written for Ubuntu; this is ${PRETTY_NAME:-unknown}."

mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
if [ "$mem_kb" -lt 3500000 ]; then
  warn "Only $((mem_kb / 1024)) MiB of RAM. ClamAV needs about 4 GiB (t3.medium or larger);"
  warn "on a smaller instance the upload scanner is killed and uploads stay quarantined."
fi

# Leftovers from an earlier failed build can be what filled the disk.
command -v docker >/dev/null && docker builder prune -af >/dev/null 2>&1 || true
free_gb=$(( $(df --output=avail -k / | tail -1) / 1024 / 1024 ))
if [ "$free_gb" -lt 8 ]; then
  df -h /
  die "Only ${free_gb} GiB free on /. The build needs about 8 GiB. Enlarge the EBS volume
to 30 GiB in the AWS console (EC2 > Volumes > Modify), then on this server run:
  sudo growpart \$(findmnt -no SOURCE / | sed -E 's/p?[0-9]+\$//') 1 && sudo resize2fs \$(findmnt -no SOURCE /)
and run this script again."
fi

export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a

# ---------------------------------------------------------------------------
log "Installing system packages"
apt-get update -y
apt-get upgrade -y
apt-get install -y ca-certificates curl git gzip unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades

if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  log "Installing Docker Engine and the Compose plugin"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
# Let the login user run docker without sudo from their next session.
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
  usermod -aG docker "$SUDO_USER"
fi

if ! swapon --show | grep -q '^/swapfile'; then
  log "Adding 2 GiB of swap"
  [ -f /swapfile ] || fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ---------------------------------------------------------------------------
log "Fetching the code ($BRANCH)"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
else
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
echo "Deploying commit $(git rev-parse --short HEAD)"

dc() { docker compose "$@"; }

# ---------------------------------------------------------------------------
if [ ! -f .env.local ]; then
  log "Generating secrets and writing configuration"
  rand() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
  secret_key=$(rand 64)
  # A Fernet key is 32 random bytes, url-safe base64 encoded.
  storage_key=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
  mysql_password=$(rand 32)
  mysql_root_password=$(rand 32)

  if [ -n "$EMAIL_HOST" ]; then
    email_backend=django.core.mail.backends.smtp.EmailBackend
  else
    email_backend=django.core.mail.backends.console.EmailBackend
    warn "No EMAIL_HOST given: emails (including password resets) will only be printed to the web log."
  fi
  moderation_model=""
  [ -n "$OPENAI_API_KEY" ] && moderation_model=omni-moderation-latest

  umask 077
  cat > .env <<EOF
MYSQL_PASSWORD=$mysql_password
MYSQL_ROOT_PASSWORD=$mysql_root_password
EOF

  cat > .env.local <<EOF
# Written by deploy.sh on $(date -u +%Y-%m-%dT%H:%MZ). Edit and re-run deploy.sh to apply.
# NEVER regenerate SOUNDBRIDGE_PRIVATE_STORAGE_KEY: stored files become unreadable.
SOUNDBRIDGE_PUBLIC_ORIGIN=http://$SERVER_IP:$APP_PORT
SOUNDBRIDGE_SECRET_KEY=$secret_key
SOUNDBRIDGE_PRIVATE_STORAGE_KEY=$storage_key

SOUNDBRIDGE_ALLOW_SIGNUP=true
SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION=false

MYSQL_PASSWORD=$mysql_password

SOUNDBRIDGE_EMAIL_BACKEND=$email_backend
EMAIL_HOST=$EMAIL_HOST
EMAIL_PORT=$EMAIL_PORT
EMAIL_HOST_USER=$EMAIL_HOST_USER
EMAIL_HOST_PASSWORD=$EMAIL_HOST_PASSWORD
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=$DEFAULT_FROM_EMAIL

SOUNDBRIDGE_TERMS_VERSION=2026-09-01
SOUNDBRIDGE_PRIVACY_VERSION=2026-09-01

OPENAI_API_KEY=$OPENAI_API_KEY
OPENAI_MODEL=$OPENAI_MODEL
SOUNDBRIDGE_MODERATION_MODEL=$moderation_model

SPOTIFY_CLIENT_ID=$SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET=$SPOTIFY_CLIENT_SECRET
EOF
  umask 022
  first_run=1
else
  log "Keeping the existing .env and .env.local"
  first_run=0
fi
chmod 600 .env .env.local
dc config --quiet

# ---------------------------------------------------------------------------
log "Building images (this takes several minutes the first time)"
dc build
docker image prune -f >/dev/null || true

log "Updating ClamAV signatures"
dc run --rm web freshclam || warn "freshclam failed; uploads stay quarantined until it succeeds. The weekly cron will retry."

log "Starting the database and Redis"
dc up -d db redis

log "Running migrations"
dc run --rm web python manage.py migrate --noinput

# ---------------------------------------------------------------------------
has_admin=$(dc run --rm -T web python manage.py shell -c "
from django.contrib.auth import get_user_model
print(get_user_model().objects.filter(is_superuser=True).exists())
" 2>/dev/null | tail -1 || true)
if [ "$has_admin" != True ] || [ -n "$ADMIN_EMAIL" ]; then
  ask ADMIN_EMAIL "Administrator email"
  ask ADMIN_PASSWORD "Administrator password (not shown)" secret
  [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ] || die "Administrator email and password are required."
  log "Creating the administrator account"
  dc run --rm -e ADMIN_EMAIL="$ADMIN_EMAIL" -e ADMIN_PASSWORD="$ADMIN_PASSWORD" web \
    python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email = os.environ['ADMIN_EMAIL'].strip().lower()
if User.objects.filter(email=email).exists():
    print('Administrator', email, 'already exists; left unchanged.')
else:
    User.objects.create_superuser(email, os.environ['ADMIN_PASSWORD'])
    print('Created administrator', email)
"
fi

log "Starting SoundBridge"
dc up -d --remove-orphans

log "Waiting for the web server"
healthy=0
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null -H "Host: $SERVER_IP" "http://127.0.0.1:$APP_PORT/api/health"; then
    healthy=1; break
  fi
  sleep 3
done

# ---------------------------------------------------------------------------
log "Installing backups and scheduled jobs"
cat > /usr/local/bin/soundbridge-backup <<EOF
#!/bin/bash
# Nightly local backup of the database and encrypted artifacts. Copy these off
# the server (with the key in $APP_DIR/.env.local) - they are useless without it.
set -euo pipefail
cd $APP_DIR
stamp=\$(date -u +%Y%m%dT%H%M%SZ)
dest=/var/backups/soundbridge
mkdir -p "\$dest" && chmod 700 "\$dest"
docker compose exec -T db sh -c \\
  'exec mysqldump --single-transaction --routines --triggers -u root -p"\$MYSQL_ROOT_PASSWORD" soundbridge' \\
  | gzip > "\$dest/db-\$stamp.sql.gz"
docker compose run --rm -T web tar -cz -C /app/.data artifacts > "\$dest/artifacts-\$stamp.tar.gz"
find "\$dest" -type f -mtime +7 -delete
EOF
chmod 755 /usr/local/bin/soundbridge-backup

cat > /etc/cron.d/soundbridge <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 2 * * * root /usr/local/bin/soundbridge-backup >> /var/log/soundbridge-backup.log 2>&1
0 4 * * 1 root cd $APP_DIR && docker compose run --rm web freshclam >> /var/log/soundbridge-freshclam.log 2>&1
EOF
chmod 644 /etc/cron.d/soundbridge

# ---------------------------------------------------------------------------
dc ps
echo
if [ "$healthy" = 1 ]; then
  log "SoundBridge is running at http://$SERVER_IP:$APP_PORT"
else
  warn "The web server did not answer yet. Check: cd $APP_DIR && docker compose logs --tail=100 web"
fi
cat <<EOF

Next steps:
  * Open port $APP_PORT (TCP) in the EC2 security group, or the site is unreachable from outside.
  * Back up $APP_DIR/.env and $APP_DIR/.env.local somewhere safe OFF this server.
    Losing SOUNDBRIDGE_PRIVATE_STORAGE_KEY makes every stored upload unreadable.
  * Logs:    cd $APP_DIR && docker compose logs -f web worker scheduler
  * Update:  push to GitHub, then re-run this script.
EOF
