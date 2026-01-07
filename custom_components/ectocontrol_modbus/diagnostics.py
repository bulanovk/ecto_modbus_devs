"""Diagnostics support for Ectocontrol Modbus Adapter v2 integration."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Return diagnostics for the config entry (gateway cache and protocol info)."""
    store = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not store:
        return {"error": "entry_not_setup"}

    gateway = store.get("gateway")
    protocol = store.get("protocol")
    coordinator = store.get("coordinator")

    return {
        "slave_id": getattr(gateway, "slave_id", None),
        "cache": getattr(gateway, "cache", {}),
        "protocol": {"port": getattr(protocol, "port", None), "baudrate": getattr(protocol, "baudrate", None)},
        "coordinator_name": getattr(coordinator, "name", None),
    }
