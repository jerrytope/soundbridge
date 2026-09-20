# Deploying SoundBridge to an AWS Ubuntu server

The shipped product is the Django application in this repository: Gunicorn serving
`config.wsgi`, MySQL, Redis, and two Celery processes (a worker and exactly one beat
scheduler). `Dockerfile` and `compose.yaml` describe that runtime, and this guide runs
them on a single Ubuntu EC2 instance.

There is no domain name yet, so the site is reached directly at **`http://<server-ip>:8001`**.
Section 7 covers moving to a domain and HTTPS later; that change is two settings and a
reverse proxy, and nothing in the application needs rewriting for it.

The retired Node/React/Vercel prototype (`src/`, `server/`, `api/`, `package.json`,
`vite.config.js`, `vercel.json`) is no longer tracked in git and plays no part in a
deployment. The Python modules mention those paths only in comments recording what each
one was ported from.

Read [docs/MVP_OPERATIONS.md](docs/MVP_OPERATIONS.md) alongside this guide: it covers the
background jobs, private-file encryption, privacy processing, plans and entitlements in
more depth than the steps below.

> **Plain HTTP carries everything in the clear.** On `http://<ip>:8001` the password
> typed at sign-in, the session cookie and every royalty figure cross the network
> unencrypted, and anyone on the path can read or change them. That is a reasonable
> trade for a private pilot with people you have briefed. Do not invite real creators to
> put real earnings into it until section 7 is done.

> **This build is not launch-certified.** `python manage.py launch_check` fails closed
> until every release gate is recorded, and several gates are human decisions no script
> can supply. Section 8 explains what that means. You can run the service privately long
> before those gates pass.

---

## 1. What you need before you start

| Item | Value |
| --- | --- |
| Instance | EC2 `t3.medium` (2 vCPU, 4 GiB) or larger, Ubuntu 24.04 LTS |
| Storage | 30 GiB gp3, encrypted |
| Elastic IP | Allocated and associated — **required**, because the IP *is* the address people will use, and an unassociated public IP changes on every stop/start |
| Security group | Inbound 22 from your own IP only, and 8001 from wherever your testers are. Nothing else. |

4 GiB of RAM is a floor, not a preference. ClamAV's signature database is well over a
gigabyte and `clamscan` loads it on every invocation; on a 2 GiB instance the scanner is
killed under memory pressure and every upload stays quarantined. Do not publish MySQL's
3306 — the database container has no host port at all, which is deliberate.

If you can scope it, open 8001 to your testers' IP ranges rather than `0.0.0.0/0`. Over
plain HTTP that is the only access control between the internet and the sign-in form.

You will also need SMTP credentials (password recovery depends on real delivery) and, if
you are enabling those features, an OpenAI API key and Spotify client credentials.

## 2. Prepare the host

```bash
ssh ubuntu@your.elastic.ip

sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git

# Docker Engine and the Compose plugin, from Docker's own repository.
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo tee /etc/apt/keyrings/docker.asc > /dev/null
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu && newgrp docker

sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

Give the instance 2 GiB of swap. Image builds and `clamscan` both spike, and swap turns a
hard OOM kill into a slow request:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Check that nothing already holds port 8001 — if something does, change the published port
in `compose.yaml` and use that port everywhere below:

```bash
sudo ss -lntp | grep ':8001' || echo "8001 is free"
```

## 3. Get the code onto the server

```bash
sudo mkdir -p /srv/soundbridge && sudo chown ubuntu:ubuntu /srv/soundbridge
git clone <your-repository-url> /srv/soundbridge
cd /srv/soundbridge
git checkout <the-tag-you-are-releasing>
```

Deploy a tag, not a moving branch. You cannot roll back to "whatever `main` was last
Tuesday", and section 10 depends on knowing exactly which commit is live.

## 4. Generate the secrets

Three values are generated once and then never regenerated, because existing data depends
on them. Keep them in AWS Secrets Manager or your password manager, not only on the
instance.

```bash
# Django signing key. Changing it invalidates every session.
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Private-artifact encryption key. Losing it makes every stored profile image,
# statement upload and data export permanently unreadable.
docker run --rm python:3.12-slim sh -c \
  "pip install -q cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"

# Two MySQL passwords: one for the application user, one for root.
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 5. Write the configuration

Two files, both of which stay out of git (`.env*` is ignored).

**`/srv/soundbridge/.env`** — read only by Docker Compose, to interpolate `${...}` in
`compose.yaml`:

```dotenv
MYSQL_PASSWORD=the-application-password-from-step-4
MYSQL_ROOT_PASSWORD=the-root-password-from-step-4
```

