## Grafana Loki Setup using Docker

1. Create a directory called loki. Make loki your current working directory.

```bash
mkdir loki
cd loki
```

2. Copy and paste the following command into your command line to download the docker-compose file.

```bash
wget https://raw.githubusercontent.com/grafana/loki/v3.4.1/production/docker-compose.yaml -O docker-compose.yaml
```

3. With loki as the current working directory, run the following ‘docker-compose` command.

```bash
docker-compose -f docker-compose.yaml up
```

4. Verify that Loki is up and running by visiting [http://localhost:3100/ready](http://localhost:3100/ready) in your browser.

Note: If the above setup does not work, please refer to the official [Grafana Loki documentation](https://grafana.com/docs/loki/latest/setup/install/docker/#install-with-docker-compose) for latest instructions.

## Grafana Loki Setup using Docker (Basic HTTP Auth)

1. Create a directory called loki. Make loki your current working directory.

```bash
mkdir loki
cd loki
```

2. Fetch the `docker-compose.auth.yml` file

```bash
wget https://raw.githubusercontent.com/keephq/keep/refs/heads/main/keep/providers/grafana_loki_provider/docker-compose.auth.yml
```

3. Create a file called `loki-basic-auth.yml` with the following content in the loki directory.

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push
    basic_auth:
      username: admin
      password: admin

scrape_configs:
- job_name: system
  static_configs:
  - targets:
      - localhost
    labels:
      job: varlogs
      __path__: /var/log/*log
```

4. Start the Loki server with Basic HTTP Auth

```bash
docker compose -f docker-compose.auth.yml up
```
