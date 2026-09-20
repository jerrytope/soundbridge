# MVP implementation evidence and remaining work

Updated 19 September 2026 (second pass). Companion to `mvp_completion_plan.md`; supersedes any inference that the earlier Django parity checklist meant PRD completion.

## Implemented (verification in progress)

| Requirement | Implemented behavior | Evidence |
| --- | --- | --- |
| AUTH-01 | Email verification with single-use expiring tokens, resend limits, password reset, session invalidation, shared authentication throttling, CSRF | `accounts.test_mvp`, legacy auth tests |
| ONB-01 | Persistent completion and multi-goal routing | `GoalRoutingTests` |
| PRO-01 | Username, country, skills, availability, credits/links, publication and visibility, public photo authorization | `NetworkTests`, browser smoke |
| DISC-01 | Real published-profile discovery, filtering, pagination, matching explanation | `NetworkTests`, discovery tests |
| CONN-01 | Real request state transitions, idempotence, actor checks, blocks, reports | `NetworkTests`, resource API tests |
| COLL-01 | Real invitations, expiry, participant access, brief editing, milestones, activity, split versions/responses, quarantined files | `CollaborationWorkflowTests` |
| MSG-01 | Accepted-connection messaging, deduplication, polling, mute/report; collaboration messages | `NetworkTests`; group-specific mute/report and delivery tracking remain incomplete |
| OPP-01 | Curated verified directory, evidence, filtering, bookmarks, external applications, tracking and reporting | Admin validation and template implementation; broader operator tests pending |
| REL-01 | Editable stage/needs, metadata readiness, campaign plans, task dates, reminders | Operations tests and browser smoke |
| ROY-01 | Decimal low/mid/high ranges, versioned input provenance, deductions/tax/share, compare/export/delete | Calculator tests |
| ROY-02 | Quarantine, fail-closed scanning, isolated CSV parsing, mapping review/correction, atomic import, duplicates, export/delete | SecureImportTests; actual scanner and retention/object storage evidence outstanding |
| ROY-03 | Category explanations and next actions | Content written; expert/legal review pending |
| AI-01 | PRD specialist coverage, context scopes and revocation, atomic daily allowance, feedback/report queue, deletion, provider moderation on both directions (fail-closed on a public origin), per-call latency/token metrics, evaluation harness with starter cases | `GovernanceTests`, `aiteam.test_safety` (14 cases). Live evaluation runs against the real provider, and expert review of the education content, remain outstanding |
| BILL-01 | Approved-plan and subscription models; capability limits enforced across releases, collaborations, scenarios, statements, connections and AI; checkout, signature-verified idempotent webhooks, reconciliation and cancellation implemented against a provider adapter contract | `billing.tests` (27 cases, fake adapter). No provider is selected, so `SOUNDBRIDGE_BILLING_PROVIDER` is unset and checkout/webhook refuse to act; the adapter subclass and live verification remain |
| NOTIF-01 | In-app/email category preferences, durable outbox, reminders, permanent-failure tracking with the error class recorded | `operations.test_delivery` (6 cases); live email operations pending |
| PRIV-01 | Versioned consent, authenticated export, deletion request tracking, context revocation, worker-processed exports into expiring private artifacts, executed account deletion under an approved grace period and shared-content rule, retention sweeps for artifacts/audit/notifications | `operations.test_privacy` (25 cases) and an end-to-end run against the development server |
| Foundation | Additive migrations, staff role separation, audit records, v1 resources/retry keys, OpenAPI for implemented routes, PostgreSQL configuration, Django containers/workers, redacted telemetry, CI | Test suite (205 tests); deployment/CI/production operations still require execution |
| Private storage | Profile images, original statement uploads and exports held outside the database as private artifacts, encrypted at rest when a Fernet key is configured, served only to the owner through an expiring link; `migrate_private_bytes` moves existing rows | `operations.test_storage_migration` (7 cases); object storage in the hosting environment and key management remain operator work |
| API coverage | Resource groups for profiles, goals, credits, connections, messages, collaborations, opportunities, royalty calculations, statements, transactions, manual income, release projects, notifications, AI conversations, subscriptions, entitlements and reports | `apiv1.test_resource_coverage` (24 cases); `docs/openapi.json` regenerated with 19 paths |

## Required before calling the MVP complete

1. Approve launch markets/entity, terms/privacy, prices/limits, email/payment providers, retention/deletion/shared-data rules, moderation ownership and AI escalation. Until these exist as approved records the application stays closed: no plan limits, no privacy processing, no checkout.
2. Choose a payment provider and implement one `billing.providers.Provider` subclass for it, then verify checkout, webhook signatures, reconciliation and cancellation against the provider's own sandbox.
3. Point private artifact storage at the hosting environment's object store and manage the encryption key outside the repository; rehearse restoring artifacts alongside a database snapshot.
4. Run the AI evaluation cases against the real model, extend them with the specialists' content owners, and have the rights and royalty education reviewed by a qualified professional.
5. Validate scanning with actual malware signatures, production PostgreSQL concurrency, email delivery, backup restore, deployment rollback, observability and alerts.
6. Complete supported-browser/accessibility/manual security and load acceptance and record product approval against PRD §17.3.

Implemented since the first pass: capability entitlements across every screen and the API; the billing lifecycle behind a provider adapter; worker-processed exports and executed account deletion under an approved retention policy; private artifact storage with encryption at rest and expiring authorized downloads; email delivery failure tracking; nine further API resource groups; AI moderation, per-call cost and latency metrics, and the evaluation harness. `launch_check` now reports these as configuration and approval gates rather than missing code.

No production release, external messages, real charges or provider account changes have been performed. Test email uses local test addresses/backends. Existing user data must be backed up before applying migrations.
