-- Requires PostgreSQL 16+ (IS JSON), read-only role and statement_timeout=5s.
-- Version/query-plan attestation is an activation gate, not assumed production.
WITH failures AS MATERIALIZED (
 SELECT id, uuid, graph_uuid, records, state
 FROM queue_job
 WHERE channel='root.inventory_orchestrator' AND state='failed'
 ORDER BY id LIMIT 101
), parsed AS (
 SELECT *, CASE WHEN records IS JSON OBJECT THEN records::jsonb END AS ref
 FROM failures
), identified AS (
 SELECT *, CASE WHEN ref->>'_type'='odoo_recordset'
  AND ref->>'model'='inventory.orchestrator'
  AND jsonb_typeof(ref->'ids')='array'
  THEN CASE WHEN jsonb_array_length(ref->'ids')=1
   AND jsonb_typeof(ref->'ids'->0)='number'
   AND (ref->'ids'->>0) ~ '^[1-9][0-9]{0,9}$'
   THEN (ref->'ids'->>0)::bigint END END AS candidate_operation_id
 FROM parsed
)
SELECT q.uuid::text AS job_uuid, coalesce(q.graph_uuid::text,'') AS graph_uuid,
 coalesce(o.id::text,'') AS operation_id,
 coalesce(o.state,'unknown') AS business_state,
 CASE WHEN o.id IS NULL THEN 'operation_reference_missing_or_unverified'
      ELSE 'singleton_operation_reference_verified;business_success_unverified' END AS correlation_evidence,
 CASE WHEN (SELECT count(*) FROM failures)>100 THEN 'truncated' ELSE 'retained_only' END AS coverage,
 'failed'::text AS queue_state, 'parent_failed'::text AS inventory_kind,
 'inventory-attention-v1'::text AS inventory_attention_owner, 1 AS value
FROM identified q
LEFT JOIN inventory_orchestrator o ON o.id=q.candidate_operation_id
ORDER BY q.id LIMIT 100;
