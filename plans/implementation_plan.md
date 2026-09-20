> MVP follow-up: [completion plan](mvp_completion_plan.md) and [implementation status](mvp_implementation_status.md). The earlier parity checklist is not PRD completion. See [Django operations](../docs/MVP_OPERATIONS.md) for current setup.

# SoundBridge — Django Implementation Plan

Version 1.0 · 17 September 2026
Scope: server-rendered Django rebuild of the SoundBridge backend and screens, with the existing UI unchanged.
Reference: `plans/SoundBridge_Product_Requirements_Document.pdf` (PRD v1.0, 5 September 2026).

---

## 1. Context

The repository as checked out contains only config, docs and twelve 550-byte HTML shells that point at a
missing `/src/main.jsx`. `npm run dev` fails immediately with
`Could not resolve "./server/backend.js"`. The application source was never committed; it was supplied
separately as `SOUNDBRIDGE WEBAPP.zip` (32 MB) in the project root, alongside the PRD in `plans/`.

The zip contains the complete existing application:

| Area | Contents |
| --- | --- |
| `src/` | The React SPA that **is** the current UI — `main.jsx` (37 KB, 16 routes and a `Shell` with sidebar nav, mobile drawer and page search), `Landing.jsx`, `ai/AiStudio.jsx`, `components/`, `backend/useWorkspace.js`, `domain.js`, `creators.js` |
| CSS | `src/design.css` (31 KB), `src/landing.css` (20 KB), `src/app.css` (8.7 KB), `src/ai/studio.css` (12 KB) — the design to preserve |
| `server/` | The Node backend being replaced — `backend.js` (SQLite schema, auth, sessions, workspace, images), `ai.js` (nine OpenAI specialists), `spotify.js`, `start.js`, `request-policy.js`, plus tests |
| `legacy/` | The original 12-page static HTML/CSS/JS prototype, still reachable in the React app at `/<page>.html` |
| Data/config | `.env.local` with OpenAI and Spotify credentials, `.env.example`, `.data/soundbridge.sqlite`, a `dist/` build, `.vercel/` |

### Decisions taken with the product owner

1. **Build the backend with Django**, replacing `server/`.
2. **Do not change the UI.** Server-rendered Django templates reproduce the React screens and reuse the
   existing stylesheets verbatim. Nothing under `src/` is edited.
3. **PRD §13.1 entities in the Django ORM** (decimal-safe money), while keeping the **same API shape** —
   the existing `/api/*` workspace JSON contract keeps working on top of those models.
4. **Feature parity first.** Everything the current app does, verified running. PRD gaps (email
   verification, password reset, messaging, billing and entitlements, notifications, data export and
   account deletion) are a later phase.

### Intended outcome

One Django application serving the identical interface, backed by real relational data instead of a
single JSON blob per user, with the React application left intact on disk as the visual reference.

---

## 2. What the PRD requires of this build

The PRD is the product baseline; the constraints that bind this phase are:

- **§12.1** React/TypeScript is named as the production frontend direction, but **no production
  financial, authentication or entitlement state in browser storage** is the binding rule. Server-rendered
  Django satisfies it; the current app's `localStorage` local-mode workspace is retained only as the
  unauthenticated fallback it already is.
- **§12.3** Versioned HTTPS APIs, consistent errors, idempotent mutation retries, authorization at every
  resource, **decimal-safe money and no floating-point storage for financial amounts**.
- **§10.2** The royalty estimator must record rate source, effective date, version, territory assumptions
  and formula, and must never present a single universal fixed per-stream rate as guaranteed income.
- **§10.3** Statement ingestion is CSV-first, mapped to a canonical schema, with duplicate detection and
  anomalies phrased as possible issues requiring confirmation.
- **§9.1** The AI gateway stays server-side: no provider keys in the browser, entitlement checks, rate
  limits, versioned prompts, uploaded content treated as untrusted data, no training on private content.
- **§14** Object-level permission checks, upload allowlists and size limits, encryption in transit,
  restricted access to financial data, documented disclosures.

The estimator, statement ingestion and AI gateway in the current app already follow most of this; the
Django port must not regress it.

