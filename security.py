# -*- coding: utf-8 -*-
"""Security helpers: in-memory rate limiting for login and password reset.

Kept dependency-free and schema-free (no database change) so existing data is
never touched. Thread-safe via a single lock. State is per-process and clears
on restart, which is an accepted trade-off for this deployment's threat model.
"""
import threading
import time
from collections import defaultdict

_lock = threading.Lock()
_events = defaultdict(list)


def _prune(key, window):
    now = time.time()
    _events[key] = [t for t in _events.get(key, []) if now - t < window]
    return _events[key]


def is_blocked(key, limit, window):
    """Return True when `key` has reached `limit` events within `window` seconds."""
    with _lock:
        return len(_prune(key, window)) >= limit


def record(key):
    """Record an event (e.g. a failed login) for `key`."""
    with _lock:
        _events[key].append(time.time())


def remaining(key, limit, window):
    """Number of attempts still allowed for `key` within `window` seconds."""
    with _lock:
        return max(0, limit - len(_prune(key, window)))
