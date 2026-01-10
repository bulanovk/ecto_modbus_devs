"""Config flow for Ectocontrol Modbus Adapter v2 integration."""
from __future__ import annotations

import asyncio
from fnmatch import fnmatch
from typing import Any

import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_NAME,
    CONF_DEBUG_MODBUS,
    CONF_POLLING_INTERVAL,
    CONF_RETRY_COUNT,
    SERIAL_PORT_PATTERNS,
    DEFAULT_SCAN_INTERVAL,
    MODBUS_RETRY_COUNT,
)
from .modbus_protocol import ModbusProtocol


class EctocontrolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ectocontrol Modbus Adapter v2."""

    VERSION = 1

    def __init__(self) -> None:
        self._errors: dict[str, str] = {}
        self._ports: list[str] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return None

    def _build_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        """Build the form schema dynamically based on available ports."""
        if defaults is None:
            defaults = {}

        # Build the port schema field conditionally based on available ports
        if self._ports:
            port_schema = {
                vol.Required(
                    CONF_PORT, default=defaults.get(CONF_PORT, self._ports[0])
                ): vol.In(self._ports)
            }
        else:
            port_schema = {
                vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, "")): str
            }

        schema_dict = {
            **port_schema,
            vol.Required(
                CONF_SLAVE_ID, default=defaults.get(CONF_SLAVE_ID, 1)
            ): vol.All(int, vol.Range(min=1, max=32)),
            vol.Optional(
                CONF_NAME, default=defaults.get(CONF_NAME, "Ectocontrol Boiler")
            ): str,
            vol.Optional(
                CONF_POLLING_INTERVAL,
                default=defaults.get(CONF_POLLING_INTERVAL, DEFAULT_SCAN_INTERVAL.seconds),
            ): vol.All(int, vol.Range(min=5, max=300)),
            vol.Optional(
                CONF_RETRY_COUNT,
                default=defaults.get(CONF_RETRY_COUNT, MODBUS_RETRY_COUNT),
            ): vol.All(int, vol.Range(min=0, max=10)),
            vol.Optional(
                CONF_DEBUG_MODBUS, default=defaults.get(CONF_DEBUG_MODBUS, False)
            ): bool,
        }
        return vol.Schema(schema_dict)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step where user provides port and slave id."""
        # List all available serial ports and filter by supported patterns
        try:
            all_ports = await asyncio.to_thread(serial.tools.list_ports.comports)
            self._ports = [
                p.device for p in all_ports
                if any(fnmatch(p.device, pattern) for pattern in SERIAL_PORT_PATTERNS)
            ]
        except Exception as e:
            _LOGGER.error("Failed to list serial ports: %s", e)
            self._ports = []

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=self._build_schema(), errors={}
            )

        # Validate slave id
        try:
            slave = int(user_input[CONF_SLAVE_ID])
            if not (1 <= slave <= 32):
                raise ValueError()
        except (ValueError, KeyError):
            self._errors[CONF_SLAVE_ID] = "invalid_slave"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_schema(user_input),
                errors=self._errors,
            )

        # Check duplicates for same port and slave
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (
                entry.data.get(CONF_PORT) == user_input[CONF_PORT]
                and entry.data.get(CONF_SLAVE_ID) == slave
            ):
                self._errors[CONF_SLAVE_ID] = "already_configured"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._build_schema(user_input),
                    errors=self._errors,
                )

        # Attempt connection and basic read
        try:
            debug_modbus = user_input.get(CONF_DEBUG_MODBUS, False)
            polling_interval = user_input.get(
                CONF_POLLING_INTERVAL, DEFAULT_SCAN_INTERVAL.seconds
            )
            retry_count = user_input.get(CONF_RETRY_COUNT, MODBUS_RETRY_COUNT)

            protocol = ModbusProtocol(user_input[CONF_PORT], debug_modbus=debug_modbus)
            connected = await protocol.connect()
            if not connected:
                self._errors["base"] = "cannot_connect"
                await protocol.disconnect()
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._build_schema(user_input),
                    errors=self._errors,
                )

            try:
                regs = await protocol.read_registers(slave, 0x0010, 1, timeout=3.0)
            finally:
                await protocol.disconnect()

            if regs is None:
                self._errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._build_schema(user_input),
                    errors=self._errors,
                )
        except Exception as e:
            _LOGGER.error("Connection test failed: %s", e)
            self._errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=self._build_schema(user_input),
                errors=self._errors,
            )

        title = user_input.get(CONF_NAME) or f"{user_input[CONF_PORT]}:{slave}"
        return self.async_create_entry(
            title=title,
            data={
                CONF_PORT: user_input[CONF_PORT],
                CONF_SLAVE_ID: slave,
                CONF_NAME: user_input.get(CONF_NAME),
                CONF_DEBUG_MODBUS: debug_modbus,
                CONF_POLLING_INTERVAL: polling_interval,
                CONF_RETRY_COUNT: retry_count,
            },
        )
