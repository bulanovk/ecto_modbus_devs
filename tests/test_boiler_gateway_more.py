import pytest

from custom_components.ectocontrol_modbus.boiler_gateway import BoilerGateway


class FakeProto:
    def __init__(self):
        self.writes = []
        self.reads = {}

    async def write_register(self, slave_id, addr, value):
        self.writes.append((slave_id, addr, value))
        return True

    async def read_registers(self, slave_id, addr, count):
        # return configured read value or zeros
        return [self.reads.get(addr, 0)]


@pytest.mark.asyncio
async def test_boiler_gateway_edge_cases_and_writes():
    proto = FakeProto()
    gw = BoilerGateway(proto, slave_id=5)

    # pressure lsb 0xFF -> None
    gw.cache = {0x001A: 0xFF}
    assert gw.get_pressure() is None

    # flow lsb 0xFF -> None
    gw.cache = {0x001B: 0xFF}
    assert gw.get_flow_rate() is None

    # modulation lsb 0xFF -> None
    gw.cache = {0x001C: 0xFF}
    assert gw.get_modulation_level() is None

    # states bits: ensure bits parsed correctly
    gw.cache = {0x001D: 0b00000110}  # burner off, heating on, dhw on
    assert gw.get_burner_on() is False
    assert gw.get_heating_enabled() is True
    assert gw.get_dhw_enabled() is True

    # main/additional error 0xFFFF -> None
    gw.cache = {0x001E: 0xFFFF, 0x001F: 0xFFFF}
    assert gw.get_main_error() is None
    assert gw.get_additional_error() is None

    # outdoor temp 0x7F -> None
    gw.cache = {0x0020: (0x7F << 8)}
    assert gw.get_outdoor_temperature() is None

    # outdoor negative -5 -> 0xFB as msb
    gw.cache = {0x0020: (0xFB << 8)}
    assert gw.get_outdoor_temperature() == -5

    # ch setpoint active negative: raw >= 0x8000
    gw.cache = {0x0026: 0xFF00}  # -256 -> -1.0
    assert gw.get_ch_setpoint_active() == pytest.approx(-1.0)

    # ch setpoint active invalid marker
    gw.cache = {0x0026: 0x7FFF}
    assert gw.get_ch_setpoint_active() is None

    # test write helpers
    ok = await gw.set_ch_setpoint(123)
    assert ok is True
    assert proto.writes[-1] == (5, 0x0031, 123)

    # test set_circuit_enable_bit uses cached value for read-modify-write
    gw.cache = {0x0039: 0x0001}  # bit 0 already set
    ok2 = await gw.set_circuit_enable_bit(2, True)
    assert ok2 is True
    # verify last write set bit 2 while preserving bit 0
    assert proto.writes[-1][2] == 0x0005  # bit 0 + bit 2 = 0x0001 | 0x0004 = 0x0005

    # reboot and reset commands
    ok3 = await gw.reboot_adapter()
    ok4 = await gw.reset_boiler_errors()
    assert ok3 is True and ok4 is True
