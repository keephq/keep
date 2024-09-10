## Clickhouse Setup using Docker

1. Pull the Clickhouse image from Docker Hub

```bash
docker pull clickhouse/clickhouse-server
```

2. Start the Clickhouse server container

```bash
docker run -d \
    --name clickhouse-server \
    -p 9000:9000 -p 8123:8123 \
    -e CLICKHOUSE_USER=username \
    -e CLICKHOUSE_PASSWORD=password \
    -e CLICKHOUSE_DB=database \
    -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \
    clickhouse/clickhouse-server
```

3. Get access to the Clickhouse server container's shell

```bash
docker exec -it clickhouse-server /bin/bash
```

4. Access the Clickhouse client from the container's shell

```bash
clickhouse-client
```

5. Now you can run SQL queries in the Clickhouse client

```sql
USE database;
SHOW TABLES;
```

6. Create logs_table and insert data into it

```sql
CREATE TABLE logs_table
(
    timestamp DateTime DEFAULT now(),
    level String,
    message String,
    source String,
    user_id UInt32
)
ENGINE = MergeTree
ORDER BY timestamp;
```

```sql
INSERT INTO logs_table (level, message, source, user_id) VALUES
('INFO', 'User login successful', 'auth_service', 1),
('ERROR', 'Failed to connect to database', 'db_service', 0),
('DEBUG', 'Processing payment request', 'payment_service', 5),
('INFO', 'User logged out', 'auth_service', 1),
('WARN', 'High memory usage detected', 'monitoring_service', 0),
('ERROR', 'Timeout while sending email', 'email_service', 2),
('INFO', 'File uploaded successfully', 'file_service', 3),
('DEBUG', 'Starting batch process', 'batch_service', 0),
('INFO', 'New user registered', 'auth_service', 4),
('ERROR', 'Failed to process payment', 'payment_service', 5);
```

7. Some sql queries to test

Retrieve the latest log entry

```sql
SELECT * FROM logs_table
ORDER BY timestamp DESC
LIMIT 1;
```

Retrieve Logs with a Specific User ID and Level

```sql
SELECT * FROM logs_table WHERE user_id = 5 AND level = 'DEBUG';
```