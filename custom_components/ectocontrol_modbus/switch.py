"""Switch platform for Ectocontrol Modbus Adapter v2."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo, CONNECTION_NETWORK_MAC

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    # expose heating enable (bit 0) and DHW enable (bit 1)
    async_add_entities([
        CircuitSwitch(coordinator, bit=0, name="Heating Enable"),
        CircuitSwitch(coordinator, bit=1, name="DHW Enable"),
    ])


class CircuitSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, bit: int = 0, name: str | None = None):
        super().__init__(coordinator)
        self._bit = bit
        self._attr_name = name or f"Circuit {bit}"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_circuit_{self._bit}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for entity association."""
        port = self.coordinator.gateway.protocol.port
        slave_id = self.coordinator.gateway.slave_id
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, f"{port}:{slave_id}")},
            identifiers={(DOMAIN, f"{port}:{slave_id}")},
        )

    @property
    def is_on(self) -> bool | None:
        # states may not reflect circuit enable; read from cache/register via gateway
        # this entity uses get_burner_on as a placeholder if no dedicated getter
        # use constant from const if available; fallback to literal
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
