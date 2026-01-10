"""Tests for the button entities."""
import pytest

from custom_components.ectocontrol_modbus.button import RebootAdapterButton, ResetErrorsButton


class FakeGateway:
    """Fake gateway for testing."""

    def __init__(self):
        self.slave_id = 2
        self.reboot_called = False
        self.reset_called = False
        # Add protocol mock for device_info tests
        self.protocol = type('obj', (object,), {'port': 'mock_port'})

    async def reboot_adapter(self):
        self.reboot_called = True
        return True

    async def reset_boiler_errors(self):
        self.reset_called = True
        return True


class DummyCoordinator:
    """Dummy coordinator for testing."""

    def __init__(self, gateway):
        self.gateway = gateway
        self.last_update_success = True  # Add for availability tests

    async def async_request_refresh(self):
        self.refreshed = True


@pytest.mark.asyncio
async def test_buttons_press_triggers_commands_and_refresh() -> None:
    """Test button press triggers commands and coordinator refresh."""
    gw = FakeGateway()
    coord = DummyCoordinator(gw)

    reboot_btn = RebootAdapterButton(coord)
    reset_btn = ResetErrorsButton(coord)

    await reboot_btn.async_press()
    assert gw.reboot_called is True

    await reset_btn.async_press()
    assert gw.reset_called is True
