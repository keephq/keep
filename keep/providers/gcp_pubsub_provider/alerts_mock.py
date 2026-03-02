ALERTS = {
    "GkeSecurityBulletin": {
        "payload": {
            "message": {
                "data": "eyJ0eXBlX3VybCI6IlNFQ1VSSVRZX0JVTExFVElOIiwiY2x1c3Rlcl9uYW1lIjoicHJvZC1jbHVzdGVyLTEiLCJ0aXRsZSI6IkdLRSBTZWN1cml0eSBCdWxsZXRpbjogQ1ZFLTIwMjQtMTIzNCIsImRlc2NyaXB0aW9uIjoiQSB2dWxuZXJhYmlsaXR5IHdhcyBmb3VuZCBpbiB0aGUgTGludXgga2VybmVsIHRoYXQgY291bGQgYWxsb3cgcHJpdmlsZWdlIGVzY2FsYXRpb24uIFVwZGF0ZSB5b3VyIG5vZGVzLiIsInJlc291cmNlTmFtZSI6InByb2plY3RzL215LXByb2plY3QvbG9jYXRpb25zL3VzLWNlbnRyYWwxL2NsdXN0ZXJzL3Byb2QtY2x1c3Rlci0xIn0=",
                "attributes": {
                    "notification_type": "SECURITY_BULLETIN",
                    "cluster_name": "prod-cluster-1",
                },
                "messageId": "msg-sec-001",
                "publishTime": "2024-01-15T10:30:00.000Z",
            }
        },
    },
    "GkeUpgradeAvailable": {
        "payload": {
            "message": {
                "data": "eyJ0eXBlX3VybCI6IlVQR1JBREVfQVZBSUxBQkxFIiwiY2x1c3Rlcl9uYW1lIjoic3RhZ2luZy1jbHVzdGVyIiwidGl0bGUiOiJHS0UgVXBncmFkZSBBdmFpbGFibGU6IDEuMjguMi1na2UuMTAwMCIsImRlc2NyaXB0aW9uIjoiQSBuZXcgdmVyc2lvbiBvZiBHS0UgaXMgYXZhaWxhYmxlIGZvciB5b3VyIGNsdXN0ZXIuIn0=",
                "attributes": {
                    "notification_type": "UPGRADE_AVAILABLE",
                    "cluster_name": "staging-cluster",
                },
                "messageId": "msg-upg-002",
                "publishTime": "2024-01-15T12:00:00.000Z",
            }
        },
    },
    "GkeUpgradeForced": {
        "payload": {
            "message": {
                "data": "eyJ0eXBlX3VybCI6IlVQR1JBREVfRk9SQ0VEIiwiY2x1c3Rlcl9uYW1lIjoibGVnYWN5LWNsdXN0ZXIiLCJ0aXRsZSI6IkdLRSBGb3JjZWQgVXBncmFkZTogMS4yNSBlbmQgb2YgbGlmZSIsImRlc2NyaXB0aW9uIjoiWW91ciBjbHVzdGVyIHdpbGwgYmUgYXV0b21hdGljYWxseSB1cGdyYWRlZCBhcyB2ZXJzaW9uIDEuMjUgaXMgbm8gbG9uZ2VyIHN1cHBvcnRlZC4ifQ==",
                "attributes": {
                    "notification_type": "UPGRADE_FORCED",
                    "cluster_name": "legacy-cluster",
                },
                "messageId": "msg-frc-003",
                "publishTime": "2024-01-16T08:00:00.000Z",
            }
        },
    },
}
