"""Number platform for Ectocontrol Modbus Adapter v2."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([CHSetpointNumber(coordinator)])


class CHSetpointNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "CH Setpoint"
        self._attr_native_min_value = -10.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1 / 256.0

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_ch_setpoint"

    @property
    def native_value(self):
        return self.coordinator.gateway.get_ch_setpoint_active()

    async def async_set_native_value(self, value: float) -> None:
        # convert degrees to raw (1/256 deg steps)
        raw = int(round(value * 256))
        await self.coordinator.gateway.set_ch_setpoint(raw)
        await self.coordinator.async_request_refresh()
