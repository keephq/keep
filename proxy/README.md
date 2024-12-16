# Development Proxy Setup

This directory contains the configuration files and Docker services needed to run Keep with a proxy setup, primarily used for testing and development scenarios requiring proxy configurations (e.g., corporate environments, Azure AD authentication).

## Directory Structure

```
proxy/
├── docker-compose-proxy.yml   # Docker Compose configuration for proxy setup
├── squid.conf                 # Squid proxy configuration
├── nginx.conf                 # Nginx reverse proxy configuration
└── README.md                  # This file
```

## Components

The setup consists of several services:

- **Squid Proxy**: Acts as a forward proxy for HTTP/HTTPS traffic
- **Nginx**: Serves as a reverse proxy/tunnel
- **Keep Frontend**: The Keep UI service configured to use the proxy
- **Keep Backend**: The Keep API service
- **Keep WebSocket**: The WebSocket server for real-time updates

## Network Architecture

The setup uses two Docker networks:

- `proxy-net`: External network for proxy communication
- `internal`: Internal network with no external access (secure network for inter-service communication)

## Configuration

### Environment Variables

The Keep Frontend service is preconfigured with proxy-related environment variables:

```env
http_proxy=http://proxy:3128
https_proxy=http://proxy:3128
HTTP_PROXY=http://proxy:3128
HTTPS_PROXY=http://proxy:3128
npm_config_proxy=http://proxy:3128
npm_config_https_proxy=http://proxy:3128
```

### Usage

1. Start the proxy environment:

```bash
docker compose -f docker-compose-proxy.yml up
```

2. To run in detached mode:

```bash
docker compose -f docker-compose-proxy.yml up -d
```

3. To stop all services:

```bash
docker compose -f docker-compose-proxy.yml down
```

### Accessing Services

- Keep Frontend: http://localhost:3000
- Keep Backend: http://localhost:8080
- Squid Proxy: localhost:3128

## Custom Configuration

### Modifying Proxy Settings

To modify the Squid proxy configuration:

1. Edit `squid.conf`
2. Restart the proxy service:

```bash
docker compose -f docker-compose-proxy.yml restart proxy
```

### Modifying Nginx Settings

To modify the Nginx reverse proxy configuration:

1. Edit `nginx.conf`
2. Restart the nginx service:

```bash
docker compose -f docker-compose-proxy.yml restart tunnel
```

## Troubleshooting

If you encounter connection issues:

1. Verify proxy is running:

```bash
docker compose -f docker-compose-proxy.yml ps
```

2. Check proxy logs:

```bash
docker compose -f docker-compose-proxy.yml logs proxy
```

3. Test proxy connection:

```bash
curl -x http://localhost:3128 https://www.google.com
```

## Development Notes

- The proxy setup is primarily intended for development and testing
- When using Azure AD authentication, ensure the proxy configuration matches your environment's requirements
- SSL certificate validation is disabled by default for development purposes (`npm_config_strict_ssl=false`)

## Security Considerations

- This setup is intended for development environments only
- The internal network is isolated from external access for security
- Modify security settings in `squid.conf` and `nginx.conf` according to your requirements

## Contributing

When modifying the proxy setup:

1. Document any changes to configuration files
2. Test the setup with both proxy and non-proxy environments
3. Update this README if adding new features or configurations
