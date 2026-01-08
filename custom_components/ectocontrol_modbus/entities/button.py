"""Button platform for adapter commands (reboot, reset errors)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    entities = [RebootAdapterButton(coordinator), ResetErrorsButton(coordinator)]
    async_add_entities(entities)


class RebootAdapterButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Reboot Adapter"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_reboot"

    async def async_press(self) -> None:
        await self.coordinator.gateway.reboot_adapter()
        await self.coordinator.async_request_refresh()


class ResetErrorsButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Reset Boiler Errors"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_reset_errors"

    async def async_press(self) -> None:
        await self.coordinator.gateway.reset_boiler_errors()
        await self.coordinator.async_request_refresh()
