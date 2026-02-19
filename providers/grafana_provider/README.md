## How to debug with local grafana

### version 9.3.2(with the bug)

docker run -d --name=grafana -p 3001:3000 grafana/grafana-enterprise:9.3.2

### version > 9.4.7 (latest)

docker run -d --name=grafana -p 3001:3000 grafana/grafana-enterprise

### Version 10.4 with legacy alerting

Create a custom config file

Copy# Create a custom config file
cat << EOF > grafana.ini
[alerting]
enabled = true

[unified_alerting]
enabled = false
EOF

Run Grafana with legacy alerting enabled

```
docker run -d \
  --name=grafana-legacy \
  -p 3001:3000 \
  -v $(pwd)/grafana.ini:/etc/grafana/grafana.ini \
  grafana/grafana-enterprise:10.4.0
```

Default login credentials:
username: admin
password: admin

only part that needs to be manualy:

```
curl -X POST -H "Content-Type: application/json" \
  -u admin:admin \
  http://localhost:3001/api/serviceaccounts \
  -d '{"name":"keep-service-account","role":"Admin"}'

# should get smth like:
{"id":2,"name":"keep-service-account","login":"sa-keep-service-account","orgId":1,"isDisabled":false,"role":"Admin","tokens":0,"avatarUrl":""}%

# then take the id and:
curl -X POST -H "Content-Type: application/json" \
  -u admin:admin \
  http://localhost:3001/api/serviceaccounts/2/tokens \
  -d '{"name":"keep-token"}'


# and get
{"id":1,"name":"keep-token","key":"glsa_XXXXXX"}%
```

### For Topology Quickstart
Follow this guide:
https://grafana.com/docs/tempo/latest/getting-started/docker-example/