## Guide to deploy VictoriaMetrics using docker

### 1. Clone the repository

```bash
git clone https://github.com/VictoriaMetrics/VictoriaMetrics.git
```

### 2. Change the directory to docker

```bash
cd deployment/docker
```

### 3. Change the ports in the docker-compose file to avoid conflicts with the keep services

```bash
sed -i -e 's/3000:3000/3001:3000/' -e 's/127.0.0.1:3000/127.0.0.1:3001/' docker-compose.yml
```

### 3. Run the docker-compose file

```bash
docker-compose up -d
```

### 4. You can access the following services on the following ports

vicotriametrics - [http://localhost:8428](http://localhost:8428)
grafana - [http://localhost:3001](http://localhost:3001)
vmagent - [http://localhost:8429](http://localhost:8429)
vmalert - [http://localhost:8880](http://localhost:8880)
alertmanager - [http://localhost:9093](http://localhost:9093)
