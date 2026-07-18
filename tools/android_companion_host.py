"""Keep the MotionRunner Android companion host online.

Run this while the Android companion app is trying to connect through:

    adb reverse tcp:8765 tcp:8765

The short probe intentionally exits after sending a drag. This host stays up so
the companion does not fall back into its reconnect loop.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backends.android_touch import AndroidTouchBackend, WebSocketServerTransport
from core.models.device import DeviceDescriptor, DeviceSession
from core.models.touch import TouchCommand, TouchCommandType


def wait_until_ready(backend: AndroidTouchBackend, wait_seconds: float, status_interval: float) -> None:
    deadline = time.monotonic() + wait_seconds
    next_status = 0.0
    while time.monotonic() < deadline:
        health = backend.health()
        if health.healthy:
            print(f"Android companion ready: {health.message}")
            return
        now = time.monotonic()
        if now >= next_status:
            print(f"Waiting for Android companion: {health.message}")
            next_status = now + status_interval
        time.sleep(0.1)
    raise SystemExit(f"Companion not ready after {wait_seconds:.1f}s: {backend.health().message}")


def send_probe_drag(backend: AndroidTouchBackend, x: float, y: float) -> None:
    now = time.perf_counter()
    commands = [
        TouchCommand(TouchCommandType.BEGIN, 0, x, y, now, 1, reason="persistent_host_probe"),
        TouchCommand(TouchCommandType.MOVE, 0, x + 80, y, now + 0.1, 2, reason="persistent_host_probe"),
        TouchCommand(TouchCommandType.MOVE, 0, x + 120, y + 40, now + 0.2, 3, reason="persistent_host_probe"),
        TouchCommand(TouchCommandType.END, 0, x + 120, y + 40, now + 0.3, 4, reason="persistent_host_probe"),
    ]
    for command in commands:
        backend.send(command)
        time.sleep(0.05)
    print("Probe drag submitted.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Persistent WebSocket host for the Android companion")
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=1600)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--wait-seconds", type=float, default=60.0)
    parser.add_argument("--status-interval", type=float, default=2.0)
    parser.add_argument("--probe", action="store_true", help="Send one safe drag after the companion is ready")
    parser.add_argument("--exit-after-probe", action="store_true", help="Exit after --probe instead of staying online")
    parser.add_argument("--x", type=float, default=360.0)
    parser.add_argument("--y", type=float, default=800.0)
    args = parser.parse_args()

    descriptor = DeviceDescriptor("physical-device", "Android companion host", args.width, args.height)
    backend = AndroidTouchBackend(transport=WebSocketServerTransport(args.host, args.port))
    backend.connect(DeviceSession(descriptor, backend.name))
    print(f"MotionRunner host listening on ws://{args.host}:{args.port}")
    print("Leave this running while the Android companion is connected. Press Ctrl+C to stop.")
    try:
        wait_until_ready(backend, args.wait_seconds, args.status_interval)
        if args.probe:
            send_probe_drag(backend, args.x, args.y)
            if args.exit_after_probe:
                return
        while True:
            time.sleep(args.status_interval)
            health = backend.health()
            print(f"Host status: {'ready' if health.healthy else 'not ready'} - {health.message}")
    except KeyboardInterrupt:
        print("Stopping MotionRunner Android host.")
    finally:
        backend.close()


if __name__ == "__main__":
    main()
