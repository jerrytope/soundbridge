# SoundBridge PRD gap findings

Reviewed: 18 September 2026  
Baseline: `SoundBridge_Product_Requirements_Document.pdf` v1.0 (5 September 2026)  
Scope: current Django application in this repository

## Conclusion

The Django codebase is a working foundation and a port of much of the earlier React/Node prototype. It does **not** satisfy every P0 requirement or the MVP release acceptance criteria in the PRD. The checked boxes in `tasks.md` describe the narrower Django parity plan, whose section 1 explicitly defers several PRD features. Do not treat that checklist as PRD completion.

This is a source review, not a launch certification. Live AI and Spotify calls, browser accessibility, security, load, backup restore, and production deployment were not verified during this review. The project's own `README.md` also says live provider calls and public deployment have not been verified.

## What is already present

- Email/password sign-up and sign-in, server sessions, onboarding, profile editing, and a workspace export (`accounts/views.py`, `config/settings.py`).
- A database-backed sample creator directory, filtering, saved creators, collaboration briefs, sample opportunities, and application drafts (`network/`).
- Release projects with persistent tasks and artwork (`releases/`).
- Decimal-based master-streaming scenarios, saved calculations, CSV imports, duplicate detection, per-currency totals, and statement deletion (`royalties/`).
- Nine specialist interfaces, stored conversations, a server-side model gateway, and a daily AI request allowance (`aiteam/`).
- Private image ownership checks and a JSON API for the earlier workspace contract (`accounts/images.py`, `apiv1/`).

These are useful pieces, but several models contain future states or fields without the user workflows required to operate them.

## P0 gaps that block PRD MVP acceptance

| PRD area | Finding in current code | Required outcome |
| --- | --- | --- |
| AUTH-01; pp. 5, 7, 14, 16 | `accounts/views.py` supports sign-up, sign-in, and sign-out. There is no email verification or password-reset flow. The `User` model has no verification or consent version fields. | Verification and recovery work end to end; required terms and privacy consent are recorded with versions and timestamps. |
| PRO-01; pp. 5, 7–8 | `CreatorProfile` has name, role, city, bio, portfolio, genres, goals, and two visibility flags. It lacks a unique username, country/region, skills, availability, credits, richer links/media, and a public view backed by real user profiles. | Required profile fields, public preview, and visibility controls apply to real creator accounts. |
| DISC-01, CONN-01; pp. 5, 7–8 | `Creator` records are seeded samples. `network/views.py:save_creator` toggles a saved sample and `Connection` defaults to `accepted`; there is no recipient who can accept or decline. Search reads all rows into memory and has no pagination or skills filter. | Real profile discovery with paginated filters; permission-checked request, accept, decline, cancel, block, and report actions. |
| COLL-01, MSG-01; pp. 5, 7–8 | The collaboration page creates a title/brief and toggles completion. Participant, milestone, and split models exist, but their full workflows are absent. There are no user-to-user message threads, files, mute/report actions, or activity history. | A permission-checked collaboration workspace with participant and milestone workflows, split proposals, and accepted-context messaging. |
| OPP-01; pp. 5, 7 | Opportunities are seeded samples. The page saves an application **draft** only; it does not submit an application. There is no operator verification/reporting workflow, saved items, or complete source/eligibility/deadline presentation. | Real curated records with documented verification state, complete listing details, reporting, and working application links or submission behavior. |
| REL-01; pp. 5, 7, 16 | Projects, dates, and checklists persist. No reminder delivery, metadata readiness workflow, or campaign plan is visible in `releases/views.py` or `templates/releases.html`. | Complete project needs, reminders, metadata readiness, and campaign planning; task progress remains persistent. |
| ROY-01; pp. 7, 10, 16 | `royalties/services.py:estimate` and `templates/calculator.html` return one amount from a user-entered rate. The form does not collect territory mix, reporting period, distributor/label deductions, or taxes. `Calculation` has rate-source/version fields, but the UI does not capture an effective date or source details. | Low, midpoint, and high scenarios with versioned rate provenance, territory/period assumptions, gross/deductions/share breakdown, and save/compare/export/delete actions. |
| ROY-02; pp. 7, 10, 16 | CSV is parsed immediately and original bytes are stored in `Statement.original_csv`. There is no malware scan, isolated processing, mapping review, confidence indication, correction workflow, or documented retention/encryption-at-rest control. `RoyaltyTransaction` has canonical fields, but the importer fills many only if columns happen to exist. | Secure import, explicit mapping confirmation/correction, normalized review, traceability, deletion/reversal, and the required operational controls. |
| ROY-03; pp. 8, 10 | Category constants exist in `royalties/models.py`, but a complete rights education and next-action journey is not established by those constants. | Plain-language education for master, mechanical, performance, neighboring, sync, and contractual income, with relevant next actions. |
| AI-01; pp. 8–9, 16 | The model gateway, history, and daily cap exist. There is no real Free/Pro entitlement source, user feedback/reporting flow, conversation deletion/retention controls, moderation queue, or demonstrated launch evaluation. `aiteam/agents.json` contains role guidance, but PRD governance is broader. | Server-enforced plan limits, safety/reporting controls, context consent, feedback, retention/deletion, evaluations, and documented failure states. |
| BILL-01; pp. 8, 11, 16 | `templates/membership.html` labels Pro and checkout as planned. There is no subscription model, payment flow, verified webhook, invoices, cancellation, or entitlement reconciliation. | Choose provider and commercial terms; implement checkout, verified events, plan state, recovery/cancellation, and entitlements. |
| PRIV-01; pp. 8, 14 | `accounts/views.py:export_workspace` provides a JSON workspace export. There is no account deletion request/workflow, complete consent management, retention policy, or deletion audit. The export may need review against the PRD's full data portability expectation. | Authenticated export, consent correction/revocation, tracked deletion, and retention behavior. |

