"""Tests for entity platform async_setup_entry functions."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from custom_components.ectocontrol_modbus.const import DOMAIN


class FakeEntry:
    def __init__(self, entry_id="test_entry"):
        self.entry_id = entry_id


class FakeCoordinator:
    def __init__(self):
        self.gateway = MagicMock()
        self.name = "test_coordinator"


@pytest.mark.asyncio
async def test_sensor_async_setup_entry():
    """Test sensor platform async_setup_entry."""
    from custom_components.ectocontrol_modbus.entities.sensor import async_setup_entry as sensor_setup

    hass = MagicMock(spec=HomeAssistant)
    entry = FakeEntry()
    coordinator = FakeCoordinator()

    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "coordinator": coordinator,
            }
        }
    }

    entities_added = []

    def add_entities(entities):
        entities_added.extend(entities)

    await sensor_setup(hass, entry, add_entities)

    assert len(entities_added) == 9  # 9 sensors
    assert all(hasattr(ent, "_attr_name") for ent in entities_added)


@pytest.mark.asyncio
async def test_binary_sensor_async_setup_entry():
    """Test binary_sensor platform async_setup_entry."""
    from custom_components.ectocontrol_modbus.entities.binary_sensor import async_setup_entry as binary_setup

    hass = MagicMock(spec=HomeAssistant)
    entry = FakeEntry()
    coordinator = FakeCoordinator()

    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "coordinator": coordinator,
            }
        }
    }

    entities_added = []

    def add_entities(entities):
        entities_added.extend(entities)

    await binary_setup(hass, entry, add_entities)

    assert len(entities_added) == 3  # 3 binary sensors
    assert all(hasattr(ent, "_attr_name") for ent in entities_added)


@pytest.mark.asyncio
async def test_number_async_setup_entry():
    """Test number platform async_setup_entry."""
    from custom_components.ectocontrol_modbus.entities.number import async_setup_entry as number_setup

    hass = MagicMock(spec=HomeAssistant)
    entry = FakeEntry()
    coordinator = FakeCoordinator()

    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "coordinator": coordinator,
            }
        }
    }

    entities_added = []

    def add_entities(entities):
        entities_added.extend(entities)

    await number_setup(hass, entry, add_entities)

    assert len(entities_added) == 5  # CH Setpoint, CH Min, CH Max, DHW Setpoint, Max Modulation
    assert hasattr(entities_added[0], "async_set_native_value")


@pytest.mark.asyncio
async def test_switch_async_setup_entry():
    """Test switch platform async_setup_entry."""
    from custom_components.ectocontrol_modbus.entities.switch import async_setup_entry as switch_setup

    hass = MagicMock(spec=HomeAssistant)
    entry = FakeEntry()
    coordinator = FakeCoordinator()

    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "coordinator": coordinator,
            }
        }
    }

    entities_added = []

    def add_entities(entities):
        entities_added.extend(entities)

    await switch_setup(hass, entry, add_entities)

    assert len(entities_added) == 2  # Heating Enable, DHW Enable
    assert all(hasattr(ent, "async_turn_on") for ent in entities_added)
