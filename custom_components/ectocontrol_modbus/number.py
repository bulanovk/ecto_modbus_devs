"""Number platform for Ectocontrol Modbus Adapter v2."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo, CONNECTION_NETWORK_MAC

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities(
        [
            CHSetpointNumber(coordinator),
            CHMinMaxNumber(coordinator, "CH Min Limit", "ch_min", min_value=0, max_value=100),
            CHMinMaxNumber(coordinator, "CH Max Limit", "ch_max", min_value=0, max_value=100),
            DHWSetpointNumber(coordinator),
            MaxModulationNumber(coordinator),
        ]
    )


class CHSetpointNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True

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
    def device_info(self) -> DeviceInfo:
        """Return device info for entity association."""
        port = self.coordinator.gateway.protocol.port
        slave_id = self.coordinator.gateway.slave_id
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, f"{port}:{slave_id}")},
            identifiers={(DOMAIN, f"{port}:{slave_id}")},
        )

    @property
    def native_value(self):
        return self.coordinator.gateway.get_ch_setpoint_active()

    async def async_set_native_value(self, value: float) -> None:
        # convert degrees to raw (1/256 deg steps)
        raw = int(round(value * 256))
        await self.coordinator.gateway.set_ch_setpoint(raw)
        await self.coordinator.async_request_refresh()


class CHMinMaxNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, name: str, key: str, min_value: int = 0, max_value: int = 100):
        super().__init__(coordinator)
        self._attr_name = name
        self._key = key
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = 1

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_{self._key}"

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
    def native_value(self):
        # Map keys to gateway getters if present
        if self._key == "ch_min":
            return self.coordinator.gateway._get_reg(0x0033)
        if self._key == "ch_max":
            return self.coordinator.gateway._get_reg(0x0034)
        return None

    async def async_set_native_value(self, value: float) -> None:
        # write single-byte u8 values into full register (assume MSB storage)
        raw = int(value) & 0xFF
        addr = 0x0033 if self._key == "ch_min" else 0x0034
        await self.coordinator.gateway.protocol.write_register(self.coordinator.gateway.slave_id, addr, raw)
        await self.coordinator.async_request_refresh()


class DHWSetpointNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "DHW Setpoint"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_dhw_setpoint"

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
    def native_value(self):
        return self.coordinator.gateway._get_reg(0x0037)

    async def async_set_native_value(self, value: float) -> None:
        raw = int(value) & 0xFF
        await self.coordinator.gateway.set_dhw_setpoint(raw)
        await self.coordinator.async_request_refresh()


class MaxModulationNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Max Modulation"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_max_modulation"

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
    def native_value(self):
        # value stored in MSB of 16-bit register
        raw = self.coordinator.gateway._get_reg(0x0038)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        return None if msb == 0xFF else msb

    async def async_set_native_value(self, value: float) -> None:
        raw = int(value) & 0xFF
        await self.coordinator.gateway.set_max_modulation(raw)
        await self.coordinator.async_request_refresh()
