"""Bound temporary token creation; never store plan content or forwarded headers."""
from collections import deque
import math
from threading import Lock
from time import monotonic


class SessionAdmission:
    def __init__(self, *, clock=monotonic, per_peer=10, total=120, window=60):
        self.clock, self.per_peer, self.total, self.window = clock, per_peer, total, window
        self.peers, self.recent = {}, deque()
        self.lock = Lock()

    def reserve(self, peer):
        """Return retry seconds, or admit. Peer comes only from the ASGI client."""
        with self.lock:
            now = self.clock()
            while self.recent and self.recent[0] <= now - self.window:
                self.recent.popleft()
            for key in list(self.peers):
                bucket = self.peers[key]
                while bucket and bucket[0] <= now - self.window:
                    bucket.popleft()
                if not bucket:
                    del self.peers[key]
            bucket = self.peers.get(peer, deque())
            blocked = []
            if len(bucket) >= self.per_peer:
                blocked.append(bucket[0] + self.window - now)
            if len(self.recent) >= self.total:
                blocked.append(self.recent[0] + self.window - now)
            if blocked:
                return max(1, math.ceil(max(blocked)))
            self.peers[peer] = bucket
            bucket.append(now)
            self.recent.append(now)
            return 0

    def clear(self):
        with self.lock:
            self.peers.clear()
            self.recent.clear()