---

## 3. Recover the source

Extract `SOUNDBRIDGE WEBAPP.zip` into the repository root, skipping `node_modules/`, `dist/`, `.vercel/`,
`__MACOSX/` and `.DS_Store`. This restores `src/`, `server/`, `legacy/`, `api/`, `.env.example` and
`.env.local`. The `.gitignore` inside the zip already excludes `.env*`, `.data/`, `dist/` and
`node_modules/`.

`src/` and `server/` stay in place and unmodified so `npm run dev -- --host 127.0.0.1` remains runnable
for side-by-side UI comparison during verification.

---

## 4. Project layout

Django 6.0.3, Pillow and requests are already installed (Python 3.12.3). Add `requirements.txt` pinning
them. Database: SQLite at `.data/django.sqlite3`, kept separate from the Node file.

```
manage.py
requirements.txt
config/            settings.py, urls.py, wsgi.py, asgi.py
accounts/          custom email user, session policy, profile, onboarding, stored images
network/           creators catalogue, connections, collaborations, opportunities, drafts
releases/          release projects and tasks
royalties/         calculations, statements, transactions, income sources, education copy
aiteam/            agent registry, conversations, deliverables, gateway, daily usage
integrations/      Spotify catalog search, configuration status
apiv1/             workspace-JSON compatibility layer (serializers + /api/* views)
templates/         base.html, shell.html, one template per screen, partials/
static/css/        design.css, app.css, landing.css, studio.css   (copied verbatim)
static/js/         shell.js, calculator.js, upload.js, ai_studio.js, image_upload.js
```

### Settings that mirror current behaviour

