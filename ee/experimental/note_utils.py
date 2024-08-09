import heapq

from datetime import timedelta


class NodeCandidate:
    def __init__(self, fingerpint, timestamp):
        self.fingerprint = fingerpint
        self.timestamps = set([timestamp])

    @property
    def first_timestamp(self):
        if self.timestamps:
            return min(self.timestamps)
        return None

    @property
    def last_timestamp(self):
        if self.timestamps:
            return max(self.timestamps)
        return None

    def __lt__(self, other):
        return self.last_timestamp < other.last_timestamp

    def __str__(self):
        return f'NodeCandidate(fingerprint={self.fingerprint}, first_timestamp={self.first_timestamp}, last_timestamp={self.last_timestamp}, timestamps={self.timestamps})'


class NodeCandidateQueue:
    def __init__(self, candidate_validity_window=None):
        self.queue = []
        self.candidate_validity_window = candidate_validity_window

    def push_candidate(self, candidate):
        for c in self.queue:
            if c.fingerprint == candidate.fingerprint:
                c.timestamps.update(candidate.timestamps)
                heapq.heapify(self.queue)
                return
        heapq.heappush(self.queue, candidate)

    def push_candidates(self, candidates):
        for candidate in candidates:
            self.push_candidate(candidate)

    def pop_invalid_candidates(self, current_timestamp):
        # check incident-wise consistency
        validity_threshold = current_timestamp - \
            timedelta(seconds=self.candidate_validity_window)

        while self.queue and self.queue[0].last_timestamp <= validity_threshold:
            heapq.heappop(self.queue)

        for c in self.queue:
            c.timestamps = {
                ts for ts in c.timestamps if ts > validity_threshold}
            heapq.heapify(self.queue)

    def get_candidates(self):
        return self.queue

    def copy(self):
        new_queue = NodeCandidateQueue(self.candidate_validity_window)
        new_queue.queue = self.queue.copy()
        return new_queue

    def __str__(self):
        candidates_str = "\n".join(str(candidate) for candidate in self.queue)
        return f'NodeCandidateQueue(\ncandidate_validity_window={self.candidate_validity_window}, \nqueue=[\n{candidates_str}\n])'

    def __iter__(self):
        return iter(self.queue)

    def __len__(self):
        return len(self.queue)
