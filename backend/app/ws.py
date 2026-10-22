from fastapi import WebSocket


class Manager:
    """Keeps open dashboard connections and pushes live updates to all of them."""

    def __init__(self):
        self.conns: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns.add(ws)

    def disconnect(self, ws: WebSocket):
        self.conns.discard(ws)

    async def broadcast(self, msg: dict):
        for ws in list(self.conns):
            try:
                await ws.send_json(msg)
            except Exception:
                self.conns.discard(ws)


manager = Manager()
