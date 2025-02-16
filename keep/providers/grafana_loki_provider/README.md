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
