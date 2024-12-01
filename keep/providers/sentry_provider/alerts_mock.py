ALERTS = {
    "browser_timeout": {
        "payload": {
            "id": "4616132097",
            "project": "frontend-app",
            "project_name": "frontend-app",
            "project_slug": "frontend-app",
            "logger": "javascript",
            "level": "error",
            "culprit": "fetchUserProfile at app.js:245",
            "message": "Failed to fetch user profile: NetworkError: Server responded with 504 Gateway Timeout",
            "url": "https://keep-dr.sentry.io/issues/4616132097/",
            "event": {
                "event_id": "a892bf7d01c640b597831fb1710e3414",
                "title": "Failed to fetch user profile",
                "level": "error",
                "type": "default",
                "logentry": {
                    "formatted": "Failed to fetch user profile: NetworkError: Server responded with 504 Gateway Timeout",
                    "message": None,
                },
                "logger": "javascript",
                "platform": "javascript",
                "timestamp": 1709991285.873,
                "environment": "production",
                "user": {
                    "id": "user_8675309",
                    "ip_address": "198.51.100.42",
                    "geo": {
                        "country_code": "US",
                        "city": "San Francisco",
                        "region": "CA",
                    },
                },
                "request": {
                    "url": "https://api.example.com/users/profile",
                    "method": "GET",
                    "headers": [
                        ["Accept", "application/json"],
                        [
                            "User-Agent",
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                        ],
                    ],
                },
                "contexts": {
                    "browser": {
                        "name": "Chrome",
                        "version": "121.0.0.0",
                        "type": "browser",
                    },
                    "client_os": {
                        "name": "Mac OS X",
                        "version": "10.15.7",
                        "type": "os",
                    },
                },
                "tags": [
                    ["browser", "Chrome 121.0.0.0"],
                    ["error.type", "NetworkError"],
                    ["http.status_code", "504"],
                    ["environment", "production"],
                ],
            },
        }
    },
    "server_overload": {
        "payload": {
            "id": "4616132098",
            "project": "frontend-app",
            "project_name": "frontend-app",
            "project_slug": "frontend-app",
            "logger": "javascript",
            "level": "error",
            "culprit": "submitOrder at checkout.js:178",
            "message": "Order submission failed: Server responded with 503 Service Unavailable - System under heavy load",
            "url": "https://keep-dr.sentry.io/issues/4616132098/",
            "event": {
                "event_id": "b723cf8e01c640b597831fb1710e3415",
                "level": "error",
                "title": "Order submission failed",
                "type": "default",
                "logentry": {
                    "formatted": "Order submission failed: Server responded with 503 Service Unavailable - System under heavy load",
                    "message": None,
                },
                "logger": "javascript",
                "platform": "javascript",
                "timestamp": 1709991385.873,
                "environment": "production",
                "user": {
                    "id": "user_2468101",
                    "ip_address": "203.0.113.25",
                    "geo": {"country_code": "GB", "city": "London", "region": "ENG"},
                },
                "request": {
                    "url": "https://api.example.com/orders/submit",
                    "method": "POST",
                    "data": {"order_id": "ORD-12345", "total": 299.99},
                    "headers": [
                        ["Content-Type", "application/json"],
                        [
                            "User-Agent",
                            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Mobile/15E148 Safari/604.1",
                        ],
                    ],
                },
                "contexts": {
                    "browser": {
                        "name": "Mobile Safari",
                        "version": "17.3.1",
                        "type": "browser",
                    },
                    "client_os": {"name": "iOS", "version": "17.3.1", "type": "os"},
                },
                "tags": [
                    ["browser", "Mobile Safari 17.3.1"],
                    ["error.type", "ApiError"],
                    ["http.status_code", "503"],
                    ["environment", "production"],
                ],
            },
        }
    },
    "database_timeout": {
        "payload": {
            "id": "4616132099",
            "project": "frontend-app",
            "project_name": "frontend-app",
            "project_slug": "frontend-app",
            "logger": "javascript",
            "level": "error",
            "culprit": "loadProductCatalog at products.js:89",
            "message": "Failed to load product catalog: Server responded with 502 Bad Gateway - Database connection timeout",
            "url": "https://keep-dr.sentry.io/issues/4616132099/",
            "event": {
                "title": "Failed to load product catalog",
                "event_id": "c634de9f01c640b597831fb1710e3416",
                "level": "error",
                "type": "default",
                "logentry": {
                    "formatted": "Failed to load product catalog: Server responded with 502 Bad Gateway - Database connection timeout",
                    "message": None,
                },
                "logger": "javascript",
                "platform": "javascript",
                "timestamp": 1709991485.873,
                "environment": "production",
                "user": {
                    "id": "user_1357924",
                    "ip_address": "192.0.2.78",
                    "geo": {"country_code": "DE", "city": "Berlin", "region": "BE"},
                },
                "request": {
                    "url": "https://api.example.com/catalog/products",
                    "method": "GET",
                    "headers": [
                        ["Accept", "application/json"],
                        [
                            "User-Agent",
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
                        ],
                    ],
                },
                "contexts": {
                    "browser": {
                        "name": "Edge",
                        "version": "120.0.0.0",
                        "type": "browser",
                    },
                    "client_os": {"name": "Windows", "version": "10", "type": "os"},
                },
                "tags": [
                    ["browser", "Edge 120.0.0.0"],
                    ["error.type", "ApiError"],
                    ["http.status_code", "502"],
                    ["environment", "production"],
                ],
            },
        }
    },
}
