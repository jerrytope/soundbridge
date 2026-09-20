# Running the Django MVP implementation

This implementation is not launch-certified. Run `python manage.py launch_check` for explicit blockers. The PRD completion plan remains the baseline; `plans/mvp_implementation_status.md` records implemented work and outstanding gates.

## Local setup

Use Python 3.12 or newer. Create a virtual environment, install `requirements.txt`, back up the existing SQLite database, then run `python manage.py migrate` and `python manage.py runserver`. Additive migrations preserve legacy rows. The five initial migration edits predate this implementation and were not rewritten.

Existing accounts must verify their email and complete missing onboarding. Former `is_staff` users do not automatically become superusers: use `createsuperuser` for a controlled administrative account and grant explicit group permissions to moderators. Never grant moderators billing, account-change, or financial permissions by default.

Email verification is switched off by default (`SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION`), so accounts are usable the moment they are created and no confirmation message is sent; `launch_check` blocks while that is the case. With it enabled, verification messages enter the durable outbox. Run `python manage.py deliver_email` locally; the console backend prints development emails. Configure a real email backend for external delivery. Password recovery currently sends through Django's configured mail backend directly. Do not use the console backend in production because recovery and verification links are sensitive.

## Background work

Start Redis, then run `celery -A config.celery worker --loglevel=INFO` and exactly one `celery -A config.celery beat --loglevel=INFO`. Jobs deliver emails every minute, scan/parse pending uploads every minute, and emit reminders every 15 minutes. The same work can be run manually:

- `python manage.py deliver_email`
- `python manage.py process_statements`
- `python manage.py scan_files`
- `python manage.py send_reminders`
- `python manage.py process_privacy_requests` (exports and account deletions)
- `python manage.py apply_retention` (expired artifacts, audit and notification trimming)
- `python manage.py reconcile_billing` (once a payment provider adapter exists)

Set `SOUNDBRIDGE_MALWARE_SCANNER` to the installed `clamscan` executable and maintain its signature database. Unavailable scanners, timeouts, and rejected files never produce downloadable files or imported income. The CSV parser runs as a separate isolated Python process with Linux CPU/memory bounds.

Email delivery retries at most eight times with backoff. A message that exhausts its retries is marked `failed` with the error class that stopped it, so delivery problems stay visible instead of disappearing; monitor `EmailDelivery` rows in that state. A process failure after a successful SMTP send but before the database commit can cause duplicate email; no exactly-once delivery guarantee is made.

## Private files

Profile images, original statement uploads and generated exports are held as private artifacts outside the database, under `SOUNDBRIDGE_PRIVATE_STORAGE_ROOT` (default `.data/artifacts`). Set `SOUNDBRIDGE_PRIVATE_STORAGE_KEY` to a Fernet key and the bytes on disk are ciphertext; a deployment with a public origin refuses to store an artifact without one. Generate a key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and keep it with your other secrets: losing it makes existing artifacts unreadable.

Run `python manage.py migrate_private_bytes` once after upgrading to move existing database-held bytes into the store; it is safe to re-run and `--dry-run` reports what would move. Back up the artifact directory together with the database, since one references the other.

## Privacy processing

Exports and account deletions are carried out by `process_privacy_requests`, and only when a `RetentionPolicy` has been approved in the admin by a named owner referencing its decision. The policy supplies the deletion grace period, how long an export stays downloadable, how audit and notification history is trimmed, and what happens to messages the departing account sent into someone else's thread: delete them, or keep the text with the sender identity removed. Deletion is recorded in the audit trail with the account identifier before the row is removed. Nothing here has a default: an unapproved policy means nothing is processed.

## Container configuration

`Dockerfile` runs Django/Gunicorn; `compose.yaml` supplies web, worker, scheduler, MySQL and Redis. Create `.env.local`, export a strong `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD` for Compose interpolation, and inspect `docker compose config` locally without sharing its secret values. Build the image, run migrations as a one-off job, initialize/update ClamAV signatures, then start the services. Do not run migrations concurrently from each web worker.

