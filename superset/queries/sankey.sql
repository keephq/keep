WITH time_window AS (
    SELECT datetime('now', '-140 day') as start_time,
    datetime('now') as end_time
),
total_alerts AS (
    SELECT COUNT(*) as total_count
    FROM lastalert
),
dedup_stats AS (
    -- First layer: Provider to Deduplication Status
    SELECT
        provider_type as source,
        CASE
            WHEN deduplication_type = 'full' THEN 'Deduplicated'
            WHEN deduplication_type = 'partial' THEN 'Correlated'
        END as target,
        COUNT(*) as count
    FROM alertdeduplicationevent
    WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                       AND (SELECT end_time FROM time_window)
    AND deduplication_type IN ('full', 'partial')
    GROUP BY provider_type, deduplication_type

    UNION ALL

    -- Add the non-deduplicated flow
    SELECT
        provider_type as source,
        'Not Deduplicated' as target,
        COUNT(*) as count
    FROM alert
    WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                       AND (SELECT end_time FROM time_window)
    GROUP BY provider_type

    UNION ALL

    -- Second layer: Deduplicated goes to Dropped, others go to Alert
    SELECT 'Deduplicated' as source, 'Dropped' as target, COUNT(*) as count
    FROM alertdeduplicationevent
    WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                       AND (SELECT end_time FROM time_window)
    AND deduplication_type = 'full'

    UNION ALL

    SELECT 'Correlated' as source, 'Alert' as target, COUNT(*) as count
    FROM alertdeduplicationevent
    WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                       AND (SELECT end_time FROM time_window)
    AND deduplication_type = 'partial'

    UNION ALL

    SELECT 'Not Deduplicated' as source, 'Alert' as target, COUNT(*) as count
    FROM alert
    WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                       AND (SELECT end_time FROM time_window)

    UNION ALL

    -- Third layer: Alert to Incident/Noise (10/90 split)
    SELECT
        'Alert' as source,
        'Incident' as target,
        CAST(COUNT(*) * 0.10 as INTEGER) as count
    FROM (
        SELECT * FROM alertdeduplicationevent
        WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                           AND (SELECT end_time FROM time_window)
        AND deduplication_type = 'partial'
        UNION ALL
        SELECT * FROM alert
        WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                           AND (SELECT end_time FROM time_window)
    ) combined_alerts

    UNION ALL

    SELECT
        'Alert' as source,
        'Noise' as target,
        CAST(COUNT(*) * 0.90 as INTEGER) as count
    FROM (
        SELECT * FROM alertdeduplicationevent
        WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                           AND (SELECT end_time FROM time_window)
        AND deduplication_type = 'partial'
        UNION ALL
        SELECT * FROM alert
        WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                           AND (SELECT end_time FROM time_window)
    ) combined_alerts
)
SELECT *
FROM dedup_stats
ORDER BY source, target;
