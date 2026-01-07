import importlib
import pytest

init_module = importlib.import_module("custom_components.ectocontrol_modbus")


class DummyHass:
    def __init__(self):
        self.data = {}


@pytest.mark.asyncio
async def test_async_setup_and_entry_unload():
    hass = DummyHass()
    ok = await init_module.async_setup(hass, {})
    assert ok is True
    assert init_module.DOMAIN in hass.data

    ok2 = await init_module.async_setup_entry(hass, entry=None)
    assert ok2 is True

    ok3 = await init_module.async_unload_entry(hass, entry=None)
    assert ok3 is True