Only the web port is bound, to loopback. A production deployment still requires HTTPS ingress, a trusted proxy configuration, managed secrets, encrypted database/backup volumes, scanner updates, health probes and tested backup recovery. Container database volumes are not automatically encrypted. The Docker build collects static assets and WhiteNoise serves them. No Vercel/Node deployment is supported by the new Django runtime.

## Migration and recovery

Back up databases and private bytes together. Rehearse additive migrations against a copy before changing the application database. Reconcile counts, ownership, currency totals, image references and representative logins. Keep the previous application release and database snapshot together: rolling code back alone does not reverse data changes. Restoring a snapshot loses changes after that snapshot; schedule cutovers and capture the accepted recovery point and recovery time in the launch decisions.

SQLite local backup example: use Python's `sqlite3.Connection.backup`, which handles WAL correctly; copying the main database file alone while the application is running is insufficient. MySQL backup/restore (`mysqldump --single-transaction`) and encrypted storage evidence must be verified in the actual hosting environment before launch.

## API and compatibility

`docs/openapi.json` documents the implemented `/api/v1/` resource routes. Browser mutations use a Django session, CSRF token and UUID `Idempotency-Key`. Reusing a key with different content returns 409. Lists paginate at 20 rows and monetary values are decimal strings. The legacy workspace `PUT` returns 410; legacy reads and internal Node imports remain. The archived React/Node reference app is not a supported production client for these changes.

The contract now covers profiles, goals, credits, connections, messages, collaborations, opportunities, royalty calculations, statements and transactions, manual income, release projects, notifications, AI conversations, subscriptions, entitlements and reports. A `402` response means an approved plan limit was reached. Remaining collaboration, privacy and opportunity operator workflows still use Django forms, and richer response schemas remain release work.

## Plans, entitlements and billing

Capability limits come from approved `Plan` rows: `ai_daily`, `release_plans`, `active_collaborations`, `saved_calculations`, `statements` and `connection_requests_daily`. A capability missing from a plan is disabled. While no plan is approved and no public origin is configured, limits are not enforced, which keeps development usable; a public deployment with no approved plan is closed. Downgrades never delete data — an account over its new limit keeps everything and simply cannot add more.

Checkout, the webhook and reconciliation are implemented against `billing.providers.Provider`; no provider is chosen, so `SOUNDBRIDGE_BILLING_PROVIDER` is unset and both checkout and the webhook refuse to act. Selecting a provider means implementing one subclass, registering it and setting that variable. Entitlement changes only ever follow a signature-verified webhook event or a reconciliation read; the browser redirect after checkout grants nothing.

## AI safety and evaluations

Set `SOUNDBRIDGE_MODERATION_MODEL` to the provider moderation model. Messages are moderated before they reach the model and replies before they are shown; on a public origin an unconfigured or unavailable moderation check blocks the request rather than letting content through. Every model call records latency, token counts, model and prompt version in `ModelCall`, never message text.

Load the starter evaluation cases with `python manage.py load_ai_evaluations` and run them with `python manage.py run_ai_evaluations --fail-on-regression`. Runs call the provider and cost money, so they are deliberate. `launch_check` requires a recorded run, against the configured model, with no failing cases.

## Tests and release gates

Run `python manage.py test`, `python manage.py makemigrations --check --dry-run`, and `python manage.py collectstatic --noinput`. For the browser smoke test, install Playwright and Chromium, then run `python tools/browser_smoke.py --app-python /path/to/app/venv/bin/python`. It creates a temporary database, never the user's database, and exercises two real browser sessions.

The automated suite does not replace manual keyboard/screen-reader review, the supported-browser matrix, MySQL concurrency/load testing, production security review, live model/provider evaluations, restore tests or product acceptance. CI is configured for MySQL and the browser smoke path, but a workflow file is not evidence that hosted CI has passed.
