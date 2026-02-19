ALERT = [{
  "eventId": "562949953436734-562949955000593",
  "alert": {
    "severity": "Info",
    "dateStartZoned": "2025-03-24 17:28:40 UTC",
    "agentId": 562949953424211,
    "ipAddress": "172.17.0.2",
    "agentName": "te",
    "ruleExpression": "Last Contact ≥ 6 minutes ago",
    "type": "Agent",
    "ruleAid": 562949953552543,
    "hostname": "te",
    "dateStart": "2025-03-24 17:28:40",
    "ruleName": "Default Agent Offline Notification",
    "alertId": 562949955000593,
    "ruleId": 562949953553310
  },
  "eventType": "ALERT_NOTIFICATION_TRIGGER",
  "agentAlert": {
    "severity": "Info",
    "dateStartZoned": "2025-03-24 17:28:40 UTC",
    "agentId": 562949953424211,
    "ipAddress": "172.17.0.2",
    "agentName": "te",
    "ruleExpression": "Last Contact ≥ 6 minutes ago",
    "type": "Agent",
    "ruleAid": 562949953552543,
    "hostname": "te",
    "dateStart": "2025-03-24 17:28:40",
    "ruleName": "Default Agent Offline Notification",
    "alertId": 562949955000593,
    "ruleId": 562949953553310
  }
},
{
  "eventId": "9437a575-4b00-44a2-899a-41d1134eef08--5abda706-c065-40fa-aa8c-059c3ac1ea9d",
  "alert": {
    "severity": "Info",
    "dateStartZoned": "2025-03-17 19:43:00 UTC",
    "apiLinks": [
      {
        "rel": "related",
        "href": "https://api.thousandeyes.com/v4/tests/562949953502258"
      },
      {
        "rel": "data",
        "href": "https://api.thousandeyes.com/v4/web/http-server/562949953502258"
      }
    ],
    "testLabels": [
      {
        "id": 562949953465712,
        "name": "Web Server"
      },
      {
        "id": 562949953465711,
        "name": "https://pdf.ezhil.dev"
      },
      {
        "id": 562949953465713,
        "name": "Health Overview Dashboard"
      }
    ],
    "active": 0,
    "ruleExpression": "Response Code is not OK (2xx)",
    "dateEnd": "2025-03-24 17:21:00",
    "type": "HTTP Server",
    "ruleAid": 562949953552543,
    "agents": [
      {
        "dateStart": "2025-03-17 19:43:00",
        "dateEnd": "2025-03-24 17:21:00",
        "active": 0,
        "metricsAtStart": "Response Code: 502",
        "metricsAtEnd": "Response Code: 200",
        "permalink": "https://app.thousandeyes.com/alerts/list/?__a=562949953552543&alertId=5abda706-c065-40fa-aa8c-059c3ac1ea9d&agentId=4503",
        "agentId": 4503,
        "agentName": "Hong Kong (Trial)"
      }
    ],
    "testTargetsDescription": [
      "https://pdf.ezhil.dev"
    ],
    "violationCount": 1,
    "dateStart": "2025-03-17 19:43:00",
    "dateEndZoned": "2025-03-24 17:21:00 UTC",
    "ruleName": "PDF Test",
    "testId": 562949953502258,
    "alertId": "5abda706-c065-40fa-aa8c-059c3ac1ea9d",
    "ruleId": 562949955720954,
    "permalink": "https://app.thousandeyes.com/alerts/list/?__a=562949953552543&alertId=5abda706-c065-40fa-aa8c-059c3ac1ea9d",
    "testName": "https://pdf.ezhil.dev - HTTP Server"
  },
  "eventType": "ALERT_NOTIFICATION_CLEAR"
}]
