# Running SoundBridge locally on Windows

**Short answer: you do not need Docker.** The app runs directly on Python with a local
SQLite file. Docker is only for reproducing the production stack (MySQL, Redis,
Celery workers, ClamAV). Start with the plain Python route below; read
[Optional: the Docker stack](#optional-the-docker-stack) only if you need background jobs
or MySQL.

---

## What the app actually is

The backend is Django (`manage.py`, `config/`), serving both the HTML screens in
`templates/` and the JSON API under `/api/` and `/api/v1/`. The `src/`, `server/` and
`package.json` files are the archived React/Node original — they are **not** what you run.
Ignore `npm run dev` unless you are specifically working on the legacy React reference app.

## Prerequisites

- **Python 3.12 or newer.** You already have 3.12.3 and 3.13.3 on this machine. Use 3.12
  to match `Dockerfile` and the lockfile.
- Git, and about 300 MB free for the virtual environment.
- No database server, no Redis, no Node — not for the default setup.

## First-time setup

Run these from the repository root (`C:\Users\HP\Documents\temitope\soundbridge`) in
PowerShell.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_creators
```

If `Activate.ps1` is blocked by execution policy, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again.

`migrate` creates `.data/django.sqlite3`. That single file holds accounts, profiles,
connections, collaborations, releases, royalty data, images, AI conversations and sessions.
Back it up together with `.data/artifacts/` (private files reference each other).

`seed_creators` loads sample creator records for browsing. It is disabled on public
deployments and is safe to skip.

## Every time you work

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000>.

**Use the same hostname consistently.** `localhost` and `127.0.0.1` keep separate cookies,
so switching between them silently logs you out. Development mode accepts loopback
connections only.

### Create an account

Sign up through the UI. Verification email goes into a durable outbox rather than being
sent — with the default console backend you flush it and read the link in your terminal:

```powershell
python manage.py deliver_email
```

For an admin account:

```powershell
python manage.py createsuperuser
```

Staff status alone grants no permissions; assign explicit group permissions in the admin.

## Configuration (`.env.local`)

Server-only settings live in `.env.local`, which is git-ignored. `config/env.py` reads
`.env.example` first and then `.env.local`, and real environment variables override both.
Your `.env.local` currently holds only `VERCEL_OIDC_TOKEN`, which means you are on the
SQLite default — that is the intended local setup.

Nothing is required to boot. Add keys only for the features you want:

| Feature | Keys | Screen to verify |
| --- | --- | --- |
| AI assistants | `OPENAI_API_KEY`, `OPENAI_MODEL` | `/assistants` |
| Spotify catalog search | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | `/music-search` |
| Upload scanning | `SOUNDBRIDGE_MALWARE_SCANNER` (path to `clamscan`) | `/royalty-upload` |

Restart the server after editing `.env.local`; values are cached per process.

Two things to expect locally:

- **Leave `MYSQL_DATABASE` empty.** Setting it switches Django to MySQL and the app will
  fail to start without a running server. Empty means SQLite.
- **Signing up logs you straight in.** Email verification is switched off; set
  `SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION=true` in `.env.local` to exercise that flow.
- **Uploads stay quarantined** while `SOUNDBRIDGE_MALWARE_SCANNER` is unset. ClamAV is not
  packaged for Windows here, so CSV statement imports will not complete on the plain Python
  route. Use the Docker stack if you need to exercise that flow.

## Background jobs without Docker

Celery and Redis schedule the recurring work, but every job is also a management command
you can run by hand when you need it:

```powershell
python manage.py deliver_email             # flush the email outbox
python manage.py process_statements        # parse uploaded royalty CSVs
python manage.py scan_files                # scan quarantined uploads
python manage.py send_reminders
python manage.py process_privacy_requests  # exports and deletions
python manage.py apply_retention
python manage.py reconcile_billing
```

`process_privacy_requests` does nothing until a retention policy is approved in the admin —
that is deliberate, not a bug.

## Checks and tests

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
python manage.py launch_check              # lists remaining release blockers
```

`launch_check` is expected to fail: this build is not launch-certified.

## Optional: the Docker stack

Use this when you want MySQL, Redis, the Celery worker and scheduler, and working
malware scanning — i.e. the production shape. You need Docker Desktop running.

```powershell
$env:MYSQL_PASSWORD = "<a strong password>"
$env:MYSQL_ROOT_PASSWORD = "<another strong password>"
docker compose config                      # inspect; do not share the output
docker compose build
docker compose run --rm web python manage.py migrate
docker compose up
```

Notes:

- `compose.yaml` requires `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD` in your shell or a
  Compose env file; it refuses to start without them.
- It also expects `.env.local` to exist (it does).
- The web port is published on every interface as `8000`, so this stack is reached at
  <http://127.0.0.1:8000> rather than the runserver port above.
- Run migrations as the one-off job above, never concurrently from each web worker.
- This stack uses MySQL, so it does **not** share data with your SQLite file.
- Stop with `docker compose down`; add `-v` only if you intend to destroy the database
  volume.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `django.db.utils.OperationalError` on start | `MYSQL_DATABASE` is set in `.env.local` but no MySQL is running. Clear it. |
| Logged out when navigating | You switched between `localhost` and `127.0.0.1`. Pick one. |
| No verification email | Verification is off by default, so none is sent. With it on, the console backend queues it; run `python manage.py deliver_email`. |
| CSV upload stuck in quarantine | No malware scanner configured. Expected on Windows without Docker. |
| AI status shows configured but requests fail | The indicator only checks that a key is present; billing and model access are proven only by a real request. |
| `docker compose` errors about `MYSQL_PASSWORD` | Export it and `MYSQL_ROOT_PASSWORD` in the shell before running any compose command. |

## Related documents

- [BACKEND_SETUP.md](BACKEND_SETUP.md) — API contract, OpenAI and Spotify integration detail
- [docs/MVP_OPERATIONS.md](docs/MVP_OPERATIONS.md) — workers, private storage, privacy processing, recovery
- [DEPLOYMENT.md](DEPLOYMENT.md) — production deployment
