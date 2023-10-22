# Run the docker-compose
```docker
docker-compose up -d
```
# Create the topic
```bash
docker-compose exec kafka /opt/kafka/bin/kafka-topics.sh --create --topic alert --partitions 1 --replication-factor 1 --zookeeper zookeeper:2181
```

# Publish event
```bash
echo "This is an test alert" | kafkacat -v -b kafka:9092 -t alert -P  -X security.protocol=SASL_PLAINTEXT  -X sasl.mechanisms=PLAIN -X sasl.username=admin -X sasl.password=admin-secret
```

# Consume event
```bash
kafkacat -v -b kafka:9092 -t alert -C -X security.protocol=SASL_PLAINTEXT -X sasl.mechanisms=PLAIN -X sasl.username=admin -X sasl.password=admin-secret
```
