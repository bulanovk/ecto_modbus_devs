"""Switch platform for Ectocontrol Modbus Adapter v2."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    # expose a single circuit switch (bit 0) as example
    async_add_entities([CircuitSwitch(coordinator, bit=0)])


class CircuitSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, bit: int = 0):
        super().__init__(coordinator)
        self._bit = bit
        self._attr_name = f"Circuit {bit}"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_circuit_{self._bit}"

    @property
    def is_on(self) -> bool | None:
        # states may not reflect circuit enable; read from cache/register via gateway
        # this entity uses get_burner_on as a placeholder if no dedicated getter
        states = self.coordinator.gateway.cache.get(0x001D)
        if states is None:
            return None
        lsb = states & 0xFF
        return bool(lsb & (1 << self._bit))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.gateway.set_circuit_enable_bit(self._bit, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.gateway.set_circuit_enable_bit(self._bit, False)
        await self.coordinator.async_request_refresh()
