# Navigating SoundBridge

A walkthrough of every screen in the workspace, in the order you meet them. Routes are
written as you would type them after `http://127.0.0.1:8000`. To get the app running, see
[LOCAL_DEVELOPMENT.md](../LOCAL_DEVELOPMENT.md).

---

## 1. Getting in

### `/` — Landing

The public entry page. It links to sign-up and sign-in. Signed in and past onboarding, you
land on `/portal` instead.

### `/signup` — Create an account

You accept the versioned terms and privacy documents here (readable at `/legal/terms` and
`/legal/privacy`). Sign-in lives on the same screen.

Forgot a password? `/password-reset` sends a recovery link through the configured mail
backend.

### `/verify-email` — The first gate

**Until your email is verified, the workspace is closed to you.** You can reach only
sign-out, onboarding, `/settings`, public profiles and the legal pages; everything else
redirects back here, and the JSON API answers `403 email_unverified`.

Email verification is switched off, so signing up takes you straight into the workspace and no message is sent. With `SOUNDBRIDGE_REQUIRE_EMAIL_VERIFICATION=true`, the verification message sits locally in a durable outbox rather than being sent. Flush it
and read the link from your terminal:

```powershell
python manage.py deliver_email
```

## 2. Onboarding — the second gate

Onboarding is persistent: `/portal` bounces you to the next incomplete step until every
required one is done. The steps are ordered, and **which steps you get depends on the goals
you pick**:

| Order | Route | What it asks | Required |
| --- | --- | --- | --- |
| 1 | `/onboarding` | Your role | Always |
| 2 | `/goals` | What you want from the platform | Always — pick at least one |
| 3 | `/profile-setup` | Name, username, country/region, biography | Always — all four |
| 4 | `/genres` | Genres and skills | Always — at least one genre or skill |
| 5 | `/royalty-setup` | Royalty starting point | Only if you chose "Understand royalties" |
| 6 | `/release-setup` | First release plan | Only if you chose "Plan a release" |

If you want to see the royalty and release setup steps, choose those two goals at step 2.
Each step refuses to advance until its fields are filled — the error tells you exactly
which. Once the last required step is done you are dropped at `/portal` and onboarding
never reappears.

## 3. The workspace shell

Every signed-in page shares one frame:

- **Left sidebar** — eleven links in two captioned groups: *Your network* (Overview,
  Discover, Collaborations, Connections, Notifications, Opportunities) and *Your creative
  toolkit* (AI Team, Royalties, Release Planner, Analytics, Music Search). On a narrow
  screen it collapses behind the hamburger button.
- **Top bar** — the current page name, and a **"Find your next move"** search button. That
  opens a jump-to dialog covering the sidebar pages plus four that are not in the sidebar:
  Royalty Calculator, Statement Upload, Membership, and Settings & profile. This is the
  fastest way to reach anything.

Screens not in the sidebar or the search dialog are reached from within a page: a
collaboration workspace from `/collaborations`, a release from `/release-planner`, an import
review from `/royalty-upload`, and so on.

## 4. Your network

### `/portal` — Overview

The home screen. Four stat tiles, each a link: profile completeness (→ `/settings`), saved
creators (→ `/collaborations`), release plans (→ `/release-planner`), AI conversations
(→ `/assistants`). Below them your most recent release plan with its task readiness
percentage and next three unfinished tasks, plus three suggested next moves.

### `/discover` — Find people

Lists published profiles of verified, active accounts. Filter by search text and role using
the controls (they are URL parameters, so a filtered view is bookmarkable). Sample seeded
creators appear under their own legacy cards at `/creators/<id>` and can be saved for later;
they are demonstration records, not real accounts.

Open anyone's public page at `/people/<username>`.

### `/connections` — Requests, blocks and reports

Send a request from someone's profile; accept, decline or withdraw from here. Blocking is
available per person, and `/reports/new` files a report for moderator review. Connection
requests are rate-limited per day by your plan (`connection_requests_daily`).

### `/messages/<connection id>` — Direct threads

