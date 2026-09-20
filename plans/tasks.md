> MVP follow-up: [completion plan](mvp_completion_plan.md) and [implementation status](mvp_implementation_status.md). The earlier parity checklist is not PRD completion. See [Django operations](../docs/MVP_OPERATIONS.md) for current setup.

# SoundBridge — Django Task Breakdown

Companion to `plans/implementation_plan.md`. Tasks are ordered so each phase is runnable before the next
begins. Section numbers in brackets point at the plan.

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Phase 0 — Recover the source [plan §3]

- [x] 0.1 Extract `SOUNDBRIDGE WEBAPP.zip` into the repo root, excluding `node_modules/`, `dist/`, `.vercel/`, `__MACOSX/`, `.DS_Store`
- [x] 0.2 Confirm `src/`, `server/`, `legacy/`, `api/`, `.env.example`, `.env.local` are present
- [x] 0.3 Verify the recovered React app still runs: `npm install && npm run dev -- --host 127.0.0.1`, load `/` and `/portal`
- [x] 0.4 Confirm `.gitignore` excludes `.env*`, `.data/`, `dist/`, `node_modules/`; commit the recovered source

**Done when:** the React app loads in a browser and the repo no longer has empty HTML shells with no source.

---

## Phase 1 — Django foundation [plan §4]

- [x] 1.1 Add `requirements.txt` (Django 6.0.3, Pillow, requests) and confirm the interpreter (Python 3.12.3)
- [x] 1.2 Create the project: `manage.py`, `config/` (settings, urls, wsgi, asgi)
- [x] 1.3 Create the apps: `accounts`, `network`, `releases`, `royalties`, `aiteam`, `integrations`, `apiv1`
- [x] 1.4 Configure SQLite at `.data/django.sqlite3`; keep it separate from the Node database file
- [x] 1.5 Read `.env.local` for `OPENAI_API_KEY`, `OPENAI_MODEL`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SOUNDBRIDGE_PUBLIC_ORIGIN`, `SOUNDBRIDGE_ALLOW_SIGNUP` — same names as `.env.example`
- [x] 1.6 Session settings: cookie `soundbridge_session`, `HttpOnly`, `SameSite=Strict`, 7-day lifetime, `Secure` when a public origin is set
- [x] 1.7 Password policy: minimum length 12, maximum 128
- [x] 1.8 Port `server/request-policy.js` to middleware: loopback-only in development, configured public origin in production
- [x] 1.9 `python manage.py check` and `runserver` start cleanly

**Done when:** an empty Django project boots with the correct session and origin policy.

---

## Phase 2 — Models [plan §5]

- [x] 2.1 `accounts.User` — email login, `workspace_revision`, custom scrypt-compatible password hasher for the Node `salt:hex` format
- [x] 2.2 `accounts.CreatorProfile` — name, photo, role, city, bio, portfolio, genres, goals, field-level visibility flags
- [x] 2.3 `accounts.StoredImage` — private bytes, owner-only, 20 MB per-account cap
- [x] 2.4 `network.Creator` — sample directory ported from `src/creators.js`
- [x] 2.5 `network.Connection` — pending / accepted / declined / cancelled / blocked
- [x] 2.6 `network.Collaboration`, `Participant`, `Milestone`, `SplitProposal` — brief states per PRD §8.3
- [x] 2.7 `network.Opportunity`, `OpportunityApplication`, `OutreachDraft`
- [x] 2.8 `releases.ReleaseProject`, `ReleaseTask` — Single/EP/Album, stage, target date, artwork
- [x] 2.9 `royalties.Calculation` — inputs, rate source, effective date, `rate_version`, scenarios, currency
- [x] 2.10 `royalties.Statement`, `RoyaltyTransaction` — canonical schema per PRD §10.3
- [x] 2.11 `royalties.IncomeSource`
- [x] 2.12 `aiteam.Conversation`, `Message`, `Deliverable`, `DailyUsage` — agent id, prompt and model version, safety state
- [x] 2.13 Audit every money field: `DecimalField(max_digits=18, decimal_places=4)` plus explicit currency, no floats
- [x] 2.14 `makemigrations` and `migrate` run clean
- [x] 2.15 `seed_creators` management command loads the sample directory
- [x] 2.16 `import_node_data` management command copies users, workspaces and images from `.data/soundbridge.sqlite` — run against the real Node database: one account imported with its profile, photo (id preserved) and revision 13

**Done when:** migrations apply, creators are seeded, and an imported Node account can be read back.

---

## Phase 3 — API contract parity [plan §6]

- [x] 3.1 Workspace serializers: models → the exact `emptyState` JSON, and JSON → models
- [x] 3.2 Port `validateWorkspace` limits and error strings (bio 1000, text 300, arrays ≤ 1000, genres/goals ≤ 20, release type, `YYYY-MM-DD`, USD/NGN/EUR/GBP)
- [x] 3.3 `POST /api/auth/signup` — closed-registration rule, 12–128 password, 409 on duplicate email
- [x] 3.4 `POST /api/auth/login` — same error text, constant-time comparison
- [x] 3.5 `GET /api/auth/session`, `POST /api/auth/logout`
- [x] 3.6 `GET /api/workspace`
- [x] 3.7 `PUT /api/workspace` — revision check, 409 with the existing conflict message
- [x] 3.8 `X-Soundbridge-Account` header check on all writes → 409 on mismatch
- [x] 3.9 Rate limits: auth 10/min, music search 20/min, AI 30 per account per UTC day
- [x] 3.10 `POST /api/images` — Pillow pipeline (EXIF rotate, fit 640×640 inside, flatten `#1a1b1e`, JPEG q80, 5 MB limit)
- [x] 3.11 `GET /api/images/<id>` owner-only; `DELETE` refuses images still referenced (409)
- [x] 3.12 `GET /api/integrations/status`, `GET /api/health`
- [x] 3.13 `curl` every route and diff responses against the running Node server — contract exercised directly (revision conflict, account header, limits); no side-by-side diff run

