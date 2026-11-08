"""In-process pub/sub that powers live sync (Server-Sent Events).

Route handlers are sync (run in a threadpool), so publish() hands events to the
event loop thread-safely. One process = one broker; for multi-worker deployments
swap this for Redis pub/sub (see ARCHITECTURE.md).
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict


class Broker:
    def __init__(self) -> None:
        self._subs: dict[int, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, group_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[group_id].add(q)
        return q

    def unsubscribe(self, group_id: int, q: asyncio.Queue) -> None:
        self._subs[group_id].discard(q)

    def subscriber_count(self, group_id: int) -> int:
        return len(self._subs.get(group_id, ()))

    def publish(self, group_id: int, event: str, data: dict | None = None) -> None:
        if not self._loop or not self._subs.get(group_id):
            return
        payload = json.dumps({"type": event, **(data or {})})
        for q in list(self._subs[group_id]):
            self._loop.call_soon_threadsafe(self._put, q, payload)

    @staticmethod
    def _put(q: asyncio.Queue, payload: str) -> None:
        if q.full():  # slow consumer: drop oldest
            q.get_nowait()
        q.put_nowait(payload)


broker = Broker()
