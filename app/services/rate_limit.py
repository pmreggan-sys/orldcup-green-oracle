from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = limit_per_minute
        self.window_s = 60
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> tuple[bool, int]:
        now = time.time()
        async with self._lock:
            entries = self._requests[key]
            while entries and now - entries[0] > self.window_s:
                entries.popleft()
            if len(entries) >= self.limit_per_minute:
                retry_after = max(1, int(self.window_s - (now - entries[0])))
                return False, retry_after
            entries.append(now)
            return True, 0
