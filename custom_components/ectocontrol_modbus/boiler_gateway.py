"""BoilerGateway: maps Modbus registers to semantic boiler values."""
from __future__ import annotations

from typing import Dict, Optional
import logging

from .const import (
    REGISTER_CH_TEMP,
    REGISTER_DHW_TEMP,
    REGISTER_PRESSURE,
    REGISTER_FLOW,
    REGISTER_MODULATION,
    REGISTER_STATES,
    REGISTER_MAIN_ERROR,
    REGISTER_ADD_ERROR,
    REGISTER_OUTDOOR_TEMP,
    REGISTER_MFG_CODE,
    REGISTER_MODEL_CODE,
    REGISTER_CH_SETPOINT,
    REGISTER_CH_SETPOINT_ACTIVE,
    REGISTER_COMMAND,
    REGISTER_COMMAND_RESULT,
    REGISTER_CIRCUIT_ENABLE,
)

_LOGGER = logging.getLogger(__name__)


class BoilerGateway:
    """High-level adapter for a single boiler slave.

    The gateway holds a `cache` dict populated by the coordinator. Values
    are raw 16-bit register integers as returned by `modbus-tk`.
    """

    def __init__(self, protocol, slave_id: int):
        self.protocol = protocol
        self.slave_id = slave_id
        self.cache: Dict[int, int] = {}

    # ---------- READ ACCESSORS (from cache) ----------

    def _get_reg(self, addr: int) -> Optional[int]:
        return self.cache.get(addr)

    def get_ch_temperature(self) -> Optional[float]:
        raw = self._get_reg(REGISTER_CH_TEMP)
        if raw is None or raw == 0x7FFF:
            return None
        # i16 scaled by 10
        # modbus-tk returns unsigned 16-bit; interpret signed
        if raw >= 0x8000:
            raw = raw - 0x10000
        return raw / 10.0

    def get_dhw_temperature(self) -> Optional[float]:
        raw = self._get_reg(REGISTER_DHW_TEMP)
        if raw is None or raw == 0x7FFF:
            return None
        return raw / 10.0

    def get_pressure(self) -> Optional[float]:
        raw = self._get_reg(REGISTER_PRESSURE)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        if msb == 0xFF:
            return None
        return msb / 10.0

    def get_flow_rate(self) -> Optional[float]:
        raw = self._get_reg(REGISTER_FLOW)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        if msb == 0xFF:
            return None
        return msb / 10.0

    def get_modulation_level(self) -> Optional[int]:
        raw = self._get_reg(REGISTER_MODULATION)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        return None if msb == 0xFF else msb

    def get_burner_on(self) -> Optional[bool]:
        raw = self._get_reg(REGISTER_STATES)
        if raw is None:
            return None
        lsb = raw & 0xFF
        return bool(lsb & 0x01)

    def get_heating_enabled(self) -> Optional[bool]:
        raw = self._get_reg(REGISTER_STATES)
        if raw is None:
            return None
        lsb = raw & 0xFF
        return bool((lsb >> 1) & 0x01)

    def get_dhw_enabled(self) -> Optional[bool]:
        raw = self._get_reg(REGISTER_STATES)
        if raw is None:
            return None
        lsb = raw & 0xFF
        return bool((lsb >> 2) & 0x01)

    def get_main_error(self) -> Optional[int]:
        raw = self._get_reg(REGISTER_MAIN_ERROR)
        if raw is None or raw == 0xFFFF:
            return None
        return raw

    def get_additional_error(self) -> Optional[int]:
        raw = self._get_reg(REGISTER_ADD_ERROR)
        if raw is None or raw == 0xFFFF:
            return None
        return raw

    def get_outdoor_temperature(self) -> Optional[int]:
        raw = self._get_reg(REGISTER_OUTDOOR_TEMP)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        if msb == 0x7F:
            return None
        # signed i8
        if msb >= 0x80:
            msb = msb - 0x100
        return msb

    def get_manufacturer_code(self) -> Optional[int]:
        raw = self._get_reg(REGISTER_MFG_CODE)
        if raw is None or raw == 0xFFFF:
            return None
        return raw

    def get_model_code(self) -> Optional[int]:
        raw = self._get_reg(REGISTER_MODEL_CODE)
        if raw is None or raw == 0xFFFF:
            return None
        return raw

    def get_ch_setpoint_active(self) -> Optional[float]:
        raw = self._get_reg(REGISTER_CH_SETPOINT_ACTIVE)
        if raw is None or raw == 0x7FFF:
            return None
        # step = 1/256 degC
        # treat as signed i16
        if raw >= 0x8000:
            raw = raw - 0x10000
        return raw / 256.0

    # ---------- WRITE HELPERS ----------

    async def set_ch_setpoint(self, value_raw: int) -> bool:
        return await self.protocol.write_register(self.slave_id, REGISTER_CH_SETPOINT, value_raw)

    async def set_dhw_setpoint(self, value: int) -> bool:
        return await self.protocol.write_register(self.slave_id, REGISTER_DHW_SETPOINT, value)

    async def set_circuit_enable_bit(self, bit: int, enabled: bool) -> bool:
        # read-modify-write 0x0039
        regs = await self.protocol.read_registers(self.slave_id, REGISTER_CIRCUIT_ENABLE, 1)
        current = regs[0] if regs else 0
        if enabled:
            newv = current | (1 << bit)
        else:
            newv = current & ~(1 << bit)
        return await self.protocol.write_register(self.slave_id, REGISTER_CIRCUIT_ENABLE, newv)

    async def reboot_adapter(self) -> bool:
        # write command 2 to 0x0080
        return await self.protocol.write_register(self.slave_id, REGISTER_COMMAND, 2)

    async def reset_boiler_errors(self) -> bool:
        return await self.protocol.write_register(self.slave_id, REGISTER_COMMAND, 3)
