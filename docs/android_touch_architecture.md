# Android Touch Architecture

MotionRunner now has a platform-neutral touch-control slice beside the existing
keyboard runner.

```text
HandObservation
  -> HandPointerProvider
  -> PointerFilter
  -> AbsoluteMapper or VirtualJoystickMapper
  -> TouchStateMachine
  -> OutputBackend
  -> Transport (Android companion only)
```

The boundary rules are:

- Vision code emits `PointerState`; it does not import Android or backend code.
- Mapping code emits `TouchIntent`; it does not know about MediaPipe.
- `TouchStateMachine` is the only component that decides `BEGIN`, `MOVE`, `END`,
  and `CANCEL`.
- Output backends receive ordered `TouchCommand` objects only.
- The Android backend owns a versioned JSON protocol and a persistent WebSocket
  host. The companion is a reconnecting client; USB development uses `adb reverse`
  so the companion connects to device-local loopback while the host receives the
  connection on its own loopback port.
- Android APIs exist only in `android-companion/`; Python vision, gesture, mapping,
  and touch-state code never import them.

Initial host-side modules:

- `core.models`: immutable pointer, touch, device, and profile data.
- `core.ports`: backend, pointer-provider, and profile-repository contracts.
- `interaction.pointer`: hand-to-pointer conversion and filtering.
- `interaction.mapping`: absolute and virtual-joystick mapping.
- `interaction.profiles`: JSON profile loading.
- `runtime.touch_state_machine`: contact lifecycle validation.
- `runtime.touch_pipeline`: observation-to-backend orchestration.
- `backends.mock`, `backends.recording`, `backends.android_touch`: output ports.
- `runtime.replay`, `runtime.touch_debug`: deterministic recording/replay and
  backend-neutral debug-overlay data.

Sample profiles live under `profiles/`:

- `profiles/games/default_touch.json`
- `profiles/games/default_joystick.json`
- `profiles/devices/default_android.json`

## Companion protocol

Every JSON envelope contains `protocolVersion`, `messageType`, `sequenceNumber`,
`timestamp`, and `payload`. Version 1 defines `HELLO`, `DEVICE_INFO`,
`TOUCH_COMMAND`, `ACK`, `HEARTBEAT`, and `ERROR`. The host accepts a session only
after the companion reports compatible protocol support, valid display data,
single-pointer support, and an enabled Accessibility service.

The host starts a server at `127.0.0.1:8765` by default. For USB development:

```powershell
adb reverse tcp:8765 tcp:8765
```

Then start the companion connection from the installed Android app. This does not
require the PC and device to share a LAN.

Run the physical probe only on a harmless screen (it performs a short drag):

```powershell
python tools/android_companion_probe.py --width 720 --height 1600
```

## Android companion build and device validation

`android-companion/` is intentionally an independent Kotlin Android application.
Install a JDK 17+ and Android SDK Platform 36 (or open the folder in Android
Studio and let it provision matching components), then build/install the debug APK.
The environment used for this implementation has neither a JDK nor Android SDK,
so APK compilation and physical validation have not been performed here.

On Windows, `android-companion\gradlew.bat assembleDebug` bootstraps the pinned
Gradle 8.11.1 distribution locally, so no system Gradle installation is needed.

On the device, open the companion, enable **MotionRunner touch control** in
Accessibility settings, then start its connection. The companion runs a foreground
connection service and reports its capabilities after connecting.

The first physical gate is not optional: verify `BEGIN → MOVE → MOVE → END` on the
SM-A066B with a real drag, then capture accepted/cancelled segment timings. Android
Accessibility gesture dispatch serializes and may cancel in-progress gestures; the
companion therefore uses a one-pointer continued-stroke scheduler. Multi-touch and
claims of production-grade latency are deferred until that gate passes.