**`/srv/soundbridge/.env.local`** — read by the application through `config/env.py`.
Substitute your Elastic IP for `13.51.0.0`:

```dotenv
# Declaring a public origin is the switch that turns this into a production
# deployment: DEBUG goes off, ALLOWED_HOSTS narrows to this host, and signup closes
# unless reopened below. Keep the scheme http:// and the port on it while the site is
# reached by IP address — an https:// origin turns on the HTTPS redirect and Secure
# cookies, which over plain HTTP would loop the browser and never store a session.
SOUNDBRIDGE_PUBLIC_ORIGIN=http://13.51.0.0:8001
SOUNDBRIDGE_SECRET_KEY=the-django-key-from-step-4
SOUNDBRIDGE_PRIVATE_STORAGE_KEY=the-fernet-key-from-step-4

# Open public registration. Omit this and only an administrator can create accounts.
SOUNDBRIDGE_ALLOW_SIGNUP=true

# Email verification stays off: signing up logs you straight in, and the details you
# signed up with are the details you sign in with. Set this to true to require a
# confirmation link again.
SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION=false

# MySQL. The user, database name and host are set in compose.yaml and override
# anything written here; only the password is read from this file.
MYSQL_PASSWORD=the-application-password-from-step-4

# Real email. Password recovery sends through this backend directly, so the console
# backend would print reset links into the container log instead of delivering them.
SOUNDBRIDGE_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=email-smtp.eu-west-1.amazonaws.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-smtp-username
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=SoundBridge <noreply@example.com>

# The approved policy versions users are consenting to.
SOUNDBRIDGE_TERMS_VERSION=2026-09-01
SOUNDBRIDGE_PRIVACY_VERSION=2026-09-01

# Model access. Moderation runs before a message reaches the model and before a reply
# is shown; on a public origin an unconfigured moderation model blocks AI requests.
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
SOUNDBRIDGE_MODERATION_MODEL=omni-moderation-latest

# Spotify catalogue search (optional).
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

```bash
chmod 600 /srv/soundbridge/.env /srv/soundbridge/.env.local
```

Two things about configuration that will otherwise cost you an afternoon:

- `config/env.py` reads **`.env.example` first and `.env.local` second**, and a real
  environment variable beats both. `.env.example` is a tracked file carrying development
  defaults, so every production value you care about must be set explicitly in
  `.env.local` rather than left to fall through.
- `compose.yaml` sets `PORT`, `MYSQL_*`, `CELERY_BROKER_URL` and
  `SOUNDBRIDGE_MALWARE_SCANNER` in its `environment:` block, which **overrides** anything
  in `.env.local`. Change those in `compose.yaml`, not in the env file.

Check the result without printing the secrets to your terminal:

```bash
docker compose config --quiet && echo "compose configuration is valid"
```

## 6. First deployment

```bash
cd /srv/soundbridge
docker compose build

# Fetch ClamAV signatures into the named volume. The image installs the scanner but
# ships no signature database, and without this every upload is quarantined.
docker compose run --rm web freshclam

# Migrate once, as a one-off job. Never let several web workers migrate concurrently.
docker compose run --rm web python manage.py migrate

# One controlled administrative account.
docker compose run --rm web python manage.py createsuperuser

docker compose up -d
docker compose ps
```

Confirm the application is serving. Every request is checked against your public origin,
so a probe from the server itself has to send the matching `Host` header — a bare
`curl http://127.0.0.1:8001/api/health` is answered with `403` by design, not because
anything is broken:

```bash
curl -sS -H 'Host: 13.51.0.0' http://127.0.0.1:8001/api/health
```

Then open `http://13.51.0.0:8001` in a browser. Sign up, and you should land in the
workspace immediately — there is no confirmation email to wait for, and those same
details sign you back in afterwards.

Accounts imported from the earlier prototype only need to finish onboarding. Former
`is_staff` users are **not** promoted to superusers; grant moderators explicit group
permissions, and never give them billing, account-change or financial permissions.

## 7. Later: a domain name and HTTPS

When the domain exists, point an A record at the Elastic IP and then:

1. Change the published port in `compose.yaml` back to loopback only —
   `ports: ['127.0.0.1:8001:8001']` — so nothing reaches Gunicorn except the proxy.
2. Change one line in `.env.local`:
   `SOUNDBRIDGE_PUBLIC_ORIGIN=https://app.example.com`. That scheme is what turns on the
   HTTPS redirect, HSTS, Secure cookies and the forwarded-protocol header; no other
   setting changes.
