import pytest
from unittest.mock import patch

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


class FakeHass:
    def __init__(self):
        self.data = {}
        self.services = FakeServices()
        self.config = FakeConfig()


class DummyEntry:
    def __init__(self, entry_id, data):
        self.entry_id = entry_id
        self.data = data


@pytest.mark.asyncio
async def test_services_register_and_cleanup():
    hass = FakeHass()
    entry = DummyEntry("e1", {CONF_PORT: "/dev/ttyUSB0", CONF_SLAVE_ID: 1})

    with patch("custom_components.ectocontrol_modbus.dr.async_get") as mock_get_dr:
        mock_get_dr.return_value = FakeDeviceRegistry()
        ok = await async_setup_entry(hass, entry)
        assert ok is True
        # services should be registered
        assert (DOMAIN, "reboot_adapter") in hass.services._registered
        assert (DOMAIN, "reset_boiler_errors") in hass.services._registered

        # unload entry should remove services because it's the last entry
        ok2 = await async_unload_entry(hass, entry)
        assert ok2 is True
        assert (DOMAIN, "reboot_adapter") not in hass.services._registered
        assert (DOMAIN, "reset_boiler_errors") not in hass.services._registered
