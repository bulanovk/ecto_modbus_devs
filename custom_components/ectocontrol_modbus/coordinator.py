"""DataUpdateCoordinator for polling the boiler registers."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, MODBUS_READ_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class BoilerDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that polls Modbus registers and updates the `BoilerGateway` cache."""

    def __init__(
        self,
        hass,
        gateway,
        name: str,
        update_interval: timedelta = DEFAULT_SCAN_INTERVAL,
        retry_count: int = 3,
        read_timeout: float = MODBUS_READ_TIMEOUT,
        config_entry: Optional[Any] = None,
    ):
        self.gateway = gateway
        self.name = name
        self.retry_count = retry_count
        self.read_timeout = read_timeout
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=update_interval,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> Dict[int, int]:
        """Fetch data from Modbus and update gateway cache.

        Reads registers 0x0010..0x0026 in a single batch and stores them in gateway.cache
        as a mapping {address: value}.

        Implements configurable retry logic for transient failures.
        """
        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                # Start address 0x0010, count 23 (0x0010..0x0026)
                regs = await self.gateway.protocol.read_registers(
                    self.gateway.slave_id, 0x0010, 23, timeout=self.read_timeout
                )
                if regs is None:
                    raise UpdateFailed("No response from device")

                data = {}
                base = 0x0010
                for i, v in enumerate(regs):
                    data[base + i] = v

                # Update gateway cache
                self.gateway.cache = data

                # Log retry recovery
                if attempt > 0:
                    _LOGGER.info("Recovered after %d retry attempts", attempt)

                return data

            except asyncio.TimeoutError as err:
                last_error = err
                if attempt < self.retry_count:
                    _LOGGER.warning(
                        "Timeout polling device (attempt %d/%d), retrying...",
                        attempt + 1,
                        self.retry_count + 1,
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
            except UpdateFailed:
                # Re-raise UpdateFailed immediately (already handled)
                raise
            except Exception as err:
                last_error = err
                if attempt < self.retry_count:
                    _LOGGER.warning(
                        "Error polling boiler (attempt %d/%d): %s, retrying...",
                        attempt + 1,
                        self.retry_count + 1,
                        err,
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue

        # All retries exhausted
        _LOGGER.error("Unexpected error polling boiler after %d attempts: %s", self.retry_count + 1, last_error)
        raise UpdateFailed(f"Unexpected error: {last_error}")
