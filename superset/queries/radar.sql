WITH time_window AS (
    SELECT datetime('now', '-140 day') as start_time,
    datetime('now') as end_time
),
raw_metrics AS (
    SELECT
        (SELECT COUNT(DISTINCT type)
         FROM provider) as connected_providers,

        (SELECT COUNT(*)
         FROM alert
         WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                            AND (SELECT end_time FROM time_window)) as total_alerts,

        (SELECT COUNT(*)
         FROM alertdeduplicationevent
         WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                            AND (SELECT end_time FROM time_window)) as dedup_events,

        (SELECT COUNT(*)
         FROM workflowexecution
         WHERE execution_time BETWEEN (SELECT start_time FROM time_window)
                            AND (SELECT end_time FROM time_window)) as workflow_executions,

        (SELECT CAST(COUNT(*) * 0.10 as INTEGER)
         FROM alert
         WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                            AND (SELECT end_time FROM time_window)) as incidents,

        (SELECT COUNT(*)
         FROM alertenrichment
         WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                            AND (SELECT end_time FROM time_window)) as enrichments
)
SELECT
    'Current' as group_name,
    CASE WHEN connected_providers = 0 THEN 1
         ELSE ROUND(CAST(connected_providers AS FLOAT) / NULLIF(connected_providers, 0) * 10, 2)
    END as connected_providers,
    CASE WHEN total_alerts = 0 THEN 1
         ELSE ROUND(CAST(total_alerts AS FLOAT) / NULLIF(total_alerts, 0) * 10, 2)
    END as total_alerts,
    CASE WHEN dedup_events = 0 THEN 1
         ELSE ROUND(CAST(dedup_events AS FLOAT) / NULLIF(dedup_events, 0) * 10, 2)
    END as dedup_events,
    CASE WHEN workflow_executions = 0 THEN 1
         ELSE ROUND(CAST(workflow_executions AS FLOAT) / NULLIF(workflow_executions, 0) * 10, 2)
    END as workflow_executions,
    CASE WHEN incidents = 0 THEN 1
         ELSE ROUND(CAST(incidents AS FLOAT) / NULLIF(incidents, 0) * 10, 2)
    END as incidents,
    CASE WHEN enrichments = 0 THEN 1
         ELSE ROUND(CAST(enrichments AS FLOAT) / NULLIF(enrichments, 0) * 10, 2)
    END as enrichments
FROM raw_metrics

UNION ALL

-- Add reference group with max values
SELECT
    'Max Reference' as group_name,
    10 as connected_providers,
    10 as total_alerts,
    10 as dedup_events,
    10 as workflow_executions,
    10 as incidents,
    10 as enrichments;
