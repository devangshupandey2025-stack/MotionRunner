"""Physical-device feasibility probe for the MotionRunner Android companion.

Run after starting the host on USB with `adb reverse tcp:8765 tcp:8765`, enabling
the companion Accessibility service, and pressing "Start companion connection".
"""
from __future__ import annotations

import argparse
import time
import sys
from pathlib import Path

# Allow direct `python tools/android_companion_probe.py` invocation from any cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backends.android_touch import AndroidTouchBackend, WebSocketServerTransport
from core.models.device import DeviceDescriptor, DeviceSession
from core.models.touch import TouchCommand, TouchCommandType


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a safe single-pointer drag to the Android companion")
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=1600)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--wait-seconds", type=float, default=30.0)
    parser.add_argument("--x", type=float, default=360.0)
    parser.add_argument("--y", type=float, default=800.0)
    args = parser.parse_args()

    descriptor = DeviceDescriptor("physical-device", "Android companion probe", args.width, args.height)
    backend = AndroidTouchBackend(transport=WebSocketServerTransport(args.host, args.port))
    backend.connect(DeviceSession(descriptor, backend.name))
    deadline = time.monotonic() + args.wait_seconds
    print(f"Waiting for Android companion on ws://{args.host}:{args.port} ...")
    while time.monotonic() < deadline and not backend.health().healthy:
        print(f"  {backend.health().message}")
        time.sleep(0.5)
    if not backend.health().healthy:
        raise SystemExit(f"Companion not ready: {backend.health().message}")

    now = time.perf_counter()
    commands = [
        TouchCommand(TouchCommandType.BEGIN, 0, args.x, args.y, now, 1, reason="physical_probe"),
        TouchCommand(TouchCommandType.MOVE, 0, args.x + 80, args.y, now + 0.1, 2, reason="physical_probe"),
        TouchCommand(TouchCommandType.MOVE, 0, args.x + 120, args.y + 40, now + 0.2, 3, reason="physical_probe"),
        TouchCommand(TouchCommandType.END, 0, args.x + 120, args.y + 40, now + 0.3, 4, reason="physical_probe"),
    ]
    try:
        for command in commands:
            backend.send(command)
            time.sleep(0.05)
        print("Probe commands submitted. Inspect the phone and companion logs for ACK/cancellation results.")
    finally:
        backend.close()


if __name__ == "__main__":
    main()
