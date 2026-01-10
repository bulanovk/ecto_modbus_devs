"""Tests for __init__.py setup/unload with actual entry data and service handlers."""
import asyncio
import pytest

from custom_components.ectocontrol_modbus import async_setup_entry, async_unload_entry
from custom_components.ectocontrol_modbus.const import DOMAIN, CONF_PORT, CONF_SLAVE_ID


class FakeDeviceEntry:
    def __init__(self):
        self.id = "test_device_id"


class FakeDeviceRegistry:
    def __init__(self):
        self._devices = {}

    def async_get_or_create(self, **kwargs):
        entry = FakeDeviceEntry()
        self._devices[entry.id] = entry
        return entry

    def async_get_device(self, identifiers=None, connections=None):
        return None

    def async_update_device(self, device_id, **kwargs):
        pass


class FakeServices:
    def __init__(self):
        self._registered = {}

    def async_register(self, domain, name, handler):
        self._registered[(domain, name)] = handler

    def async_remove(self, domain, name):
        self._registered.pop((domain, name), None)


class FakeConfig:
    def __init__(self):
        self.config_dir = "/tmp/config"


class FakeCoordinator:
    def __init__(self):
        self.first_refresh_called = False

    async def async_config_entry_first_refresh(self):
        self.first_refresh_called = True

    async def async_request_refresh(self):
        pass


class FakeGateway:
    def __init__(self, protocol):
        self.protocol = protocol
        self.slave_id = 1

    async def reboot_adapter(self):
        return True

    async def reset_boiler_errors(self):
        return True


class FakeProtocol:
    def __init__(self, port, debug_modbus: bool = False):
        self.port = port
        self.baudrate = 19200
        self.connected = False
        self.debug_modbus = debug_modbus

    async def connect(self):
        self.connected = True
        return True

    async def disconnect(self):
        self.connected = False


class FakeCall:
    def __init__(self, data=None):
        self.data = data or {}


class FakeHass:
    def __init__(self):
        self.data = {}
        self.services = FakeServices()
        self.config = FakeConfig()


class FakeEntry:
    def __init__(self, entry_id, port, slave_id):
        self.entry_id = entry_id
        self.data = {CONF_PORT: port, CONF_SLAVE_ID: slave_id}


@pytest.mark.asyncio
async def test_async_setup_entry_with_real_entry_and_services(monkeypatch):
    """Test async_setup_entry creates gateway/protocol/coordinator and registers services."""
    from unittest.mock import patch, MagicMock

    hass = FakeHass()
    entry = FakeEntry("entry1", "/dev/ttyUSB0", 1)

    # Create a fake coordinator that avoids the frame helper issue
    fake_coordinator = MagicMock()
    fake_coordinator.async_config_entry_first_refresh = MagicMock(return_value=asyncio.sleep(0))
    fake_coordinator.async_request_refresh = MagicMock(return_value=asyncio.sleep(0))

    with patch("custom_components.ectocontrol_modbus.dr.async_get") as mock_get_dr, \
         patch("custom_components.ectocontrol_modbus.ModbusProtocol", FakeProtocol), \
         patch("custom_components.ectocontrol_modbus.BoilerDataUpdateCoordinator", return_value=fake_coordinator), \
         patch("homeassistant.helpers.frame._hass") as mock_frame_hass:
        mock_get_dr.return_value = FakeDeviceRegistry()
        # Set up frame helper to avoid RuntimeError
        from homeassistant.helpers import frame
        mock_hass_obj = MagicMock()
        mock_hass_obj.hass = hass
        mock_frame_hass.hass = hass

        ok = await async_setup_entry(hass, entry)
        assert ok is True
        assert "entry1" in hass.data[DOMAIN]
        assert hass.services._registered[(DOMAIN, "reboot_adapter")]
        assert hass.services._registered[(DOMAIN, "reset_boiler_errors")]


@pytest.mark.asyncio
async def test_async_unload_entry_with_multiple_entries(monkeypatch):
    """Test that services are NOT removed if other entries remain."""
    from unittest.mock import patch, MagicMock

    hass = FakeHass()
    entry1 = FakeEntry("entry1", "/dev/ttyUSB0", 1)
    entry2 = FakeEntry("entry2", "/dev/ttyUSB1", 2)

    # Create a fake coordinator that avoids the frame helper issue
    fake_coordinator = MagicMock()
    fake_coordinator.async_config_entry_first_refresh = MagicMock(return_value=asyncio.sleep(0))
    fake_coordinator.async_request_refresh = MagicMock(return_value=asyncio.sleep(0))

    with patch("custom_components.ectocontrol_modbus.dr.async_get") as mock_get_dr, \
         patch("custom_components.ectocontrol_modbus.ModbusProtocol", FakeProtocol), \
         patch("custom_components.ectocontrol_modbus.BoilerDataUpdateCoordinator", return_value=fake_coordinator), \
         patch("homeassistant.helpers.frame._hass") as mock_frame_hass:
        mock_get_dr.return_value = FakeDeviceRegistry()
        # Set up frame helper to avoid RuntimeError
        mock_frame_hass.hass = hass

        await async_setup_entry(hass, entry1)
        await async_setup_entry(hass, entry2)

        # unload only entry1
        ok = await async_unload_entry(hass, entry1)
        assert ok is True
        assert "entry1" not in hass.data[DOMAIN]
        assert "entry2" in hass.data[DOMAIN]
        # services should still be registered because entry2 remains
        assert (DOMAIN, "reboot_adapter") in hass.services._registered
