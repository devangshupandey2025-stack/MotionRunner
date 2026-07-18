import tempfile
import unittest
import asyncio
import json
import threading
from dataclasses import dataclass

from backends.android_touch import AndroidTouchBackend, CompanionClient, InMemoryTransport, MessageType, ProtocolEnvelope, WebSocketServerTransport
from backends.mock import MockBackend
from backends.recording import RecordingBackend
from core.models.device import DeviceDescriptor, DeviceSession
from core.models.profile import (
    ActiveRegion,
    GameProfile,
    MappingMode,
    MappingSettings,
    VirtualJoystickSettings,
)
from core.models.touch import TouchCommandType, TouchIntent
from interaction.mapping.absolute import AbsoluteMapper
from interaction.mapping.virtual_joystick import VirtualJoystickMapper
from interaction.pointer.hand_pointer import HandPointerProvider
from interaction.pointer.pointer_filter import PointerFilter, PointerFilterSettings
from interaction.profiles import JsonProfileRepository
from runtime.touch_pipeline import TouchPipeline
from runtime.touch_state_machine import TouchStateMachine
from runtime.replay import replay_commands


@dataclass
class Observation:
    palm_x: float = 0.5
    pinch_active: bool = False
    confidence: float = 1.0
    landmarks: list[tuple[float, float]] | None = None
    timestamp: float = 1.0


class TouchStateMachineTests(unittest.TestCase):
    def test_contact_lifecycle_emits_begin_move_end(self):
        machine = TouchStateMachine()

        begin = machine.apply(TouchIntent(10, 20, True, 0, 1.0, 1))
        move = machine.apply(TouchIntent(15, 25, True, 0, 1.1, 2))
        end = machine.apply(TouchIntent(15, 25, False, 0, 1.2, 3))
        idle = machine.apply(TouchIntent(15, 25, False, 0, 1.3, 4))

        self.assertEqual([command.type for command in begin + move + end], [
            TouchCommandType.BEGIN,
            TouchCommandType.MOVE,
            TouchCommandType.END,
        ])
        self.assertEqual(idle, [])

    def test_stale_sequences_are_rejected(self):
        machine = TouchStateMachine()

        self.assertEqual(len(machine.apply(TouchIntent(10, 20, True, 0, 1.0, 2))), 1)
        self.assertEqual(machine.apply(TouchIntent(11, 21, True, 0, 1.1, 2)), [])
        self.assertEqual(machine.apply(TouchIntent(12, 22, True, 0, 1.2, 1)), [])


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.device = DeviceDescriptor("dev", "Device", 1000, 2000)

    def test_absolute_mapper_uses_active_region_and_device_pixels(self):
        profile = GameProfile(
            mapping=MappingSettings(active_region=ActiveRegion(left=0.1, top=0.2, right=0.9, bottom=0.7))
        )
        pointer = HandPointerProvider().sample(Observation(palm_x=0.5, pinch_active=True, timestamp=1.0))

        intent = AbsoluteMapper().map(pointer, profile, self.device)

        self.assertAlmostEqual(intent.x, 500.0)
        self.assertAlmostEqual(intent.y, 900.0)
        self.assertTrue(intent.contact)

    def test_virtual_joystick_mapper_clamps_to_radius(self):
        profile = GameProfile(
            mapping=MappingSettings(mode=MappingMode.VIRTUAL_JOYSTICK, dead_zone=0.0),
            joystick=VirtualJoystickSettings(center_x=0.25, center_y=0.75, radius=0.2, neutral_x=0.5, neutral_y=0.5),
        )
        pointer = HandPointerProvider().sample(Observation(palm_x=1.0, pinch_active=True, timestamp=1.0))

        intent = VirtualJoystickMapper().map(pointer, profile, self.device)

        self.assertGreater(intent.x, 250.0)
        self.assertLessEqual(intent.x, 450.0)
        self.assertTrue(intent.contact)


