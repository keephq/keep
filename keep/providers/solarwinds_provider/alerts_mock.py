"""
Realistic mock alert payloads for SolarWinds Orion webhook integration.

These fixtures represent the JSON body that SolarWinds delivers to the Keep
webhook endpoint via HTTP POST when an alert is triggered or acknowledged.

Usage (pytest):
    from keep.providers.solarwinds_provider.alerts_mock import ALERTS
    payload = ALERTS["node_down"]["payload"]

Usage (manual):
    python -m keep.providers.solarwinds_provider.alerts_mock
"""

ALERTS = {
    "node_down": {
        "payload": {
            "AlertName": "Node Down",
            "AlertMessage": "Node core-sw-01.example.com is no longer reachable.",
            "AlertDescription": (
                "ICMP ping to 10.0.1.1 has failed for 3 consecutive polling cycles "
                "(300 s). Node status has changed from Up to Down."
            ),
            "AlertDetailsUrl": "https://orion.example.com/Orion/Alerts/AlertDetails.aspx?NetObjectType=N&NetObjectID=42",
            "AlertObjectID": "42",
            "AlertActiveID": "8819",
            "Severity": 2,
            "Acknowledged": False,
            "TimeOfAlert": "2024-06-12T14:32:07+00:00",
            "NodeName": "core-sw-01.example.com",
            "NodeCaption": "Core Switch 01",
            "IP_Address": "10.0.1.1",
        },
    },
    "high_cpu": {
        "payload": {
            "AlertName": "High CPU Load",
            "AlertMessage": "CPU utilization on app-srv-03 has exceeded 85% for 10 minutes.",
            "AlertDescription": (
                "Average CPU load over the last 10 minutes: 91.4%. "
                "Threshold: 85%. Investigate running processes on the node."
            ),
            "AlertDetailsUrl": "https://orion.example.com/Orion/Alerts/AlertDetails.aspx?NetObjectType=N&NetObjectID=117",
            "AlertObjectID": "117",
            "AlertActiveID": "9203",
            "Severity": 1,
            "Acknowledged": False,
            "TimeOfAlert": "2024-06-12T09:15:44+00:00",
            "NodeName": "app-srv-03.example.com",
            "NodeCaption": "Application Server 03",
            "IP_Address": "10.0.2.53",
        },
    },
    "interface_traffic": {
        "payload": {
            "AlertName": "Interface Traffic Spike",
            "AlertMessage": "Traffic on GigabitEthernet0/1 has exceeded 80% utilisation.",
            "AlertDescription": (
                "Inbound utilisation on GigabitEthernet0/1 (distrib-sw-02) reached "
                "82.3% for 5 minutes. This is an informational alert — no action required "
                "unless sustained."
            ),
            "AlertDetailsUrl": "https://orion.example.com/Orion/Alerts/AlertDetails.aspx?NetObjectType=I&NetObjectID=330",
            "AlertObjectID": "330",
            "AlertActiveID": "9451",
            "Severity": 0,
            "Acknowledged": False,
            "TimeOfAlert": "2024-06-11T22:05:11+00:00",
            "NodeName": "distrib-sw-02.example.com",
            "NodeCaption": "Distribution Switch 02",
            "IP_Address": "10.0.3.10",
        },
    },
    "disk_full_acknowledged": {
        "payload": {
            "AlertName": "Disk Volume Full",
            "AlertMessage": "Volume C:\\ on db-primary-01 is 99% full. Write operations may fail.",
            "AlertDescription": (
                "Disk volume C:\\ has reached 99% capacity (499 GB / 500 GB). "
                "Free space is critically low. Immediate action required to prevent "
                "database and OS write failures."
            ),
            "AlertDetailsUrl": "https://orion.example.com/Orion/Alerts/AlertDetails.aspx?NetObjectType=V&NetObjectID=88",
            "AlertObjectID": "88",
            "AlertActiveID": "9700",
            "Severity": 3,
            "Acknowledged": "True",
            "TimeOfAlert": "2024-06-12T16:48:00Z",
            "NodeName": "db-primary-01.example.com",
            "NodeCaption": "Primary Database Server",
            "IP_Address": "10.0.4.20",
        },
    },
    "interface_down_string_severity": {
        "payload": {
            "AlertName": "Interface Down",
            "AlertMessage": "Interface GigabitEthernet1/0/24 on access-sw-05 is down.",
            "AlertDescription": (
                "Operational status of GigabitEthernet1/0/24 changed from Up to Down. "
                "Connected device may have been unplugged or experienced a link failure."
            ),
            "AlertDetailsUrl": "https://orion.example.com/Orion/Alerts/AlertDetails.aspx?NetObjectType=I&NetObjectID=512",
            "AlertObjectID": "512",
            "AlertActiveID": "9815",
            "Severity": "1",
            "Acknowledged": False,
            "TimeOfAlert": "2024-06-13T07:22:31+00:00",
            "NodeName": "access-sw-05.example.com",
            "NodeCaption": "Access Switch 05",
            "IP_Address": "10.0.5.45",
        },
    },
    "high_memory_resolved": {
        "payload": {
            "AlertName": "High Memory Utilization",
            "AlertMessage": "Memory usage on web-front-01 is back within normal limits.",
            "AlertDescription": (
                "Memory utilisation on web-front-01 dropped from 94% to 61% after "
                "the application service was restarted. Alert has been auto-acknowledged."
            ),
            "AlertDetailsUrl": "https://orion.example.com/Orion/Alerts/AlertDetails.aspx?NetObjectType=N&NetObjectID=205",
            "AlertObjectID": "205",
            "AlertActiveID": "9100",
            "Severity": 2,
            "Acknowledged": True,
            "TimeOfAlert": "2024-06-12T11:05:22+00:00",
            "NodeName": "web-front-01.example.com",
            "NodeCaption": "Web Frontend 01",
            "IP_Address": "10.0.6.11",
        },
    },
}


if __name__ == "__main__":
    import json

    from keep.providers.solarwinds_provider.solarwinds_provider import \
        SolarwindsProvider

    print(f"{'='*70}")
    print(f"SolarWinds mock alert round-trip — {len(ALERTS)} payloads")
    print(f"{'='*70}\n")

    for name, entry in ALERTS.items():
        payload = entry["payload"]
        dto = SolarwindsProvider._format_alert(payload)
        print(f"[{name}] {payload['AlertName']}")
        print(f"     severity  : {dto.severity}")
        print(f"     status    : {dto.status}")
        print(f"     host      : {dto.host}")
        print(f"     id        : {dto.id}")
        print(f"     received  : {dto.lastReceived}")
        print()
