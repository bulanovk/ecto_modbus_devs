"""Ectocontrol Modbus Adapter v2 integration.

Sets up per-entry Modbus protocol, gateway and coordinator and exposes services.
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_PORT, CONF_SLAVE_ID
from .modbus_protocol import ModbusProtocol
from .boiler_gateway import BoilerGateway
from .coordinator import BoilerDataUpdateCoordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up a config entry: create protocol, gateway, coordinator, register services."""
    hass.data.setdefault(DOMAIN, {})

    # support tests that call async_setup_entry with entry=None
    if entry is None:
        return True

    port = entry.data.get(CONF_PORT)
    slave = entry.data.get(CONF_SLAVE_ID)

    protocol = ModbusProtocol(port)
    gateway = BoilerGateway(protocol, slave_id=slave)
    coordinator = BoilerDataUpdateCoordinator(hass, gateway, name=f"{DOMAIN}_{slave}")

    hass.data[DOMAIN][entry.entry_id] = {
        "protocol": protocol,
        "gateway": gateway,
        "coordinator": coordinator,
    }

    # perform initial refresh
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # don't block setup on initial failure; coordinator will retry
        pass

    # register simple services for reboot and reset errors
    async def _service_handler(call: Any, command: int):
        data = call.data or {}
        entry_id = data.get("entry_id")
        if entry_id is None:
            # if single entry, use this one
            entries = list(hass.data[DOMAIN].keys())
            if len(entries) == 1:
                entry_id = entries[0]
            else:
                return

        ent = hass.data[DOMAIN].get(entry_id)
        if not ent:
            return
        gw: BoilerGateway = ent["gateway"]
        await gw.protocol.connect()
        try:
            if command == 2:
                await gw.reboot_adapter()
            elif command == 3:
                await gw.reset_boiler_errors()
        finally:
            await gw.protocol.disconnect()
            # refresh coordinator cache
            try:
                await ent["coordinator"].async_request_refresh()
            except Exception:
                pass

    hass.services.async_register(DOMAIN, "reboot_adapter", lambda call: _service_handler(call, 2))
    hass.services.async_register(DOMAIN, "reset_boiler_errors", lambda call: _service_handler(call, 3))

    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry and remove stored state."""
    if entry is None:
        return True
    hass.data[DOMAIN].pop(entry.entry_id, None)
    # If no entries remain, unregister integration-level services
    if not hass.data[DOMAIN]:
        try:
            hass.services.async_remove(DOMAIN, "reboot_adapter")
        except Exception:
            pass
        try:
            hass.services.async_remove(DOMAIN, "reset_boiler_errors")
        except Exception:
            pass
    return True