A one-to-one thread, reachable from an accepted connection. You cannot message someone you
are not connected to.

### `/collaborations` — Projects

Create a project with a brief, then open it to get its own workspace, which holds:

- **Brief** — title, description, state, start and end dates. Owner-only. Marking it
  *completed* closes the project.
- **Participants** — invite by username (published, verified accounts only). Invitations
  expire after 7 days; the invited person accepts at `/collaborations/invitations`. Owners
  can remove access.
- **Milestones** — title, due date, optional assignee. The owner or the assignee can move a
  milestone's state and leave notes.
- **Messages** — a group thread, paginated 30 at a time, rate-limited to 30 sends. Any
  message can be reported.
- **Files** — PDF, text, image or audio, up to 5 MB each, 100 per project. **Every upload is
  quarantined until scanned**, so without a malware scanner configured the download link
  never appears. This is the expected behaviour on a plain local setup.
- **Split proposals** — propose percentage shares across the accepted parties; each party
  responds. Rounds are versioned, so the history of who proposed what is kept.
- **Activity** — the last 50 audit events for the project.
- **Mute** — silences notifications for this project only.

### `/notifications`

Everything that happened to you: invitations, connection requests, milestone changes.
Mark items read here, and set your per-category preferences.

### `/opportunities`

Operator-reviewed listings only — unverified and sample rows never appear, and anything past
its deadline drops out. Filter by type, region, or saved-only. Per listing you can save it,
keep a private application draft (at least 20 characters), mark it *applied* or *withdrawn*
to track your own status, or report it.

**Applications are completed on the external site.** Saving a draft or opening the link does
not submit anything on your behalf.

## 5. Your creative toolkit

### `/assistants` — AI Team

Thirteen specialists across three categories:

| Category | Specialists |
| --- | --- |
| Business | Artist Manager, Royalty Assistant, Legal Information Assistant, Release Planner, Strategy Assistant, Collaboration Matcher, Profile Manager |
| Creative | A&R Advisor, Production Coach, Songwriting Partner |
| Growth | Content Strategist, Music Publicist, Live & Booking Coach |

Three guided workflows chain them: *Take a release from idea to launch*, *Develop a song*,
*Understand my music business*.

How a session goes: pick a specialist (or a workflow), use a suggested starter or type your
own, and converse. From a reply you can **save it to your work library** (downloadable at
`/assistants/work/<id>.txt`), **hand off** the brief and latest reply to another specialist,
or leave feedback on it. Your **artist brief** is shared context every specialist reads;
edit it once and they all see it.

Control what they may read at `/assistants/context` — context sharing is explicit, not
assumed. Delete a whole conversation from the same screen.

Two limits to expect: a per-account allowance of 30 AI requests per UTC day
(`SOUNDBRIDGE_AI_DAILY_LIMIT`), and your plan's `ai_daily` capability. Without
`OPENAI_API_KEY` set, the screen loads but requests fail — the status indicator only reports
that a key is present, not that it works.

### `/royalties` — Overview

Currency-aware earnings totals from your imported statements, plus your saved calculations.
The entry point to the four screens below.

### `/royalty-calculator`

Enter your assumptions and get low / mid / high scenarios computed with decimal arithmetic.
Save a scenario (`/royalties/calculations/<id>` to revisit or edit). Assumptions are stored
alongside the numbers, so a saved scenario always explains itself. This is educational
modelling, not a forecast.

### `/royalty-upload` — Statement import

The most multi-step flow in the app:

1. **Upload** a CSV. `/royalty-upload/sample` downloads a sample file showing the expected
   shape.
2. The file is **quarantined** and queued for scanning. Run `python manage.py scan_files`
   then `python manage.py process_statements` locally, or let Celery do it in the Docker
   stack. **Without a configured scanner the batch stays quarantined and never reaches
   review** — expected on a plain Windows setup.
3. **Review** at `/royalties/imports/<batch id>`: map each of your CSV's columns to a field,
   name the source, set the period. A preview of up to 50 rows shows what the mapping
   produces before you commit.
