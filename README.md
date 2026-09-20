# SoundBridge

A Django workspace for music creators: professional profiles, discovery, connections, collaboration, release planning, royalty records and governed AI assistance.

The [MVP completion plan](plans/mvp_completion_plan.md) and [implementation status](plans/mvp_implementation_status.md) distinguish implemented workflows from remaining PRD requirements. **This build is not production-launch certified.** Checkout, complete retention/deletion processing, private object storage, full API coverage and production acceptance remain outstanding.

## Run locally

Use Python 3.12 or newer:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Back up an existing database before migrations. `tools/rehearse_migrations.py` migrates a temporary copy and checks preservation of existing domain values:

```sh
python tools/rehearse_migrations.py .data/django.sqlite3
```

SQLite at `.data/django.sqlite3` is the local default. MySQL 8.0.16+ is configured through `MYSQL_*` environment variables and is what production runs on. Actual environment variables override `.env.local`; secrets must not be committed. The runtime is pinned in `requirements.lock`.

Email verification is switched off: signing up creates the account, signs it in and marks it verified, so the details used to sign up are the details used to sign in. The verification flow is still implemented and is restored by setting `SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION=true`, at which point `python manage.py deliver_email` delivers queued messages through the configured backend. New accounts still accept versioned terms/privacy and complete persistent goal-based onboarding. Configure an email provider before public signup: password recovery sends through it regardless. Never use console email logging for production tokens.

## Main workflows

- `/settings/professional`: publish a real profile, control field visibility, add sourced credits and portfolio links.
- `/discover`, `/people/<username>`, `/connections`: find real published profiles and manage requests, blocks and reports.
- `/collaborations`: create a brief and open its workspace for invitations, milestones, messages, files and versioned split proposals.
- `/opportunities`: browse operator-reviewed records, save listings, open external application links and track your own application status.
- `/release-planner`: create plans; open a release to edit stage, campaign, metadata readiness and dated tasks.
- `/royalty-calculator`: calculate and save low/mid/high educational scenarios with documented assumptions and decimal arithmetic.
- `/royalty-upload`: quarantine CSV files, review mappings after scanning, confirm or correct imports, export and delete statements.
- `/royalties/income`, `/royalties/summary`, `/royalties/education`: manual income, grouped currency-aware reporting and rights explanations.
- `/assistants`: original specialists plus the missing PRD roles, explicit context permissions, feedback/reporting and conversation deletion.
- `/notifications`, `/settings/privacy`, `/membership`: notification preferences, authenticated export/deletion requests and approved plan information.

Sample creators remain legacy records; the production discovery page does not show them. `seed_creators` is disabled on public deployments. Opportunity applications are completed on external sites; saving a draft or opening a link does not submit an application. Spotify remains public catalog search, not an account or royalty-data connection.

## Jobs and administration

See [Django operations](docs/MVP_OPERATIONS.md) for workers, email, scanning, deployment and recovery. The background commands are `deliver_email`, `process_statements`, `scan_files`, `send_reminders`, `process_privacy_requests`, `apply_retention` and `reconcile_billing`. Celery and Redis schedule them in the container setup.

Uploads remain quarantined if malware scanning is unavailable. Configure `SOUNDBRIDGE_MALWARE_SCANNER` and maintain scanner signatures.

Private files — profile images, original statement uploads and generated exports — are held outside the database under `SOUNDBRIDGE_PRIVATE_STORAGE_ROOT`, encrypted at rest when `SOUNDBRIDGE_PRIVATE_STORAGE_KEY` holds a Fernet key. Run `python manage.py migrate_private_bytes` once to move existing rows; back up that directory with the database.

Data exports and account deletions are carried out by `process_privacy_requests`, and only once a retention policy has been approved in the admin by a named owner. That policy supplies the deletion grace period, export availability window, audit and notification retention, and whether messages sent into someone else's thread are deleted or kept with the sender identity removed. Nothing is deleted on a default.

Create a controlled admin account with `python manage.py createsuperuser`. Staff status alone grants no permissions. Use separate roles for moderation, commercial approvals and account administration. Reviewed policies and evidence are recorded as launch decisions. `python manage.py launch_check` fails while release gates remain.

## API and tests

The implemented resource contract is [docs/openapi.json](docs/openapi.json), covering profiles, goals, credits, connections, messages, collaborations, opportunities, royalty calculations, statements and transactions, manual income, release projects, notifications, AI conversations, subscriptions, entitlements and reports. `/api/v1/` mutations require session authentication, CSRF and a UUID `Idempotency-Key`; a `402` means an approved plan limit was reached. Legacy `PUT /api/workspace` is retired with 410 because replacing the whole workspace can destroy shared records. Money in JSON is represented as decimal strings.

Plan limits (`ai_daily`, `release_plans`, `active_collaborations`, `saved_calculations`, `statements`, `connection_requests_daily`) come from approved `Plan` rows and are enforced across the screens and the API. Downgrading never deletes anything. Checkout, verified webhooks and reconciliation are implemented against a provider adapter; until `SOUNDBRIDGE_BILLING_PROVIDER` names an implemented adapter, checkout and the webhook refuse to act rather than simulate a charge.

AI messages and replies pass a moderation check (`SOUNDBRIDGE_MODERATION_MODEL`), which fails closed on a public origin, and every model call records latency and token counts without message text. Evaluation cases load with `load_ai_evaluations` and run with `run_ai_evaluations --fail-on-regression`.

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
python manage.py collectstatic --noinput
```

The browser test uses a disposable database and two browser sessions:

```sh
pip install playwright
playwright install --with-deps chromium
python tools/browser_smoke.py --app-python /absolute/path/to/.venv/bin/python
```

CI targets MySQL and Chromium. Automated results do not replace manual accessibility, supported-browser, security, load, live-provider, backup-restoration or product acceptance evidence.

## Repository history

The earlier React/Node implementation remains under `src/` and `server/` as a reference, and its historical parity plan remains in `plans/implementation_plan.md`. The current `Dockerfile` and `compose.yaml` deploy Django. The legacy Node/Vercel configuration is not a production deployment path for this implementation.
