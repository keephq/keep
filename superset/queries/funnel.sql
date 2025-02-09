WITH time_window AS (
    SELECT datetime('now', '-140 day') as start_time,
    datetime('now') as end_time
),
-- Level 1: Total events (alerts + dedup)
total_events AS (
    SELECT COUNT(*) as value, 'Total Events' as step
    FROM (
        SELECT DISTINCT id FROM alertdeduplicationevent
        WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                           AND (SELECT end_time FROM time_window)
        UNION ALL
        SELECT id FROM alert
        WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                           AND (SELECT end_time FROM time_window)
    ) all_events
),
-- Level 2: Dedup events
dedup_events AS (
    SELECT COUNT(*) as value, 'Deduplicated Events' as step
    FROM alertdeduplicationevent
    WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                       AND (SELECT end_time FROM time_window)
),
-- Level 3: Alerts (after dedup)
alerts AS (
    SELECT COUNT(*) as value, 'Alerts' as step
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
),
-- Level 4: Incidents (10% of alerts based on your Sankey logic)
incidents AS (
    SELECT CAST(COUNT(*) * 0.10 as INTEGER) as value, 'Incidents' as step
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

-- Combine all levels
SELECT * FROM total_events
UNION ALL
SELECT * FROM dedup_events
UNION ALL
SELECT * FROM alerts
UNION ALL
SELECT * FROM incidents
ORDER BY value DESC;
