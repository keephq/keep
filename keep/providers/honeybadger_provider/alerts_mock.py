ALERTS = [
    {
        "trigger": "occurrence",
        "project": {"id": "123456", "name": "MyApp"},
        "fault": {
            "id": "98765",
            "klass": "ActiveRecord::RecordNotFound",
            "message": "Couldn't find User with 'id'=99999",
            "component": "UsersController",
            "action": "show",
            "environment": "production",
            "notices_count": 47,
        },
    },
    {
        "trigger": "occurrence",
        "project": {"id": "123456", "name": "MyApp"},
        "fault": {
            "id": "98766",
            "klass": "NoMethodError",
            "message": "undefined method 'process' for nil:NilClass",
            "component": "PaymentsController",
            "action": "create",
            "environment": "production",
            "notices_count": 12,
        },
    },
    {
        "trigger": "resolved",
        "project": {"id": "123456", "name": "MyApp"},
        "fault": {
            "id": "98760",
            "klass": "Errno::ECONNREFUSED",
            "message": "Connection refused - connect(2) for 'redis.internal' port 6379",
            "component": "CacheService",
            "action": "connect",
            "environment": "production",
            "notices_count": 3,
        },
    },
]
