curl --location 'http://localhost:8080/alerts/event' \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json' \
  --header 'X-API-KEY: d508f212-12e7-4ccd-84f6-e6b1ba0c0c84' \
  --data '{
  "id": "ec365b96-4070-423d-9fc6-670c526bc383",
  "name": "Pod 'api-service-production' lacks memory",
  "status": "firing",
  "lastReceived": "2025-04-15T09:12:46.767Z",
  "environment": "production",
  "duplicateReason": null,
  "service": "QRO-Ciena.5160-SW01348",
  "source": [
    "prometheus"
  ],
  "message": "The pod 'api-service-production' lacks memory causing high error rate",
  "description": "Due to the lack of memory, the pod 'api-service-production' is experiencing high error rate",
  "severity": "critical",
  "pushed": true,
  "url": "https://www.keephq.dev?alertId=1234",
  "labels": {
    "pod": "api-service-production",
    "region": "us-east-1",
    "cpu": "88",
    "memory": "100Mi"
  },
  "ticket_url": "https://www.keephq.dev?enrichedTicketId=456",
  "fingerprint": "06b14112-f4ab-45a7-96b1-be19d1b9e246"
}'

curl --location 'http://localhost:8080/alerts/event' \
  --header 'Content-Type: application/json' \
  --header 'Accept: application/json' \
  --header 'X-API-KEY: d508f212-12e7-4ccd-84f6-e6b1ba0c0c84' \
  --data '{
  "id": "ec365b96-4070-423d-9fc6-670c526bc383",
  "name": "Pod 'api-service-production' lacks memory",
  "status": "firing",
  "lastReceived": "2025-04-15T09:12:46.767Z",
  "environment": "production",
  "duplicateReason": null,
  "service": "QRO-Juniper.ACX7024X-RT02526",
  "source": [
    "prometheus"
  ],
  "message": "The pod 'api-service-production' lacks memory causing high error rate",
  "description": "Due to the lack of memory, the pod 'api-service-production' is experiencing high error rate",
  "severity": "critical",
  "pushed": true,
  "url": "https://www.keephq.dev?alertId=1234",
  "labels": {
    "pod": "api-service-production",
    "region": "us-east-1",
    "cpu": "88",
    "memory": "100Mi"
  },
  "ticket_url": "https://www.keephq.dev?enrichedTicketId=456",
  "fingerprint": "01b14112-f4ab-45a7-96b1-be19d1b9e246"
}'
