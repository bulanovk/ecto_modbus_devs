"""Climate platform for Ectocontrol Modbus Adapter v2."""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo, CONNECTION_NETWORK_MAC

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([BoilerClimate(coordinator)])


class BoilerClimate(CoordinatorEntity, ClimateEntity):
    """Basic climate entity backed by BoilerGateway via coordinator."""

    _attr_has_entity_name = True
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Boiler"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_climate"

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
    def current_temperature(self) -> float | None:
        return self.coordinator.gateway.get_ch_temperature()

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.gateway.get_ch_setpoint()

    @property
    def hvac_action(self) -> HVACAction | None:
        burner = self.coordinator.gateway.get_burner_on()
        return HVACAction.HEATING if burner else HVACAction.IDLE

    @property
    def hvac_mode(self) -> HVACMode:
        enabled = self.coordinator.gateway.get_heating_enabled()
        return HVACMode.HEAT if enabled else HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.gateway.set_circuit_enable_bit(0, True)
        else:
            await self.coordinator.gateway.set_circuit_enable_bit(0, False)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs) -> None:
        if ATTR_TEMPERATURE in kwargs:
            temp = kwargs[ATTR_TEMPERATURE]
            raw = int(round(temp * 10))
            await self.coordinator.gateway.set_ch_setpoint(raw)
            await self.coordinator.async_request_refresh()
