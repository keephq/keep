# Run the docker-compose
```docker
docker-compose up -d
```
# Create the topic
```bash
docker-compose exec kafka /opt/kafka/bin/kafka-topics.sh --create --topic alert --partitions 1 --replication-factor 1 --zookeeper zookeeper:2181
```

# Publish event

## With SASL
```bash
echo '{"id": "1234","name": "Kafka Alert","status": "firing", "lastReceived": "2023-10-23T09:56:44.950Z","environment": "production","isDuplicate": false,  "duplicateReason": null,  "service": "backend","message": "Alert from Kafka", "description": "Alert kafka description", "severity": "critical",  "pushed": true,  "event_id": "1234",  "url": "https://www.google.com/search?q=open+source+alert+management"}' | kafkacat -v -b kafka:9092 -t alert -P  -X security.protocol=SASL_PLAINTEXT  -X sasl.mechanisms=PLAIN -X sasl.username=admin -X sasl.password=admin-secret
```

## Without SASL
```bash
echo '{"id": "1234","name": "Kafka Alert","status": "firing", "lastReceived": "2023-10-23T09:56:44.950Z","environment": "production","isDuplicate": false,  "duplicateReason": null,  "service": "backend","message": "Alert from Kafka", "description": "Alert kafka description", "severity": "critical",  "pushed": true,  "event_id": "1234",  "url": "https://www.google.com/search?q=open+source+alert+management"}' | kafkacat -v -b kafka:9092 -t alert -P
```


# Consume event
```bash
kafkacat -v -b kafka:9092 -t alert -C -X security.protocol=SASL_PLAINTEXT -X sasl.mechanisms=PLAIN -X sasl.username=admin -X sasl.password=admin-secret
```
