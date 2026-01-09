"""Tests for entity platforms covering missing branches."""
import pytest

from custom_components.ectocontrol_modbus.sensor import BoilerSensor
from custom_components.ectocontrol_modbus.binary_sensor import BoilerBinarySensor
from custom_components.ectocontrol_modbus.switch import CircuitSwitch


class DummyCoordinator:
    def __init__(self, gateway):
        self.gateway = gateway

    async def async_request_refresh(self):
        pass


class DummyGateway:
    def __init__(self):
        self.slave_id = 1
        self.cache = {}

    def get_pressure(self):
        return None

    def get_flow_rate(self):
        return None

    def get_ch_temperature(self):
        return 20.0

    def get_burner_on(self):
        return False

    def get_heating_enabled(self):
        return True

    def get_dhw_enabled(self):
        return False


def test_sensor_entity_attributes():
    """Test sensor entity attributes and unique_id."""
    gw = DummyGateway()
    coord = DummyCoordinator(gw)

    sensor = BoilerSensor(coord, "get_ch_temperature", "Test", "°C")
    assert sensor._attr_name == "Test"
    assert sensor._attr_native_unit_of_measurement == "°C"
    assert "get_ch_temperature" in sensor.unique_id


def test_binary_sensor_entity_attributes():
    """Test binary sensor entity attributes and unique_id."""
    gw = DummyGateway()
    coord = DummyCoordinator(gw)

    binary = BoilerBinarySensor(coord, "get_burner_on", "Burner")
    assert binary._attr_name == "Burner"
    assert "get_burner_on" in binary.unique_id


def test_switch_entity_cache_none():
    """Test switch when cache register is None."""
    gw = DummyGateway()
    coord = DummyCoordinator(gw)
    gw.cache = {}  # 0x001D not in cache

    switch = CircuitSwitch(coord, bit=0)
    assert switch.is_on is None


@pytest.mark.asyncio
async def test_switch_turn_on():
    """Test switch turn_on calls set_circuit_enable_bit."""
    gw = DummyGateway()
    gw.last_bit_call = None

    async def fake_set_bit(bit, enabled):
        gw.last_bit_call = (bit, enabled)
        return True

    gw.set_circuit_enable_bit = fake_set_bit
    coord = DummyCoordinator(gw)

    switch = CircuitSwitch(coord, bit=1)
    await switch.async_turn_on()
    assert gw.last_bit_call == (1, True)