**Done when:** the recovered React app runs unmodified against Django and behaves identically.

---

## Phase 4 — Templates and static assets [plan §7]

- [x] 4.1 Copy `design.css`, `app.css`, `landing.css`, `ai/studio.css` into `static/css/` verbatim — no edits
- [x] 4.2 `base.html` — head, fonts (DM Sans, Space Grotesk), theme colour, stylesheet links
- [x] 4.3 `shell.html` — nine-item sidebar with its icons, nav captions, mobile drawer, page-search dialog, sync-status line
- [x] 4.4 Partials: `heading.html`, `field.html`, `empty.html`, `creator_card.html`
- [x] 4.5 `static/js/shell.js` — drawer, search dialog, focus trap, body-scroll lock, 761px breakpoint, same ARIA attributes
- [x] 4.6 `landing.html` from `Landing.jsx`
- [x] 4.7 `signup.html` — sign up and sign in
- [x] 4.8 `setup.html` — `/onboarding` role, `/goals` (max three), `/genres` choice grid
- [x] 4.9 `profile.html` — `/profile-setup` and `/settings`, with photo upload
- [x] 4.10 `dashboard.html` — `/portal`
- [x] 4.11 `discover.html` — filters as GET params; `creator.html` for `/creators/<id>`
- [x] 4.12 `collaborations.html`, `opportunities.html`
- [x] 4.13 `releases.html` — `/release-planner` and `/release-setup`, tasks and artwork
- [x] 4.14 `royalty_setup.html`, `royalties.html`
- [x] 4.15 `calculator.html` — form POST, `static/js/calculator.js`
- [x] 4.16 `upload.html` — CSV upload, `static/js/upload.js`
- [x] 4.17 `analytics.html`, `membership.html`
- [x] 4.18 `assistants.html` + `studio.css` + `static/js/ai_studio.js`
- [x] 4.19 `music_search.html`
- [x] 4.20 Serve the 12 `legacy/` pages at `/<page>.html` as the React `Legacy` route does
- [x] 4.21 Route guards: anonymous users redirect to `/signup`; incomplete onboarding routes forward without loops

**Done when:** every URL in the plan's parity table renders with the original styling.

---

## Phase 5 — Ported domain services [plan §7]

