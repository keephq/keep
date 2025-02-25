## VictoriaLogs Setup using Docker

1. Run the following command to start VictoriaLogs container

```bash
docker run --rm -it -p 9428:9428 -v ./victoria-logs-data:/victoria-logs-data \
  docker.io/victoriametrics/victoria-logs:v1.13.0-victorialogs
```

2. Push dummy logs to VictoriaLogs (If needed)

```bash
for i in {1..100}; do
  TIMESTAMP=$(date +%s%N)
  SEVERITY=("info" "warning" "error" "critical")
  STATUS=("success" "failure" "pending")
  DESC=("Operation completed" "Network issue detected" "User login failed" "Service restarted")

  RANDOM_SEVERITY=${SEVERITY[$RANDOM % ${#SEVERITY[@]}]}
  RANDOM_STATUS=${STATUS[$RANDOM % ${#STATUS[@]}]}
  RANDOM_DESC=${DESC[$RANDOM % ${#DESC[@]}]}

  curl -H "Content-Type: application/json" -XPOST "http://localhost:9428/insert/loki/api/v1/push?_stream_fields=instance" --data-raw \
  "{
    \"streams\": [{
      \"stream\": {
        \"instance\": \"host123\",
        \"ip\": \"192.168.1.$i\",
        \"trace_id\": \"trace_$i\",
        \"severity\": \"$RANDOM_SEVERITY\",
        \"status\": \"$RANDOM_STATUS\"
      },
      \"values\": [[\"$TIMESTAMP\", \"[$RANDOM_SEVERITY] - Status: $RANDOM_STATUS - $RANDOM_DESC\"]]
    }]
  }"
done
```
