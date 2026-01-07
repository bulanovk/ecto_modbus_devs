"""DataUpdateCoordinator for polling the boiler registers."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Dict

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class BoilerDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that polls Modbus registers and updates the `BoilerGateway` cache."""

    def __init__(self, hass, gateway, name: str, update_interval: timedelta = DEFAULT_SCAN_INTERVAL):
        self.gateway = gateway
        self.name = name
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Dict[int, int]:
        """Fetch data from Modbus and update gateway cache.

        Reads registers 0x0010..0x0026 in a single batch and stores them in gateway.cache
        as a mapping {address: value}.
        """
        try:
            # Start address 0x0010, count 23 (0x0010..0x0026)
            regs = await self.gateway.protocol.read_registers(self.gateway.slave_id, 0x0010, 23, timeout=3.0)
            if regs is None:
                raise UpdateFailed("No response from device")

            data = {}
            base = 0x0010
            for i, v in enumerate(regs):
                data[base + i] = v

            # update gateway cache
            self.gateway.cache = data
            return data

        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout polling device: {err}")
        except Exception as err:
            _LOGGER.exception("Unexpected error polling boiler: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}")
