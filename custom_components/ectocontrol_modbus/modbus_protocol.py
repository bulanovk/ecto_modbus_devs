"""Async-friendly wrapper around modbus-tk RTU master.

Uses run_in_executor to wrap the synchronous `modbus_tk.modbus_rtu.RtuMaster` API.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import serial
import modbus_tk.defines as cst
import modbus_tk.modbus as modbus
import modbus_tk.modbus_rtu as modbus_rtu

_LOGGER = logging.getLogger(__name__)


class ModbusProtocol:
    """Async wrapper for modbus-tk RTU master.

    Methods return `None` or `False` on error to simplify callers.
    """

    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.client = None
        self._lock = asyncio.Lock()

    def _connect_sync(self):
        ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=self.timeout,
        )
        master = modbus_rtu.RtuMaster(ser)
        master.set_timeout(self.timeout)
        master.open()
        return master

    async def connect(self) -> bool:
        loop = asyncio.get_event_loop()
        try:
            self.client = await loop.run_in_executor(None, self._connect_sync)
            _LOGGER.debug("Modbus connected on %s", self.port)
            return True
        except Exception as exc:  # pragma: no cover - intentional broad catch
            _LOGGER.error("Failed to open Modbus port %s: %s", self.port, exc)
            self.client = None
            return False

    async def disconnect(self) -> None:
        if not self.client:
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self.client.close)
        except Exception:
            _LOGGER.debug("Error closing modbus client", exc_info=True)
        finally:
            self.client = None

    @property
    def is_connected(self) -> bool:
        return self.client is not None

    async def read_registers(
        self, slave_id: int, start_addr: int, count: int, timeout: Optional[float] = None
    ) -> Optional[List[int]]:
        """Read holding registers (function 0x03).

        Returns list of register values or None on error.
        """
        if not self.client:
            _LOGGER.warning("Modbus client not connected")
            return None

        async with self._lock:
            loop = asyncio.get_event_loop()
            try:
                if timeout is not None:
                    self.client.set_timeout(timeout)
                result = await loop.run_in_executor(
                    None,
                    self.client.execute,
                    slave_id,
                    cst.READ_HOLDING_REGISTERS,
                    start_addr,
                    count,
                )
                return list(result)
            except modbus.ModbusError as exc:
                _LOGGER.error("Modbus error read %s@%s: %s", start_addr, slave_id, exc)
                return None
            except Exception as exc:  # pragma: no cover
                _LOGGER.error("Unexpected error reading registers: %s", exc)
                return None

    async def read_input_registers(
        self, slave_id: int, start_addr: int, count: int
    ) -> Optional[List[int]]:
        if not self.client:
            return None
        async with self._lock:
            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    None,
                    self.client.execute,
                    slave_id,
                    cst.READ_INPUT_REGISTERS,
                    start_addr,
                    count,
                )
                return list(result)
            except Exception as exc:  # pragma: no cover
                _LOGGER.error("Modbus error read input regs: %s", exc)
                return None

    async def write_registers(self, slave_id: int, start_addr: int, values: List[int]) -> bool:
        """Write multiple holding registers (function 0x10)."""
        if not self.client:
            _LOGGER.warning("Modbus client not connected")
            return False

        async with self._lock:
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(
                    None,
                    self.client.execute,
                    slave_id,
                    cst.WRITE_MULTIPLE_REGISTERS,
                    start_addr,
                    len(values),
                    values,
                )
                return True
            except modbus.ModbusError as exc:
                _LOGGER.error("Modbus error write %s@%s: %s", start_addr, slave_id, exc)
                return False
            except Exception as exc:  # pragma: no cover
                _LOGGER.error("Unexpected error writing registers: %s", exc)
                return False

    async def write_register(self, slave_id: int, addr: int, value: int) -> bool:
        return await self.write_registers(slave_id, addr, [value])
