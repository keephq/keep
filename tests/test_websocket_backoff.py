import unittest
import asyncio
from bounties.bounty_01_websocket_backoff import ResilientOrderbookStream

class TestResilientOrderbookStream(unittest.TestCase):
    def test_buffer_and_queue(self):
        received = []
        stream = ResilientOrderbookStream(
            uri="ws://localhost:9999",
            on_message_callback=lambda msg: received.append(msg),
            buffer_capacity=100
        )
        # Buffer packets while disconnected
        stream.buffer_packet({"price": 100, "size": 1})
        stream.buffer_packet({"price": 101, "size": 2})

        self.assertEqual(len(stream.missed_packet_buffer), 2)

        # Flush buffer
        asyncio.run(stream._flush_buffer())
        self.assertEqual(len(received), 2)
        self.assertEqual(len(stream.missed_packet_buffer), 0)
        self.assertEqual(received[0]["price"], 100)
        self.assertEqual(received[1]["price"], 101)

    def test_backoff_timing_calculation(self):
        stream = ResilientOrderbookStream(
            uri="ws://localhost:9999",
            on_message_callback=lambda msg: None
        )
        stream.base_delay = 1.0
        stream.max_delay = 30.0
        stream.backoff_factor = 2.0

        # Attempt 1: 2.0s
        delay_1 = min(stream.max_delay, stream.base_delay * (stream.backoff_factor ** 1))
        # Attempt 3: 8.0s
        delay_3 = min(stream.max_delay, stream.base_delay * (stream.backoff_factor ** 3))
        # Attempt 10: capped at 30.0s
        delay_10 = min(stream.max_delay, stream.base_delay * (stream.backoff_factor ** 10))

        self.assertEqual(delay_1, 2.0)
        self.assertEqual(delay_3, 8.0)
        self.assertEqual(delay_10, 30.0)

if __name__ == "__main__":
    unittest.main()
