## How to start SigNoz locally

Run SigNoz using Docker Compose:
```bash
git clone -b main https://github.com/SigNoz/signoz.git
cd signoz/deploy/
docker compose -f docker/clickhouse-setup/docker-compose.yaml up -d
```

SigNoz UI will be available at `http://localhost:3301`.

Generate an API key under **Settings > API Keys**, then use it as the `api_key` configuration field.
