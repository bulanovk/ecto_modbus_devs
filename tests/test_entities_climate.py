"""Tests for the BoilerClimate entity."""
import pytest

from custom_components.ectocontrol_modbus.climate import BoilerClimate


class FakeGateway:
    """Fake gateway for testing."""

    def __init__(self):
        self.slave_id = 1
        self.last_set_raw = None
        self.circuit_written = None
        # Add protocol mock for device_info tests
        self.protocol = type('obj', (object,), {'port': 'mock_port'})

    def get_ch_temperature(self):
        return 19.5

    def get_ch_setpoint(self):
        return 21.0

    def get_burner_on(self):
        return True

    def get_heating_enabled(self):
        return False

    async def set_ch_setpoint(self, raw):
        self.last_set_raw = raw
        return True

    async def set_circuit_enable_bit(self, bit, enabled):
        self.circuit_written = (bit, enabled)
        return True


class DummyCoordinator:
    """Dummy coordinator for testing."""

    def __init__(self, gateway):
        self.gateway = gateway
        self.last_update_success = True  # Add for availability tests

    async def async_request_refresh(self):
        self.refreshed = True


def test_climate_properties() -> None:
    """Test climate entity properties."""
    gw = FakeGateway()
    coord = DummyCoordinator(gw)

    c = BoilerClimate(coord)
    assert c.current_temperature == 19.5
    assert c.target_temperature == 21.0
    # hvac_action should be HEATING when burner_on True
    assert c.hvac_action.name.lower() == "heating"


@pytest.mark.asyncio
async def test_climate_set_temperature_and_mode() -> None:
    """Test climate set_temperature and set_hvac_mode actions."""
    gw = FakeGateway()
    coord = DummyCoordinator(gw)

    c = BoilerClimate(coord)

    await c.async_set_temperature(temperature=23.2)
    # climate uses raw = int(round(temp * 10)) per implementation
    assert gw.last_set_raw == int(round(23.2 * 10))

    # set hvac mode to HEAT should enable circuit bit 0
    await c.async_set_hvac_mode(c._attr_hvac_modes[0])
    assert gw.circuit_written == (0, True)
