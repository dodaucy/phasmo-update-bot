import asyncio
import queue

import httpx


class WebhookManager:
    def __init__(self, url: str):
        self._url = url
        self._session = httpx.AsyncClient()
        self._tasks = queue.Queue()

    async def run(self) -> None:
        while True:
            if self._tasks.empty():
                await asyncio.sleep(1)
                continue
            data = self._tasks.get()
            while True:
                r = await self._session.post(
                    self._url,
                    json=data
                )
                if r.status_code != 429:
                    r.raise_for_status()
                    break
                await asyncio.sleep(r.json()["retry_after"] / 1000)
            self._tasks.task_done()

    def send(self, data: dict) -> None:
        self._tasks.put(data)