## Cross-cutting gaps and release gates

- **Notifications (P1; PRD pp. 8, 12):** No notification preference or delivery system for messages, connections, deadlines, or release reminders.
- **Trust and safety (PRD p. 14):** No complete block/report workflow, moderation queue, impersonation handling, or opportunity fraud review.
- **Production API (PRD pp. 12–13):** The API is a narrow `/api/*` compatibility layer, not the full versioned resource API. A reviewed OpenAPI contract, pagination across resource lists, and general idempotency keys are not evident.
- **Security and operations (PRD pp. 14–16):** TLS settings exist for a configured public origin, and image type/size checks exist. Malware scanning, encryption-at-rest design, structured audit trails, backup restore tests, incident procedures, metrics/alerts, and dependency scanning are not demonstrated in the repository.
- **Frontend and accessibility (PRD pp. 12, 15–16):** The production direction in the PRD is React with TypeScript. This implementation serves Django templates, by a deliberate plan decision. No WCAG 2.2 AA audit, supported browser matrix, manual keyboard/screen-reader pass, or complete loading/error-state review is recorded.
- **Real integrations:** Spotify only searches a public catalog when credentials are configured; it does not connect an account or provide royalty/artist analytics. The README says live OpenAI and Spotify calls were not made.

## Suggested implementation order

1. **Set launch decisions:** country/legal entity, supported currencies, email and payment providers, Free/Pro limits and prices, initial royalty formats, retention periods, moderation owner, and legal copy. These decisions are explicitly open in PRD section 18.3. Do not invent commercial or legal terms in code.
2. **Identity, consent, and profile foundation:** verification, password reset, consent records, real public creator profiles, account deletion and full export.
3. **Real network and safety:** paginated discovery, connection state machine, blocks/reports, collaboration permissions, messaging, and moderation tools.
4. **Career workflows:** curated opportunities and verification, release metadata/campaign plans, reminders and notification preferences.
5. **Royalty completion:** range calculator with governed assumptions; secure asynchronous CSV pipeline with mapping review and correction; education and exports.
6. **AI and Pro:** context permission, feedback/reporting and evaluations, billing-backed entitlements, verified webhooks, cancellation and reconciliation.
7. **Launch gates:** typed API contract, end-to-end and accessibility tests, security review, observability, load tests, backup restore, migration and support procedures, legal/commercial approval.

## Verification note

This document is based on reading the PRD and repository source. No Django test suite was run for this review: the available Python 3.12 environment did not have the project's dependencies installed. The five existing modified migration files were left untouched. Recheck each finding after implementation and record passing evidence against PRD section 17.3 before marking the MVP complete.
