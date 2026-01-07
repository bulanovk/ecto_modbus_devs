import pytest

from custom_components.ectocontrol_modbus.entities.sensor import BoilerSensor
from custom_components.ectocontrol_modbus.entities.binary_sensor import BoilerBinarySensor
from custom_components.ectocontrol_modbus.entities.number import CHSetpointNumber
from custom_components.ectocontrol_modbus.entities.switch import CircuitSwitch


class FakeGateway:
    def __init__(self):
        self.slave_id = 1
        self.cache = {0x001D: 0}
        self.last_set_raw = None
        self.circuit_written = None

    def get_ch_temperature(self):
        return 21.5

    def get_dhw_temperature(self):
        return 45.0

    def get_pressure(self):
        return 1.2

    def get_flow_rate(self):
        return 3.4

    def get_modulation_level(self):
        return 50

    def get_outdoor_temperature(self):
        return 10

    def get_ch_setpoint_active(self):
        return 22.0

    def get_manufacturer_code(self):
        return 0x1234

    def get_model_code(self):
        return 0x5678

    async def set_ch_setpoint(self, raw):
        self.last_set_raw = raw
        return True

    async def set_circuit_enable_bit(self, bit, enabled):
        self.circuit_written = (bit, enabled)
        return True


class DummyCoordinator:
    def __init__(self, gateway):
        self.gateway = gateway

    async def async_request_refresh(self):
        self.refreshed = True


def test_boiler_sensor_native_values():
    gw = FakeGateway()
    coord = DummyCoordinator(gw)

    s = BoilerSensor(coord, "get_ch_temperature", "CH Temp", "°C")
    assert s.native_value == 21.5
    assert s.unique_id.endswith("get_ch_temperature")

    s2 = BoilerSensor(coord, "get_manufacturer_code", "MFG", "")
    assert s2.native_value == 0x1234


def test_binary_sensor_is_on():
    gw = FakeGateway()
    gw.get_burner_on = lambda: True
    coord = DummyCoordinator(gw)

    b = BoilerBinarySensor(coord, "get_burner_on", "Burner")
    assert b.is_on is True


@pytest.mark.asyncio
async def test_number_set_and_refresh():
    gw = FakeGateway()
    coord = DummyCoordinator(gw)

    num = CHSetpointNumber(coord)
    assert num.native_value == 22.0

    await num.async_set_native_value(23.5)
    # raw = round(23.5 * 256)
    assert gw.last_set_raw == int(round(23.5 * 256))


@pytest.mark.asyncio
async def test_switch_turn_on_off_and_state():
    gw = FakeGateway()
    # set bit 0 in states
    gw.cache[0x001D] = 1
    coord = DummyCoordinator(gw)

    sw = CircuitSwitch(coord, bit=0)
    assert sw.is_on is True

    await sw.async_turn_off()
    assert gw.circuit_written == (0, False)

    await sw.async_turn_on()
    assert gw.circuit_written == (0, True)