4. **Confirm** — income totals update. You can re-map and confirm again if you got it wrong.
5. **Export** a statement back to CSV at `/royalties/statements/<id>/export`, or delete a
   batch outright.

### `/royalties/income`, `/royalties/summary`, `/royalties/education`

Manual income entry for money that never came through a statement; grouped, currency-aware
reporting by source and period; and plain-language explanations of how music rights and
royalties work.

### `/release-planner`

Create release plans, then open one at `/releases/<id>` to edit its stage, campaign notes and
metadata readiness, and to manage dated tasks. Ticking tasks drives the readiness percentage
shown on `/portal` and `/analytics`.

### `/analytics`

Four counts — saved creators, completed collaborations, completed release tasks, imported
statements — plus per-release task completion bars and earnings totals by currency. It
reports on your own data; there is no streaming or platform analytics connection.

### `/music-search`

Public Spotify catalog search. Choose a market and search. Needs `SPOTIFY_CLIENT_ID` and
`SPOTIFY_CLIENT_SECRET`.

This is catalog search only. It is **not** a Spotify account connection — no playlists,
listening history or Spotify for Artists data, because that needs a user-consent flow that
is not implemented.

## 6. Account, privacy and plan

### `/settings` — Settings & profile

Your account basics, and `/settings/export` downloads your workspace as JSON.

### `/settings/professional` — Public profile

The profile other people actually see. Publish it, control field-by-field visibility, and
add sourced credits and portfolio links. Profile completeness here is the percentage shown
on `/portal`. Your public page is `/people/<username>`.

### `/settings/privacy`

Password-confirmed actions: revoke AI context permissions, request a **data export** (served
as JSON, then available under your artifacts), or request **account deletion**.

Deletion and export requests are carried out by `python manage.py process_privacy_requests`,
and **only once a retention policy has been approved in the admin**. With no approved policy
nothing is processed — deliberate, not a bug.

### `/membership`

Your current plan and its capability limits: `ai_daily`, `release_plans`,
`active_collaborations`, `saved_calculations`, `statements`, `connection_requests_daily`. A
`402` anywhere in the app means you hit one of these.

Checkout refuses to act until `SOUNDBRIDGE_BILLING_PROVIDER` names an implemented adapter —
it will not simulate a charge. Downgrading never deletes anything; you keep your data and
simply cannot add more.

### `/admin/`

Django admin, for the account you made with `createsuperuser`. Staff status alone grants no
permissions — assign explicit group permissions. Operators use it to verify opportunity
listings, handle reports, and approve the retention policy and plans. Keep moderation,
commercial approval and account administration in separate roles.

## 7. Things that will look broken but aren't

| What you see | Why |
| --- | --- |
| Redirected to `/verify-email` from everywhere | Email not verified. Run `deliver_email`. |
| Redirected back into onboarding from `/portal` | A required step is incomplete. |
| Uploaded file or CSV stuck, no download link | No malware scanner. Quarantine is fail-closed by design. |
| Statement never reaches review | Run `scan_files` and `process_statements`, or use the Docker stack. |
| Logged out when moving between pages | You switched between `localhost` and `127.0.0.1`; they hold separate cookies. |
| No verification or notification email | Verification is off, so none is sent. Other mail is queued by the console backend — run `deliver_email` and read your terminal. |
| `402` on an action | A plan limit. See `/membership`. |
| Checkout does nothing | No billing adapter configured. It refuses rather than fake a charge. |
| Privacy export or deletion never completes | No approved retention policy in the admin. |
| Royalty setup and release setup never appeared | You didn't choose those two goals during onboarding. |

## Related documents

- [LOCAL_DEVELOPMENT.md](../LOCAL_DEVELOPMENT.md) — running the app on your machine
- [BACKEND_SETUP.md](../BACKEND_SETUP.md) — API contract, OpenAI and Spotify setup
- [MVP_OPERATIONS.md](MVP_OPERATIONS.md) — workers, private storage, privacy processing
- [openapi.json](openapi.json) — the `/api/v1/` resource contract
