ALERTS_MOCK = [
    # Service alert - OK state
    {
        "host_name": "web-server-01",
        "service_description": "HTTP",
        "service_state": "OK",
        "timestamp": "2024-01-01T10:00:00Z",
        "output": "HTTP OK: HTTP/1.1 200 OK - 1234 bytes in 0.123 second response time"
    },
    
    # Service alert - CRITICAL state
    {
        "host_name": "db-server-01",
        "service_description": "MySQL",
        "service_state": "CRITICAL",
        "timestamp": "2024-01-01T10:05:00Z",
        "output": "CRITICAL - Cannot connect to MySQL: Connection refused"
    },
    
    # Service alert - WARNING state
    {
        "host_name": "app-server-01",
        "service_description": "CPU Load",
        "service_state": "WARNING",
        "timestamp": "2024-01-01T10:10:00Z",
        "output": "WARNING - load average: 5.23, 4.12, 3.55"
    },
    
    # Host alert - DOWN state
    {
        "host_name": "network-switch-01",
        "host_state": "DOWN",
        "timestamp": "2024-01-01T10:15:00Z",
        "output": "PING CRITICAL - Packet loss = 100%"
    },
    
    # Host alert - UP state
    {
        "host_name": "firewall-01",
        "host_state": "UP",
        "timestamp": "2024-01-01T10:20:00Z",
        "output": "PING OK - Packet loss = 0%, RTA = 0.42 ms"
    },
    
    # Host alert - UNREACHABLE state
    {
        "host_name": "remote-site-router",
        "host_state": "UNREACHABLE",
        "timestamp": "2024-01-01T10:25:00Z",
        "output": "CRITICAL - Host Unreachable"
    },
    
    # Service alert - UNKNOWN state
    {
        "host_name": "storage-server-01",
        "service_description": "Disk Space",
        "service_state": "UNKNOWN",
        "timestamp": "2024-01-01T10:30:00Z",
        "output": "UNKNOWN - Unable to read disk statistics"
    }
]