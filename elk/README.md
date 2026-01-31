# ELK Stack Integration (Development)

This directory provides a **development-only ELK harness** for running Keep services with Filebeat, Logstash, and Kibana.

It allows you to collect **Keep backend container logs**, forward them through Logstash, store them in Elasticsearch, and explore them in Kibana.  
This setup is intended for **local development, debugging, and validation only** and is not suitable for production use.

---

## Directory Structure

```
proxy/
├── docker-compose-elk.yml   # Docker Compose configuration for elk integtation
├── filebeat.yaml            # Filebeat configuration file
├── logstash.conf            # Logstash configuration example to save keep-backend logs
└── README.md                # This files
```

---

## Components

The stack consists of the following services:

- **Keep Backend**  
  The Keep API service. Logs from this container are collected by Filebeat.

- **Keep WebSocket Server**  
  WebSocket server for real-time updates.

- **Filebeat**  
  Collects Docker container logs and ships them to Logstash.  
  Configured to filter logs so only the `keep-backend-elk` service is forwarded.

- **Logstash**  
  Receives logs from Filebeat, performs safe conditional parsing, and forwards events to Elasticsearch.

- **Elasticsearch**  
  Stores backend logs in time-based indices.

- **Kibana**  
  Web UI for querying and visualizing logs stored in Elasticsearch.

---

## Configuration

### Environment Variables

Create a local `.env` file from the provided example:

```bash
cp .env.example .env
## Configuration

### Environment Variables

```env
LOGSTASH_HOST=logstash-host
LOGSTASH_PORT=5044
```

### Usage

1. Start the elk environment:

```bash
docker compose -f docker-compose-elk.yml up
```

2. To run in detached mode:

```bash
docker compose -f docker-compose-elk.yml up -d
```

3. To stop all services:

```bash
docker compose -f docker-compose-elk.yml down
```

### Accessing Services

- Keep Backend: http://localhost:8080
- Kibana: http://localhost:5601

### Kibana configuration

- Goto http://localhost:5601/app/discover
- Click "Create Data view"
- Add any name you want
- Add index pattern to `keep-backend-logs-*`
- Save data view and insect logs


## Custom Configuration

### Modifying Proxy Settings

To modify the Filebeat configuration:

1. Edit `filebeat.yml`
2. Restart the filebeat service:

```bash
docker compose -f docker-compose-elk.yml restart filebeat
```

### Modifying Logstash Settings

To modify the Logstash configuration:

1. Edit `logstash.conf`
2. Restart the logstash service:

```bash
docker compose -f docker-compose-elk.yml restart logstash
```

## Security Considerations

- This setup is intended for development environments only
- SSL is disabled for all services for simplification

## Contributing

When modifying the elk setup:

1. Document any changes to configuration files
2. Test the setup of elk environments
3. Update this README if adding new features or configurations