3. Install Nginx and a certificate, and proxy to `127.0.0.1:8001`:

```nginx
server {
    listen 80;
    server_name app.example.com;
    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8001;

        # ALLOWED_HOSTS and the application's own origin policy both check the Host
        # header. Without this, Nginx forwards `127.0.0.1` and every request is 403.
        proxy_set_header Host $host;

        # Django only learns the original scheme from this header, and redirects to
        # HTTPS whenever it is missing. Nginx sets it from the real connection, which
        # also stops a client forging it.
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_redirect off;
        proxy_read_timeout 90s;
    }
}
```

```bash
sudo apt-get install -y nginx
sudo ln -sf /etc/nginx/sites-available/soundbridge /etc/nginx/sites-enabled/soundbridge
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

sudo snap install --classic certbot && sudo ln -sf /snap/bin/certbot /usr/bin/certbot
sudo certbot --nginx -d app.example.com
sudo certbot renew --dry-run
```

Then close 8001 in the security group and open 80 and 443. Serve exactly one hostname:
`ALLOWED_HOSTS` is derived from the origin and contains only that host, so redirect `www.`
in a separate server block rather than proxying it.

Static files need no Nginx configuration either way: the Docker build runs `collectstatic`
and WhiteNoise serves the result from Gunicorn with hashed filenames and compression.

## 8. Release gates

`launch_check` fails closed, and a passing test suite does not satisfy it:

```bash
docker compose run --rm web python manage.py launch_check
```

It verifies the configuration it can see — a public origin, MySQL, a malware scanner, a
non-console email backend, an artifact encryption key, a moderation model, email
verification — and then reports what it cannot certify on its own:

- **19 approved launch decisions**, each recorded in the admin with a named owner and the
  decision text: launch markets, legal entity, terms and privacy copy, email and payment
  providers, plan prices and limits, cancellation and refunds, retention and deletion, AI
  processing and escalation, moderation owner, royalty formats and rates, reviewed
  education content, hosting encryption, backup/restore evidence, browser and
  accessibility evidence, security and load evidence, AI evaluation evidence, and support
  and incident owners.
- **A payment provider.** Checkout, the webhook and reconciliation are implemented against
  `billing.providers.Provider`, but no provider is selected. Implement one subclass,
  register it, and set `SOUNDBRIDGE_BILLING_PROVIDER`. Until then checkout and the webhook
  refuse to act rather than pretending to charge anyone.
- **An approved `Plan`.** Capability limits come from approved plan rows. On a public
  origin with no approved plan, entitlements are closed.
- **An approved `RetentionPolicy`.** Without one, exports, deletions and retention trimming
  never run. Nothing here has a default.
- **A recorded AI evaluation run** against the configured model with no failing cases:
  `load_ai_evaluations`, then `run_ai_evaluations --fail-on-regression`. These call the
  provider and cost money, so they are deliberate.
- **No private bytes left in database columns.** Run `migrate_private_bytes` if it reports
  any; it is safe to re-run, and `--dry-run` reports what would move.

It also blocks while email verification is off, because an address is then never proven to
belong to the person who typed it and password recovery mails a reset link to an unproven
address. That is a deliberate product decision for the pilot, not a bug — but it is one to
record rather than forget. Either set `SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION=true` before
launch, or accept it explicitly and delete that check in
`operations/management/commands/launch_check.py`.

## 9. Running it

Celery already runs as the `worker` and `scheduler` services. The scheduler delivers queued
email every minute, scans and parses uploads every minute, sends reminders every 15
minutes, processes privacy requests every 5 minutes and applies retention hourly. Run
exactly one scheduler: scaling `worker` is fine, scaling `scheduler` duplicates every job.

```bash
docker compose logs -f web worker scheduler
docker compose ps
```

Request logs are JSON on stdout, through a formatter that keeps message text out of them.
Watch for `EmailDelivery` rows in the `failed` state — delivery retries eight times with
backoff and then stops, deliberately visibly.

Keep the scanner signatures current. A weekly refresh is the minimum:

```bash
( crontab -l 2>/dev/null; echo "0 4 * * 1 cd /srv/soundbridge && docker compose run --rm web freshclam" ) | crontab -
```

### Backups

The database and the private artifacts reference each other, and the artifacts are useless
without the Fernet key. Back up all three together, and store them off the instance — an
EBS snapshot of the instance you are backing up is not a backup.

Write `/usr/local/bin/soundbridge-backup`:

