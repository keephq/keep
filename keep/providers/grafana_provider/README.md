## How to debug with local grafana

### version 9.3.2(with the bug)
docker run -d --name=grafana -p 3001:3000 grafana/grafana-enterprise:9.3.2

### version > 9.4.7 (latest)
docker run -d --name=grafana -p 3001:3000 grafana/grafana-enterprise