- Session cookie `soundbridge_session`, `HttpOnly`, `SameSite=Strict`, 7-day lifetime, `Secure` when a
  public origin is configured.
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`,
  `SOUNDBRIDGE_PUBLIC_ORIGIN`, `SOUNDBRIDGE_ALLOW_SIGNUP` read from `.env.local` using the same names as
  `.env.example`, so the user configures nothing new.
- `MinimumLengthValidator(12)` to match the existing 12–128 character password rule.
- `server/request-policy.js` (loopback-only in development, configured public origin in production)
  becomes Django middleware.

---

## 5. Data model (PRD §13.1)

The `emptyState` shape in `src/domain.js` becomes real tables:

| Workspace key | Django model | Notes |
| --- | --- | --- |
| `profile` | `accounts.CreatorProfile` | name, photo, role, city, bio, portfolio, genres, goals; field-level visibility flags (§8.2) |
| `connections` | `network.Connection` | states pending / accepted / declined / cancelled / blocked (§8.3) |
| `projects` | `network.Collaboration`, `Participant`, `Milestone`, `SplitProposal` | brief states draft / open / matched / active / completed / cancelled (§8.3) |
| `applications` | `network.OpportunityApplication`, `network.Opportunity` | source, region, eligibility, deadline, cost, verification state |
| `releases` | `releases.ReleaseProject`, `ReleaseTask` | type Single/EP/Album, stage, target date, artwork, task completion |
| `calculations` | `royalties.Calculation` | inputs, `rate_version`, rate source, effective date, scenarios, currency |
| `statements` | `royalties.Statement`, `royalties.RoyaltyTransaction` | canonical schema: source, period, work, recording, territory, platform, usage type, units, gross, deductions, net, currency, payee |
| `royaltySources` | `royalties.IncomeSource` | selections captured during royalty setup |
| `aiConversations`, `aiDeliverables` | `aiteam.Conversation`, `Message`, `Deliverable` | agent id, prompt and model version, safety state, usage |
| `drafts` | `network.OutreachDraft` | |

- All money is `DecimalField(max_digits=18, decimal_places=4)` with an explicit currency column. No
  floats anywhere in the financial path (PRD §12.3).
- `accounts.User` carries `workspace_revision` for the optimistic-locking contract.
- Images move from the Node `images` BLOB table to `accounts.StoredImage`: private bytes, owner-only
  access, 20 MB per-account cap, served at the same `/api/images/<uuid>` URLs.
- Sample creator data in `src/creators.js` is loaded by a `seed_creators` management command into
  `network.Creator`, so Discover renders identical cards from the database.

---

## 6. Preserve the API contract

`apiv1` reproduces the routes in `server/backend.js` compatibly, reading and writing the same JSON
through serializers over the new models:

| Route | Method | Purpose |
| --- | --- | --- |
| `/api/health` | GET | liveness and storage kind |
| `/api/auth/signup` | POST | create account and session |
| `/api/auth/login` | POST | verify password and create session |
| `/api/auth/session` | GET | restore session and workspace |
| `/api/auth/logout` | POST | revoke current session |
| `/api/workspace` | GET, PUT | read and save workspace with revision check |
| `/api/images` | POST | decode, resize and store a private image |
| `/api/images/<id>` | GET, DELETE | owner-only read; delete only when unused |
| `/api/integrations/status` | GET | whether OpenAI and Spotify are configured |
| `/api/music/search` | GET | Spotify catalog search |
| `/api/ai/status`, `/api/ai/chat` | GET, POST | specialist availability and chat |

Behaviour carried over exactly, because the front end and the existing tests depend on it:

- Revision conflict → **409** with the same message ("This workspace or its images changed in another
  tab. Export your changes before reloading.").
- `X-Soundbridge-Account` header mismatch on writes → **409**.
- Rate limits: auth 10/min, music search 20/min, and a 30-request-per-account-per-UTC-day AI allowance.
- `validateWorkspace` field limits and error strings (bio 1000, other text 300, arrays ≤ 1000 entries,
  genres/goals ≤ 20, release type in Single/EP/Album, `YYYY-MM-DD` dates, currencies USD/NGN/EUR/GBP).
- Image ownership enforcement: a workspace may only reference images owned by that account.
- Registration closed when a public origin is configured unless explicitly allowed.

**Existing accounts:** a custom password hasher that accepts the Node `salt:scrypt-hex` format lets the
accounts already in `.data/soundbridge.sqlite` sign in unchanged, and an `import_node_data` management
command copies those users, workspaces and images into the Django models.

---

## 7. Templates that keep the UI identical

Copy the four stylesheets into `static/css/` **unchanged**, then port the JSX markup to templates with the
same elements, class names and copy. The shared JSX helpers become partials:

| JSX | Template |
| --- | --- |
| `Heading` | `partials/heading.html` |
| `Field` | `partials/field.html` |
| `Empty` | `partials/empty.html` |
| `CreatorCard` | `partials/creator_card.html` |
| `Shell` | `templates/shell.html` |

`shell.html` reproduces the nine-item sidebar (`⌂` Overview, `⌕` Discover, `♬` Collaborations, `◇`
Opportunities, `✦` AI Team, `₦` Royalties, `✓` Release Planner, `◉` Analytics, `♬` Music Search), the
"YOUR NETWORK" / "YOUR CREATIVE BUSINESS" nav captions, the mobile drawer, the page-search dialog and the
sync-status line.

### URL parity with `src/main.jsx`

| URL | Template |
| --- | --- |
| `/` | `landing.html` (from `Landing.jsx` + `landing.css`) |
| `/signup` | `signup.html` (sign up and sign in) |
| `/onboarding`, `/goals`, `/genres` | `setup.html` choice grid — role, up to three goals, genres |
| `/profile-setup`, `/settings` | `profile.html` with photo upload |
| `/royalty-setup`, `/release-setup` | `royalty_setup.html`, `releases.html` |
| `/portal` | `dashboard.html` |
| `/discover`, `/creators/<id>` | `discover.html` (filters as GET params), `creator.html` |
| `/collaborations`, `/opportunities` | `collaborations.html`, `opportunities.html` |
| `/royalties`, `/royalty-calculator`, `/royalty-upload` | `royalties.html`, `calculator.html`, `upload.html` |
| `/release-planner`, `/analytics`, `/membership` | `releases.html`, `analytics.html`, `membership.html` |
| `/assistants` | `assistants.html` + `studio.css` |
| `/music-search` | `music_search.html` |
| `/<page>.html` (12 pages) | the `legacy/` files served as static, as the React `Legacy` route does |

### Client-side logic that moves or shrinks

- **Discover filters** → server-side GET filtering; `.filters`, `.cards`, `.pill`, `.avatar` markup unchanged.
- **Calculator** → form POST. `estimate(streams, rate, share)` from `src/domain.js` is ported to
  `royalties/services.py` using `Decimal`, and records rate source and version per PRD §10.2 behind the
  same display the UI shows today.
- **CSV upload** → Python `csv` replaces `Papa.parse`. `normalizeStatement`'s rules (required
  `track,platform,amount,currency`; USD/NGN/EUR/GBP; identical per-row error text) and duplicate
  detection move to `royalties/services.py`.
- **Image upload** → Pillow replaces `sharp`: EXIF rotate, fit inside 640×640 without enlargement,
  flatten onto `#1a1b1e`, JPEG quality 80, 5 MB input limit, same JPEG output the UI expects.
