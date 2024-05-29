import os
import aiokafka
import asyncio
kafka_address = os.getenv("KAFKA_CLUSTERS_BOOTSTRAPSERVERS", 'localhost:9093')
keep_topic = os.getenv("KEEP_TOPIC", "Keep2")

        
class kafka_keep_provider:
    _producer = None
    _started = False
    async def start(self):
        self._producer = aiokafka.AIOKafkaProducer(bootstrap_servers = kafka_address)
        await self._producer.start()
        self._started = True
    
    
    def __del__(self):
        asyncio.run(self._producer.stop())
    
    async def enqueue_msg(self, msg):
        if(not self._started):
            await self.start()
        await self._producer.send_and_wait(keep_topic, msg)

    
    async def send_without_batching(self, msg):
        # Create the batch without queueing for delivery.
        batch = self._producer.create_batch()

        # Populate the batch. The append() method will return metadata for the
        # added message or None if batch is full.
        for i in range(1):
            metadata = batch.append(value=b"msg %d" % i, key=None, timestamp=None)
            assert metadata is not None

        # Optionally close the batch to further submission. If left open, the batch
        # may be appended to by producer.send().
        batch.close()

        # Add the batch to the first partition's submission queue. If this method
        # times out, we can say for sure that batch will never be sent.
        fut = await self._producer.send_batch(batch, keep_topic, partition=1)

        # Batch will either be delivered or an unrecoverable error will occur.
        # Cancelling this future will not cancel the send.
        record = await fut

kafka_provider = kafka_keep_provider()