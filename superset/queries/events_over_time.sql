WITH time_window AS (
    SELECT datetime('now', '-140 day') as start_time,
    datetime('now') as end_time
)
SELECT
    date(date_hour) as event_date,
    COUNT(*) as total_events
FROM (
    -- Get events from alertdeduplicationevent
    SELECT date_hour as date_hour
    FROM alertdeduplicationevent
    WHERE date_hour BETWEEN (SELECT start_time FROM time_window)
                       AND (SELECT end_time FROM time_window)
    UNION ALL
    -- Get events from alert
    SELECT datetime(timestamp) as date_hour
    FROM alert
    WHERE timestamp BETWEEN (SELECT start_time FROM time_window)
                       AND (SELECT end_time FROM time_window)
) all_events
GROUP BY date(date_hour)
ORDER BY event_date;
