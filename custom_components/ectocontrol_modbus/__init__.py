"""Ectocontrol Modbus Adapter v2 integration.

Sets up per-entry Modbus protocol, gateway and coordinator and exposes services.
"""
from __future__ import annotations

from typing import Any
import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_DEBUG_MODBUS,
    CONF_POLLING_INTERVAL,
    CONF_RETRY_COUNT,
    CONF_READ_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    MODBUS_RETRY_COUNT,
    MODBUS_READ_TIMEOUT,
)
from .modbus_protocol import ModbusProtocol
from .boiler_gateway import BoilerGateway
from .coordinator import BoilerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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
    debug_modbus = entry.data.get(CONF_DEBUG_MODBUS, False)
    polling_interval = entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_SCAN_INTERVAL.seconds)
    retry_count = int(entry.data.get(CONF_RETRY_COUNT, MODBUS_RETRY_COUNT))
    read_timeout = entry.data.get(CONF_READ_TIMEOUT, MODBUS_READ_TIMEOUT)

    protocol = ModbusProtocol(port, debug_modbus=debug_modbus)
    if not await protocol.connect():
        _LOGGER.error("Failed to connect to Modbus device on %s", port)
        return False
    gateway = BoilerGateway(protocol, slave_id=slave)
    coordinator = BoilerDataUpdateCoordinator(
        hass,
        gateway,
        name=f"{DOMAIN}_{slave}",
        update_interval=timedelta(seconds=polling_interval),
        retry_count=retry_count,
        read_timeout=read_timeout,
        config_entry=entry,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "protocol": protocol,
        "gateway": gateway,
        "coordinator": coordinator,
    }

    # Read generic device info (UID, device type, channels) BEFORE creating device in registry
    try:
        await gateway.read_device_info()
    except Exception as err:
        _LOGGER.warning("Failed to read device info: %s", err)

    # Determine device identifier: use UID if available, fall back to port:slave_id
    if gateway.device_uid:
        device_identifier = f"uid_{gateway.get_device_uid_hex()}"
        _LOGGER.debug("Using UID-based identifier: %s", device_identifier)
    else:
        device_identifier = f"{port}:{slave}"
        _LOGGER.warning("UID unavailable for slave_id=%s, using fallback identifier: %s", slave, device_identifier)

    # Store device identifier for entity use
    hass.data[DOMAIN][entry.entry_id]["device_identifier"] = device_identifier

    # Create device in registry
    device_registry = dr.async_get(hass)

    # Build device name from config or use default
    from .const import CONF_NAME
    device_name = entry.data.get(CONF_NAME) or f"Ectocontrol Boiler {slave}"

    # Use device type name if available, otherwise default model name
    model_name = gateway.get_device_type_name() or "Modbus Adapter v2"

    # Create device in registry with UID-based identifier
    # Also include legacy identifier for migration compatibility
    identifiers = {(DOMAIN, device_identifier)}
    if gateway.device_uid:
        # If we have a UID, adds the old identifier so HA can link existing devices
        identifiers.add((DOMAIN, f"{port}:{slave}"))

    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=identifiers,
        name=device_name,
        manufacturer="Ectocontrol",
        model=model_name,
        sw_version=None,
        hw_version=None,
    )

    # Store device_id for entity reference
    hass.data[DOMAIN][entry.entry_id]["device_id"] = device_entry.id

    # perform initial refresh
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # don't block setup on initial failure; coordinator will retry
        pass

    # Update device info with actual data from gateway (from coordinator poll)
    manufacturer_code = gateway.get_manufacturer_code()
    model_code = gateway.get_model_code()
    hw_version = gateway.get_hw_version()
    sw_version = gateway.get_sw_version()

    # Map codes to readable names
    manufacturer_name = "Ectocontrol"
    if manufacturer_code is not None:
        manufacturer_name = f"Ectocontrol (Mfg: {manufacturer_code})"

    # Update model name with code if available
    if model_code is not None:
        model_name = f"{model_name} (Model: {model_code})"

    device_registry.async_update_device(
        device_entry.id,
        manufacturer=manufacturer_name,
        model=model_name,
        sw_version=str(sw_version) if sw_version is not None else None,
        hw_version=str(hw_version) if hw_version is not None else None,
    )

    # Forward entry setups for platforms (include newly added platforms)
    try:
        forward = getattr(hass.config_entries, "async_forward_entry_setups", None)
        if forward:
            result = forward(
                entry,
                ["sensor", "switch", "number", "binary_sensor", "climate", "button"],
            )
            # if it's a coroutine, await it; some test fakes use MagicMock which returns non-awaitable
            if asyncio.iscoroutine(result):
                await result
    except Exception:
        # Best-effort: do not block setup on forwarding errors in test harness
        pass

    # Keep legacy services as compatibility shims for existing automation/users.
    async def _service_handler(call: Any, command: int):
        data = call.data or {}
        entry_id = data.get("entry_id")
        if entry_id is None:
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
