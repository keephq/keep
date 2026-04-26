## How to start Sensu Go locally

Pull and run the Sensu Go sandbox:
```bash
docker run -d --name sensu-backend \
  -p 3000:3000 -p 8080:8080 -p 8081:8081 \
  sensu/sensu:latest sensu-backend start \
  --state-dir=/var/lib/sensu/sensu-backend \
  --log-level=warn
```

Create an API key:
```bash
sensuctl configure -n --url http://localhost:8080 --username admin --password P@ssw0rd!
sensuctl api-key grant admin
```

Browse the web UI at `http://localhost:3000` (admin / P@ssw0rd!).
