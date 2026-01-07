import pytest

from custom_components.ectocontrol_modbus.boiler_gateway import BoilerGateway


def test_gateway_scaling_and_invalid_values():
    class DummyProtocol:
        pass

    gw = BoilerGateway(DummyProtocol(), slave_id=1)

    # prepare cache with example registers
    gw.cache = {
        0x0018: 291,        # CH temp = 29.1°C
        0x0019: 450,        # DHW = 45.0°C
        0x001A: (12 << 8),  # pressure MSB=12 -> 1.2 bar
        0x001B: (0 << 8),   # flow MSB=0 -> 0.0 L/min
        0x001C: (75 << 8),  # modulation 75%
        0x001D: 0x0003,     # bits 0 and 1 set
        0x001E: 0x0000,
        0x0020: (0x00 << 8),
        0x0021: 0x1234,
        0x0022: 0x5678,
        0x0026: 0x0100,     # setpoint raw = 256 -> 1.0°C (256/256)
    }

    assert gw.get_ch_temperature() == pytest.approx(29.1)
    assert gw.get_dhw_temperature() == pytest.approx(45.0)
    assert gw.get_pressure() == pytest.approx(1.2)
    assert gw.get_flow_rate() == pytest.approx(0.0)
    assert gw.get_modulation_level() == 75
    assert gw.get_burner_on() is True
    assert gw.get_heating_enabled() is True
    assert gw.get_dhw_enabled() is False
    assert gw.get_main_error() == 0
    assert gw.get_manufacturer_code() == 0x1234
    assert gw.get_model_code() == 0x5678
    assert gw.get_ch_setpoint_active() == pytest.approx(1.0)
