from __future__ import annotations

import os
import threading
import time

PER_MIN = int(os.environ.get("RATE_PER_MIN", "30"))
PER_DAY = int(os.environ.get("RATE_PER_DAY", "3000"))

_buckets: dict[str, dict] = {}
_lock = threading.Lock()


def check(ip: str) -> tuple[bool, int]:
    now = time.time()
    with _lock:
        b = _buckets.get(ip) or {"min": [], "day": []}
        b["min"] = [t for t in b["min"] if now - t < 60]
        b["day"] = [t for t in b["day"] if now - t < 86400]
        if len(b["min"]) >= PER_MIN:
            return False, max(1, int(60 - (now - b["min"][0])))
        if len(b["day"]) >= PER_DAY:
            return False, max(1, int(86400 - (now - b["day"][0])))
        b["min"].append(now)
        b["day"].append(now)
        _buckets[ip] = b
    return True, 0