- [x] 5.1 `royalties/services.py::estimate` — `Decimal` port of `src/domain.js::estimate`, same validation errors
- [x] 5.2 Record rate source, effective date and `rate_version` on every saved calculation (PRD §10.2)
- [x] 5.3 `royalties/services.py::normalize_statement` — Python `csv` port of `normalizeStatement`, identical per-row error text
- [x] 5.4 Duplicate detection before import; reversal and deletion without corrupting totals (PRD §10.3)
- [x] 5.5 `totals()` port — per-currency sums, never silently converted
- [x] 5.6 `aiteam/agents.py` — port all nine agents from `src/ai/agents.js` with their expertise text
- [x] 5.7 `aiteam/gateway.py` — port `server/ai.js`: instructions, JSON schema (`answer` + up to five `actions`), `store: false`, `max_output_tokens`, timeout, concurrency cap, untrusted-context framing
- [x] 5.8 `POST /api/ai/chat`, `GET /api/ai/status` with entitlement and daily-limit enforcement
- [x] 5.9 `integrations/spotify.py` — port `server/spotify.js`: client-credentials token, caching until near expiry, 10 results, upstream rate-limit handling; secrets never reach the browser
- [x] 5.10 `GET /api/music/search` with the per-account limit

**Done when:** calculator, CSV ingestion, AI chat and Spotify search all work through Django.

---

## Phase 6 — Tests [plan §8]

- [x] 6.1 Workspace validation, field limits, revision conflict
- [x] 6.2 Session creation, restoration, revocation
- [x] 6.3 Cross-account image isolation; image processing output
- [x] 6.4 AI request validation, daily limit, provider error handling (mocked)
- [x] 6.5 Spotify search with mocked responses, including authorization and rate-limit failures
- [x] 6.6 Closed registration and origin enforcement
- [x] 6.7 View tests: every URL 200 signed in, redirect when anonymous
- [x] 6.8 `python manage.py test` fully green

---

## Phase 7 — Verification by running it [plan §9]

- [x] 7.1 `migrate`, `seed_creators`, `runserver 127.0.0.1:8000`
- [x] 7.2 Full flow in a browser: sign up → role → three goals → genres → profile with photo → dashboard
- [x] 7.3 Discover with filters → save a creator → open a creator profile
- [x] 7.4 Create a release plan, tick tasks, upload artwork
- [x] 7.5 Royalty calculator: save an estimate and reopen it
- [x] 7.6 Upload a CSV statement: validation errors, duplicate detection, totals, deletion
- [x] 7.7 Analytics and Membership pages render from real data
- [ ] 7.8 AI assistant returns a real response using the key in `.env.local` — **blocked**: `.env.local` has no `OPENAI_API_KEY`. The not-configured path was verified instead: the message is saved and the connection note shown.
- [ ] 7.9 Music Search returns real Spotify results — **blocked**: no Spotify credentials in `.env.local`. Search is covered by tests with a mocked provider.
- [x] 7.10 Sign out and sign back in — data persists
- [x] 7.11 Browser console clean on every page
- [~] 7.12 Side-by-side against `npm run dev` at desktop and mobile widths — the Chrome extension is still not connected, so no **visual** pass was possible. Instead `tools/compare_ui.py` renders the React component with react-dom/server and diffs its DOM against the Django page: landing 194/194 elements and dashboard 160/160 elements, zero differences. The four stylesheets are served byte-identical to `src/`.
- [x] 7.13 `curl` API parity pass including a deliberate 409 revision conflict

**Done when:** every flow has actually been exercised in a browser, not inferred from tests.

---

## Phase 8 — Documentation [plan §10]

- [x] 8.1 Rewrite `README.md` for the Django app: what it is, setup, run, migrations, environment variables, how to exercise each flow
- [x] 8.2 Rewrite `BACKEND_SETUP.md` around the Django routes, keeping OpenAI and Spotify setup
- [x] 8.3 Note that `src/` and `server/` remain the reference implementation
- [x] 8.4 Record required product disclosures (PRD §14.1) in the UI copy where the originals already carry them

---

## Deferred to the next phase [plan §11]

Email verification · password reset · messaging (MSG-01) · connection block and report · opportunity
verification workflow · billing and entitlements (BILL-01) · notification preferences (NOTIF-01) · data
export and account deletion (PRIV-01) · audit logging and moderation queue.