class PointerPipelineTests(unittest.TestCase):
    def test_pinch_drives_begin_move_end_through_mock_backend(self):
        device = DeviceDescriptor("dev", "Device", 1000, 1000)
        backend = MockBackend()
        backend.connect(DeviceSession(device, backend.name))
        pipeline = TouchPipeline(
            pointer_provider=HandPointerProvider(),
            pointer_filter=PointerFilter(PointerFilterSettings(smoothing_alpha=1.0)),
            profile=GameProfile(),
            device=device,
            backend=backend,
        )

        pipeline.update(Observation(palm_x=0.4, pinch_active=False, timestamp=1.0))
        pipeline.update(Observation(palm_x=0.4, pinch_active=True, timestamp=1.1))
        pipeline.update(Observation(palm_x=0.5, pinch_active=True, timestamp=1.2))
        pipeline.update(Observation(palm_x=0.5, pinch_active=False, timestamp=1.3))

        self.assertEqual([command.type for command in backend.commands], [
            TouchCommandType.BEGIN,
            TouchCommandType.MOVE,
            TouchCommandType.END,
        ])

    def test_android_backend_requires_capability_handshake_before_sending(self):
        transport = InMemoryTransport()
        client = CompanionClient(transport)
        backend = AndroidTouchBackend(client)
        device = DeviceDescriptor("dev", "Device", 1000, 1000)
        backend.connect(DeviceSession(device, backend.name))
        self.assertFalse(backend.health().healthy)

        transport.receive(ProtocolEnvelope(1, MessageType.HELLO, 1, 1.0, {"companionVersion": "0.1"}))
        transport.receive(ProtocolEnvelope(1, MessageType.DEVICE_INFO, 2, 1.1, {
            "companionVersion": "0.1",
            "supportedProtocolVersions": [1],
            "androidApiLevel": 36,
            "widthPx": 720,
            "heightPx": 1600,
            "density": 2.0,
            "orientation": "PORTRAIT",
            "accessibilityEnabled": True,
            "supportedFeatures": ["single_pointer", "continued_strokes"],
            "gestureLimitations": [],
            "ignoredFutureField": "allowed",
        }))

        backend.send(TouchStateMachine().apply(TouchIntent(1, 2, True, 0, 1.0, 1))[0])

        self.assertTrue(backend.health().healthy)
        self.assertEqual([message.message_type for message in transport.messages], [
            MessageType.HELLO, MessageType.ACK, MessageType.TOUCH_COMMAND,
        ])
        self.assertEqual(transport.messages[-1].payload["commandType"], "BEGIN")

    def test_android_backend_rejects_disabled_accessibility(self):
        transport = InMemoryTransport()
        client = CompanionClient(transport)
        backend = AndroidTouchBackend(client)
        backend.connect(DeviceSession(DeviceDescriptor("dev", "Device", 100, 100), backend.name))
        transport.receive(ProtocolEnvelope(1, MessageType.HELLO, 1, 1.0, {}))
        transport.receive(ProtocolEnvelope(1, MessageType.DEVICE_INFO, 2, 1.1, {
            "companionVersion": "0.1", "supportedProtocolVersions": [1], "androidApiLevel": 36,
            "widthPx": 100, "heightPx": 100, "density": 1.0, "orientation": "PORTRAIT",
            "accessibilityEnabled": False, "supportedFeatures": ["single_pointer"],
        }))
        self.assertFalse(backend.health().healthy)
        self.assertIn("Accessibility", backend.health().message)

    def test_android_backend_rejects_incompatible_protocol(self):
        transport = InMemoryTransport()
        client = CompanionClient(transport)
        backend = AndroidTouchBackend(client)
        backend.connect(DeviceSession(DeviceDescriptor("dev", "Device", 100, 100), backend.name))
        transport.receive(ProtocolEnvelope(99, MessageType.HELLO, 1, 1.0, {}))
        self.assertFalse(backend.health().healthy)
        self.assertIn("unsupported protocol", backend.health().message)

    def test_acknowledgement_clears_pending_transport_latency(self):
        transport = InMemoryTransport()
        client = CompanionClient(transport)
        backend = AndroidTouchBackend(client)
        backend.connect(DeviceSession(DeviceDescriptor("dev", "Device", 100, 100), backend.name))
        transport.receive(ProtocolEnvelope(1, MessageType.HELLO, 1, 1.0, {}))
        transport.receive(ProtocolEnvelope(1, MessageType.DEVICE_INFO, 2, 1.1, {
            "companionVersion": "0.1", "supportedProtocolVersions": [1], "androidApiLevel": 36,
            "widthPx": 100, "heightPx": 100, "density": 1.0, "orientation": "PORTRAIT",
            "accessibilityEnabled": True, "supportedFeatures": ["single_pointer"],
        }))
        backend.send(TouchStateMachine().apply(TouchIntent(1, 2, True, 0, 1.0, 1))[0])
        command_envelope = transport.messages[-1]
        transport.receive(ProtocolEnvelope(1, MessageType.ACK, 3, 1.2, {
            "ackSequenceNumber": command_envelope.sequence_number,
        }))
        self.assertEqual(backend.health().latency_ms, 0.0)


