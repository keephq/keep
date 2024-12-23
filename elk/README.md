# ELK-stack integration

This directory contains the configuration files and Docker services needed to run Keep with a filebeat container. Useful if you want to test integration of Keep backend logs with Logstash and Kibana.

## Directory Structure

```
proxy/
├── docker-compose-elk.yml   # Docker Compose configuration for elk integtation
├── filebeat.yaml            # Filebeat configuration file
├── logstash.conf            # Logstash configuration example to save keep-backend logs
└── README.md                # This files
```

## Components

The setup consists of several services:

- **Filebeat**: Filebeat container to push keep-backend logs to logstash 
- **Keep Frontend**: The Keep UI service configured to use the proxy
- **Keep Backend**: The Keep API service
- **Keep WebSocket**: The WebSocket server for real-time updates

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
