from __future__ import annotations

import threading
import time

_TTL = 3600
_MAX = 512
_store: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def get(key: str) -> dict | None:
    with _lock:
        item = _store.get(key)
        if not item:
            return None
        expires, value = item
        if expires < time.time():
            _store.pop(key, None)
            return None
        return value


def put(key: str, value: dict) -> None:
    with _lock:
        now = time.time()
        if len(_store) >= _MAX:
            for k in [k for k, (e, _) in _store.items() if e < now]:
                _store.pop(k, None)
            while len(_store) >= _MAX:
                _store.pop(next(iter(_store)), None)
        _store[key] = (now + _TTL, value)
