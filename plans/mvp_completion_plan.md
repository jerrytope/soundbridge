# SoundBridge MVP completion plan

Baseline: PRD v1.0, `my_fix_finding.md`, and Django source reviewed 18 September 2026.

## Accepted decisions

- Complete all P0 requirements and supporting MVP notifications and matching explanations.
- Keep Django templates and the existing visual design, extending screens where needed. This is an explicit exception to the PRD React/TypeScript direction.
- Gate provider integrations and release on approved commercial and policy inputs; do not invent legal terms, prices, or retention periods.
- Support CSV first; defer direct royalty integrations and PRD §5.2 features.

## Implementation sequence

### 0. Decisions and evidence

Maintain a requirement/evidence matrix. Record launch markets, legal entity, language, currencies, providers, prices, quotas, cancellation/refund/grace policies, retention/deletion/shared-content rules, AI consent, moderation/escalation owners, supported CSV formats, rate provenance, and reviewed content. Independent work proceeds while dependent production features remain disabled.

### 1. Foundation

Use modular Django services shared by templates and versioned resource APIs. Add PostgreSQL production configuration, background workers, private encrypted object storage, reviewed OpenAPI, consistent errors, pagination, decimal-string money, idempotency, CSRF, role separation, and audit records. Retire destructive legacy workspace writes before shared records are introduced. Preserve existing modified initial migrations; use additive migrations. Replace the Node deployment with Django web/worker/scheduler deployment.

### 2. Identity, profiles, onboarding, privacy

Implement verification, recovery, resend limits, versioned consent, persistent goal-based onboarding, unique usernames, country/region, skills, availability, sourced credits, links/media, publication and field visibility. Unify completeness. Add authenticated tracked exports/deletion, retention jobs, and policy-governed shared-data handling. Public images require deliberate publication permissions.

### 3. Real network and collaboration

Discover published real profiles with indexed paginated filters and transparent matching. Preserve sample saves separately. Implement audited idempotent connection transitions, blocks, reports, moderation, real participants, invitations/expiry, milestones, activity, versioned splits, and acknowledgment/dispute. Add accepted-context messaging with polling, mute/report, and scanned permission-checked attachments.

### 4. Career and notifications

Curate opportunities with verification evidence, complete details, filtering, bookmarks, external application links, and tracking. Complete release editing, needs, metadata, campaign planning, dated tasks, and reminders. Add in-app/email preferences and timezone-aware deduplicated retryable delivery.

### 5. Money and rights

Implement low/mid/high estimates with immutable versioned provenance, market/period, deductions/taxes/share breakdown, save/compare/export/delete. No implicit currency conversion. Quarantine and scan uploads before isolated parsing, mapping review, confirmation, and atomic import. Handle unknowns, corrections, duplicate content, retries, traceability, reversal/deletion, and retention. Add manual income and grouped summaries. Publish reviewed category education; describe anomalies as possible issues.

### 6. AI and billing

Cover all nine PRD roles while preserving historical IDs. Authorize selected context, add feedback/reporting/deletion/moderation, evaluation datasets, versioned prompts, cost/latency monitoring and rollback. Require confirmation before applying changes. Use server-controlled entitlements and atomic usage reservations. Integrate approved checkout and verified idempotent webhooks, reconciliation, receipts, recovery, cancellation and data-preserving downgrade behavior. Redirects never grant Pro.

### 7. Production acceptance

Add CI, redacted structured telemetry and consent-aware product events. Define measurable SLOs/recovery targets. Verify encryption, dependency scanning, backups/restoration, incident procedures, migration reconciliation and rollback. Restrict beta, disable demo seeds/prototype routes in production, verify provider calls. Require evidence and product acceptance for every PRD §17.3 journey.

## Interfaces and tests

Resource groups: auth, profiles, credits, goals, connections, collaborations, messages, opportunities, release projects, royalty calculations/statements/transactions, manual income, AI conversations, subscriptions, entitlements, notifications, reports and privacy requests.

Test identity token expiry/reuse, CSRF and throttling, onboarding, visibility, export/deletion; network actor permissions, races, retries, blocks, invitation expiry and files; finite Decimal arithmetic, negative adjustments, mixed currencies, duplicate/malformed uploads, unavailable scanners, mapping corrections and retries; webhook signatures/reordering, quotas, cancellation, context permissions and AI safety; browser/keyboard/screen-reader/mobile journeys, load, backup restore, migrations and rollback.

## Review findings and limitations

The gap findings are substantially confirmed. Additional gaps include manual income, exact PRD assistant coverage, onboarding completion tracking, Node deployment files, destructive workspace replacement, API CSRF exemptions and unrestricted staff privileges. External opportunity application links satisfy MVP; internal submissions are not required.

Original review was source-only. Runtime evidence is recorded separately as implementation proceeds. Existing five modified initial migrations belong to the pre-existing working tree and must not be overwritten.
