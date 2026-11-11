# Inventory attention candidate — unpublished fork patch

WHY: a retained failed or uncertain Inventory job needs one durable attention case,
correlated bounded evidence, an accountable human and escalation. Existing Slack
workflow execution history does not prove delivery or business resolution. This
patch automates attention only; it has no Odoo recovery capability.

Pinned upstream: Keep v0.55.0 `ab394bf49813b92377bbce4332d4f5cad1563a9c`.
Existing tasks: [attention](https://app.clickup.com/t/1dfkggwhmck),
[coverage](https://app.clickup.com/t/1dfkggwhmcn). Independent A1 telemetry is not a
prerequisite. Detection of durable inventory progress remains unsupported without
accepted-work and verified business-effect evidence.

## Native reuse and bounded generic changes

| Hook | Why required | Native alternative evaluated / boundary |
|---|---|---|
| Reserved AlertEnrichment mutation/disposal guard | Generic enrichment can overwrite private state or overlay DTO status/assignee | Reuses native unique fingerprint/row locks; no extra storage. Only reserved keys or exact owned Incident IDs blocked. |
| Incident update/delete/merge/status/split/assign guards | ResolveOn.NEVER prevents automatic resolution but cannot protect human/generic mutation paths | Native Incident + audit + assignee retained. Exact `inventory-attention-v1:<UUID>` marker protects even lost private state. Unrelated `inventory:` prefixes/native IDs pass unchanged. |
| Native authenticated status adapter and two dedicated human routes | Human ownership and resolution must atomically change policy state and Incident | Existing `write:incident` auth verifier, trusted auth backend, configured allowed humans; API keys and impersonation rejected. Generic nonowned status is unchanged. |
| process_event early protocol filter | Disabled workflows alone still let native ingress persist/process alerts and generic Grafana send Slack | Only explicit owner `inventory-attention-v1` is gated before session/formatting. Mixed payloads preserve other alerts. Disabled or invalid config fails closed for this owner. Formatting rechecked; disabled traffic is not persisted as raw/error alerts. |
| Slack optional request_timeout | Existing transport unbounded | Default unchanged for every other consumer; Inventory opts into five seconds. Native webhook `_query` independently uses its existing ten-second timeout and response body. No new transport/retry subsystem. |

Native workflow intervals are clock drivers, not durable timers. Native Incident
PK plus reserved AlertEnrichment uniqueness/row locking serialize policy state;
no schema migration or replacement scheduler is introduced. Integrated migrated-PostgreSQL validation found upstream ORM metadata still declares fingerprint-only uniqueness while migrations 16309df224d1 and 2a6132b443ab install `(tenant_id, alert_fingerprint)`. The candidate now uses the installed composite conflict target; fixture tables mirror that migration constraint and do not alter upstream production metadata. The actual migration/image test remains authoritative. Native no-ACK/time
rules alone cannot represent uncertain delivery or safely dedupe external effects.
No exact-once remote delivery is claimed.

## Contracts and state

ACK before claim suppresses escalation. Claim first may already send even after a
later ACK; both are audited/retained. A persisted claim is not a receipt. Missing
worker/response becomes `unknown`; it is never blindly repeated. Known no-delivery
may retry within the explicit budget. Primary ACK deadline is not extended by
transport failure. Native UI summary shows every transition's status and reason.

Unknown delivery has a reconciliation deadline, then `attention.status =
manual_attention_required`; native incident assignment goes to the configured
incident lead unless a human already ACKed. A separate installed webhook provider
is attempted once, with confirmed/failed/unknown result in `attention.fallback`.
Its receiver must return a nonempty `receipt_id`; this means technical acceptance,
not human ACK. A fallback worker loss also becomes unknown, never automatic retry.
A failed or uncertain independent route leaves the assigned native queue visible.
No mechanism can promise delivery when all notification and Keep infrastructure
are unavailable; coverage and independent queue inspection are operational duties.
Configuration freezes recipients/provider IDs/deadlines per incident; drift is
quarantined, never silently adopted. Sweep rotates closed, unknown and quarantined
rows; individual corruption cannot abort unrelated cases.

`POST /incidents/{id}/inventory/resolve` requires `expected_revision`, authorized
ACK owner and evidence `{type: business_reconciliation, references: [...], summary,
operation_scope, checked_at}`; the correlated operation must be included in scope. It records native resolved/end_time/audit and private
proof atomically. The person attests reconciliation; the service does not invent
business proof from `done`. Outstanding claimed/unknown notification results require a separate human notification reconciliation before closing, so a resolved native case cannot hide pending attention. Original uncertain transport results remain retained rather than being relabeled confirmed.
`POST /incidents/{id}/inventory/reopen` requires expected revision and an explicit
reason. A new job UUID is a different case; same-job receipt freshness never
reopens. Human-authorized same-job recurrence increments generation, archives
proof/receipts and reuses a known thread. If prior send is uncertain/in-flight,
reopen refuses unless closure evidence separately includes
`notification_reconciliation: {outcome: delivered|not_delivered, references: [...],
thread_ts: <required when delivered>, claim_ids: [<each outstanding claim>]}`. Late receipts attach to their old generation.
This is human reconciliation authorization, not a timeout-based resend.

## Review, deployment and release

Inactive deployment: paused Grafana detector, both workflows disabled, empty tenant
policy, provider gate before DB/provider access, receiver owner gate before native
processing. OAC generic Grafana excludes only the explicit new owner, preserving
legacy traffic. No approved production destination/time defaults are supplied.
Activation requires written humans/coverage/channel + independent paging route,
primary and ACK/reconciliation deadlines, and proof/closure authority. 45/60/10
remain proposals, never runtime defaults.

Validation: isolated real PostgreSQL suite includes native unaffected mutation
paths, duplicates/reordering, restart, failed/uncertain delivery, ACK races,
closed/quarantine sweep fairness, authorized closure/reopen and inactive ingress.
Integrated official image/digest and actual Grafana/PG/Keep proof are recorded in
the sibling validation bundle; do not equate unit tests with deployment readiness.
Rollback: keep detector/workflows/policy inactive first, preserve native policy
state/audit, then revert image. Do not run old generic mutations against owned
records after removing guards; quarantine until reviewed state migration.

## Fork maintenance / upgrades

This is a maintained local fork, not an upstream-supported feature. The owning
team must approve any upstream update. Pin source SHA/image digest and lockfile;
rebase patch in isolation, inspect all generic mutation routes and DTO overlays,
Incident/AlertEnrichment schema, auth impersonation semantics, provider receipts,
formatter owner retention, scheduler disable semantics and entrypoint/migrations.
Run unrelated native API regression suite, real PG compatibility suite and full
inactive image test before replacing pins. No floating version auto-updates.
Future upstream extension hooks may shrink generic patches, but are not assumed.

The capped detector does not claim universal failure coverage. When the retained
query finds more than 100 results, emitted cases are explicitly `coverage_unknown`
with `missing: detector_coverage`, while observed `queue_state=failed` remains
separate evidence. Operator coverage triage is required; this increment does not
introduce a persistent pagination system or infer that omitted jobs are healthy.
The independent destination must be operationally independent of the failing Slack
path; a different provider ID or URL does not establish that. Before activation,
verify that its receiver does not proxy back into the same Slack failure domain,
that it preserves receipt evidence, and that the assigned native queue has coverage.
This is an explicit destination/coverage decision, not a claim made by the adapter.
