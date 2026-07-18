from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

from core.ports.transport import MessageHandler, Transport, TransportHealth
from backends.android_touch.protocol import ProtocolEnvelope, ProtocolError


class WebSocketServerTransport(Transport):
    """Single-companion WebSocket host.

    The Android companion is the reconnecting client.  Under USB development,
    `adb reverse tcp:<device-port> tcp:<host-port>` makes the host reachable at
    the companion's loopback address without LAN routing.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self._handler: MessageHandler | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Any = None
        self._socket: Any = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._last_message_at = 0.0
        self._last_error = ""

    def start(self, on_message: MessageHandler) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._handler = on_message
        self._ready.clear()
        self._stopped.clear()
        self._thread = threading.Thread(target=self._run, name="android-ws-host", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError(f"WebSocket transport did not start: {self._last_error or 'timeout'}")

    def _run(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._server = self._loop.run_until_complete(self._create_server())
            if self.port == 0 and self._server.sockets:
                self.port = int(self._server.sockets[0].getsockname()[1])
            self._ready.set()
            self._loop.run_forever()
        except Exception as exc:  # surfaced by start()/health()
            self._last_error = str(exc)
            self._ready.set()
        finally:
            if self._loop is not None:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self._loop.close()
            self._stopped.set()

    async def _create_server(self):
        import websockets

        return await websockets.serve(self._handle_connection, self.host, self.port)

    async def _handle_connection(self, websocket, *unused) -> None:
        with self._lock:
            previous = self._socket
            self._socket = websocket
        if previous is not None and previous is not websocket:
            await previous.close(code=1012, reason="replaced by new companion connection")
        try:
            async for raw_message in websocket:
                try:
                    if not isinstance(raw_message, str):
                        raise ProtocolError("binary WebSocket frames are not supported")
                    envelope = ProtocolEnvelope.from_dict(json.loads(raw_message))
                    self._last_message_at = time.perf_counter()
                    if self._handler is not None:
                        self._handler(envelope)
                except (json.JSONDecodeError, ProtocolError) as exc:
                    self._last_error = str(exc)
                    await websocket.send(json.dumps({
                        "protocolVersion": 1,
                        "messageType": "ERROR",
                        "sequenceNumber": 0,
                        "timestamp": time.perf_counter(),
                        "payload": {"code": "INVALID_MESSAGE", "message": str(exc)},
                    }))
        finally:
            with self._lock:
                if self._socket is websocket:
                    self._socket = None

    def send(self, envelope: ProtocolEnvelope) -> None:
        if self._loop is None or self._socket is None:
            raise RuntimeError("No Android companion is connected")
        payload = json.dumps(envelope.to_dict(), separators=(",", ":"))
        future = asyncio.run_coroutine_threadsafe(self._socket.send(payload), self._loop)
        future.result(timeout=2)

    def close(self) -> None:
        if self._loop is None:
            return

        async def shutdown() -> None:
            if self._socket is not None:
                await self._socket.close(code=1001, reason="host shutdown")
            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()
            self._loop.stop()

        asyncio.run_coroutine_threadsafe(shutdown(), self._loop)
        self._stopped.wait(timeout=3)

    def health(self) -> TransportHealth:
        connected = self._socket is not None
        if self._last_error:
            return TransportHealth(False, self._last_error)
        return TransportHealth(connected, "companion connected" if connected else "waiting for companion")
