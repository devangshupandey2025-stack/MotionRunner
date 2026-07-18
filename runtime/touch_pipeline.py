from __future__ import annotations

from core.models.device import DeviceDescriptor
from core.models.profile import GameProfile, MappingMode
from core.ports.output_backend import OutputBackend
from core.ports.pointer_provider import PointerProvider
from interaction.mapping.absolute import AbsoluteMapper
from interaction.mapping.virtual_joystick import VirtualJoystickMapper
from interaction.pointer.pointer_filter import PointerFilter
from runtime.touch_state_machine import TouchStateMachine


class TouchPipeline:
    """Platform-neutral observation-to-output pipeline."""

    def __init__(
        self,
        *,
        pointer_provider: PointerProvider,
        pointer_filter: PointerFilter,
        profile: GameProfile,
        device: DeviceDescriptor,
        backend: OutputBackend,
        pointer_id: int = 0,
    ):
        self.pointer_provider = pointer_provider
        self.pointer_filter = pointer_filter
        self.profile = profile
        self.device = device
        self.backend = backend
        self.pointer_id = pointer_id
        self.state_machine = TouchStateMachine()
        self._absolute_mapper = AbsoluteMapper()
        self._joystick_mapper = VirtualJoystickMapper()

    def update(self, observation) -> int:
        pointer = self.pointer_filter.process(self.pointer_provider.sample(observation))
        mapper = self._mapper()
        intent = mapper.map(pointer, self.profile, self.device, self.pointer_id)
        commands = self.state_machine.apply(intent)
        for command in commands:
            self.backend.send(command)
        return len(commands)

    def reset(self) -> None:
        self.pointer_filter.reset()
        if hasattr(self.pointer_provider, "reset"):
            self.pointer_provider.reset()
        self.state_machine.reset()

    def _mapper(self):
        if self.profile.mapping.mode == MappingMode.VIRTUAL_JOYSTICK:
            return self._joystick_mapper
        return self._absolute_mapper
