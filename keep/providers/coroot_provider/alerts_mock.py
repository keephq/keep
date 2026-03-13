ALERTS = {
    "Status": "CRITICAL",
    "Application": {
        "Namespace": "production",
        "Kind": "Deployment",
        "Name": "api-server",
    },
    "Reports": [
        {
            "Name": "SLO",
            "Check": "Availability",
            "Message": "error budget burn rate is 26x within 1 hour",
        }
    ],
    "URL": "https://coroot.example.com/p/project1/app/production/Deployment/api-server",
}