- **AI studio** → chat interface unchanged; `static/js/ai_studio.js` posts to `/api/ai/chat`. The nine
  agents from `src/ai/agents.js` (Artist Manager, A&R Advisor, Production Coach, Songwriting Partner,
  Music Marketing Strategist, Music Publicist, Royalty Analyst, Music Rights Guide, Live & Booking Coach)
  and the `server/ai.js` instructions, JSON-schema response (`answer` plus up to five `actions`),
  `store: false`, request timeout, concurrency cap and untrusted-context framing are ported verbatim into
  `aiteam/gateway.py`.
- **Shell behaviour** (drawer, search dialog, focus trap, body-scroll lock, desktop breakpoint at 761px)
  → about 60 lines in `static/js/shell.js` with the same DOM and ARIA attributes.

---

## 8. Tests

Port the Node coverage to Django tests:

- workspace validation, field limits and revision conflicts;
- session creation, restoration and revocation;
- cross-account image isolation and image processing output;
- AI request validation, daily limit enforcement and provider error handling (mocked);
- Spotify search with mocked responses, including rate-limit and authorization failures;
- closed registration and origin enforcement;
- view tests asserting every URL returns 200 for a signed-in user and redirects when anonymous.

---

## 9. Verification

Nothing is reported as done until it has been run:

1. `python manage.py migrate && python manage.py seed_creators && python manage.py runserver 127.0.0.1:8000`
2. `python manage.py test` — all ported tests green.
3. Browser walkthrough of the real flows: sign up → role → three goals → genres → profile with photo →
   dashboard → Discover with filters → save a creator → create a release plan and tick tasks → royalty
   calculator → upload a CSV statement → Analytics → Music Search → AI assistant → sign out and sign back
   in to confirm persistence. Console checked for errors on every page.
4. Side-by-side UI check: run the React app (`npm run dev -- --host 127.0.0.1`) and compare every screen
   against the Django one at desktop and mobile widths. The pages must look the same.
5. `curl` the API surface for contract parity, including a deliberate 409 revision conflict.
6. AI and Spotify exercised with the credentials already in `.env.local`; a failure is reported as the
   real provider error, never stubbed or fabricated.

---

## 10. Documentation

- Rewrite `README.md` for the Django app: what it is, setup, `runserver`, migrations, environment
  variables, and how to exercise each flow.
- Rewrite `BACKEND_SETUP.md` around the Django routes, keeping the OpenAI and Spotify configuration
  instructions.
- Note in both that `src/` and `server/` remain as the reference implementation.
- `Dockerfile` and `vercel.json` are left alone until deployment is revisited.

---

## 11. Out of scope for this phase

Deferred to the next phase, per the parity-first decision: email verification, password reset, messaging
(MSG-01), connection block and report flows, opportunity verification workflow, billing and entitlements
(BILL-01), notification preferences (NOTIF-01), data export and account deletion (PRIV-01), audit logging
and the moderation queue. Also out of scope, per PRD §5.3: guaranteeing royalty amounts, legal or
financial advice, platform scraping, and acting as a distributor, publisher, label, bank or collecting
society.