class ProfileRepositoryTests(unittest.TestCase):
    def test_loads_default_profiles(self):
        repo = JsonProfileRepository("profiles")

        game = repo.load_game_profile("default_touch")
        device = repo.load_device_profile("default_android")

        self.assertEqual(game.game_id, "default_touch")
        self.assertEqual(device.width_px, 1080)


class RecordingReplayTests(unittest.TestCase):
    def test_recording_round_trips_to_mock_backend(self):
        device = DeviceDescriptor("dev", "Device", 100, 100)
        with tempfile.TemporaryDirectory() as directory:
            path = f"{directory}/touches.json"
            recorder = RecordingBackend(path)
            recorder.connect(DeviceSession(device, recorder.name))
            source = TouchStateMachine()
            for intent in [
                TouchIntent(1, 2, True, 0, 1.0, 1),
                TouchIntent(3, 4, True, 0, 1.1, 2),
                TouchIntent(3, 4, False, 0, 1.2, 3),
            ]:
                for command in source.apply(intent):
                    recorder.send(command)
            recorder.flush()
            restored = RecordingBackend.load_commands(path)
            mock = MockBackend()
            mock.connect(DeviceSession(device, mock.name))
            self.assertEqual(replay_commands(restored, mock), 3)
            self.assertEqual(mock.commands, recorder.commands)


class WebSocketTransportTests(unittest.TestCase):
    def test_local_peer_exchanges_versioned_envelopes(self):
        received: list[ProtocolEnvelope] = []
        received_event = threading.Event()
        transport = WebSocketServerTransport(port=0)
        transport.start(lambda envelope: (received.append(envelope), received_event.set()))

        async def peer() -> ProtocolEnvelope:
            import websockets
            async with websockets.connect(f"ws://127.0.0.1:{transport.port}") as socket:
                await socket.send(json.dumps(ProtocolEnvelope(1, MessageType.HELLO, 1, 1.0, {}).to_dict()))
                self.assertTrue(await asyncio.to_thread(received_event.wait, 2))
                transport.send(ProtocolEnvelope(1, MessageType.ACK, 2, 2.0, {"ackSequenceNumber": 1}))
                return ProtocolEnvelope.from_dict(json.loads(await asyncio.wait_for(socket.recv(), 2)))

        try:
            reply = asyncio.run(peer())
        finally:
            transport.close()
        self.assertEqual(received[0].message_type, MessageType.HELLO)
        self.assertEqual(reply.message_type, MessageType.ACK)


if __name__ == "__main__":
    unittest.main()
