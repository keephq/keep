## Setting up LibreNMS using Docker

1. Go to [LibreNMS Docker GitHub](https://github.com/librenms/docker)

2. Clone the repository

```bash
git clone https://github.com/librenms/docker.git
```

3. Go to the cloned repository

```bash
cd docker
```

3. Go to examples/compose

```bash
cd examples/compose
```

4. Start the containers using docker-compose

```bash
docker compose up -d
```

5. Your LibreNMS instance should be running on [http://localhost:8080](http://localhost:8080)