```bash
#!/bin/bash
set -euo pipefail
cd /srv/soundbridge
stamp=$(date -u +%Y%m%dT%H%M%SZ)
dest=/var/backups/soundbridge
mkdir -p "$dest"
# --single-transaction takes a consistent InnoDB snapshot without locking writers.
docker compose exec -T db sh -c \
  'exec mysqldump --single-transaction --routines --triggers \
     -u root -p"$MYSQL_ROOT_PASSWORD" soundbridge' \
  | gzip > "$dest/db-$stamp.sql.gz"
docker compose run --rm -T web tar -cz -C /app/.data artifacts > "$dest/artifacts-$stamp.tar.gz"
aws s3 sync "$dest" "s3://your-backup-bucket/soundbridge/" --sse AES256
find "$dest" -type f -mtime +7 -delete
```

```bash
sudo chmod +x /usr/local/bin/soundbridge-backup
( crontab -l 2>/dev/null; echo "30 2 * * * /usr/local/bin/soundbridge-backup" ) | crontab -
```

A backup you have not restored is a hypothesis. Restore into a scratch instance, sign in as
a real account, open a statement and download an export — that last step is the one that
proves the key you saved is the key the artifacts were written with. Record the recovery
point and recovery time you actually measured; `backup-restore-evidence` is one of the
launch decisions.

## 10. Updating and rolling back

```bash
cd /srv/soundbridge
git fetch --tags
git checkout <new-tag>

/usr/local/bin/soundbridge-backup          # before the migration, not after

docker compose build
docker compose run --rm web python manage.py migrate
docker compose up -d
docker compose run --rm web python manage.py launch_check
```

Rehearse migrations against a copy of the production database first;
`tools/rehearse_migrations.py` exists for that. Expect a few seconds of downtime while the
containers restart.

Rolling code back does **not** reverse a data migration. A rollback means checking out the
previous tag *and* restoring the database snapshot taken beside it, which loses everything
written since. Keep the code tag and its snapshot together.

## 11. When something is wrong

| Symptom | Cause |
| --- | --- |
| Every page is `403 This host is not configured for SoundBridge.` | The address in the browser does not match `SOUNDBRIDGE_PUBLIC_ORIGIN`. It must be the same IP or hostname, character for character. |
| The browser reports a redirect loop | `SOUNDBRIDGE_PUBLIC_ORIGIN` starts with `https://` while the site is served over plain HTTP. Use `http://<ip>:8001` until a proxy terminates TLS. |
| Sign-in appears to work but every page asks you to sign in again | Same cause: an `https://` origin makes the session cookie `Secure`, so the browser never stores it over HTTP. |
| The page does not load at all from outside | Port 8001 is not open in the security group, or `compose.yaml` is still publishing to `127.0.0.1`. |
| The container exits with `SOUNDBRIDGE_SECRET_KEY is required` | A public origin is configured with no secret key. Both live in `.env.local`. |
| Signup reports that registration is closed | Setting a public origin closes registration by default. Set `SOUNDBRIDGE_ALLOW_SIGNUP=true`. |
| `docker compose up` fails on `MYSQL_PASSWORD` | `/srv/soundbridge/.env` is missing; Compose interpolates that variable and `MYSQL_ROOT_PASSWORD` from it. |
| `web` restarts while `db` is still starting | MySQL's first-run initialisation takes longer than PostgreSQL's. The health check allows 100 seconds; if your instance is slower, raise `retries` on the `db` service. |
| Uploads stay quarantined forever | `freshclam` has never run, or `clamscan` is being OOM-killed. Check free memory. |
| AI requests are refused | `SOUNDBRIDGE_MODERATION_MODEL` is unset. On a public origin, an unavailable moderation check blocks the request rather than letting content through. |

## Appendix: without Docker

To run the services directly under systemd instead:
`apt-get install python3.12-venv mysql-server redis-server clamav pkg-config default-libmysqlclient-dev build-essential`
(the last three are needed because `mysqlclient` has no Linux wheel and is compiled during
`pip install`). Create a virtualenv, `pip install -r requirements.lock`, create the
database and user in MySQL, put the same variables in `/etc/soundbridge.env` (referenced by
`EnvironmentFile=`), and write three units — Gunicorn on `config.wsgi:application` bound to
`0.0.0.0:8001`, `celery -A config.celery worker`, and one `celery -A config.celery beat`.
Run `collectstatic` as part of every deploy, because nothing else will. Set
`SOUNDBRIDGE_MALWARE_SCANNER=/usr/bin/clamscan` and `MYSQL_HOST=127.0.0.1`. Backups, the
release gates and the rollback rules are unchanged.
