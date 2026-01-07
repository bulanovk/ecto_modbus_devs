import pytest

import importlib

cf = importlib.import_module("custom_components.ectocontrol_modbus.config_flow")
const = importlib.import_module("custom_components.ectocontrol_modbus.const")


class DummyPort:
    def __init__(self, device):
        self.device = device


class DummyEntry:
    def __init__(self, data):
        self.data = data


class DummyConfigEntries:
    def __init__(self, entries=None):
        self._entries = entries or []

    def async_entries(self, domain):
        return self._entries


class DummyHass:
    def __init__(self, entries=None):
        self.config_entries = DummyConfigEntries(entries)


class FakeProtocolOK:
    def __init__(self, port):
        self.port = port

    async def connect(self):
        return True

    async def read_registers(self, slave, addr, count, timeout=None):
        return [0]

    async def disconnect(self):
        return None


class FakeProtocolFailConnect(FakeProtocolOK):
    async def connect(self):
        return False


class FakeProtocolNoResponse(FakeProtocolOK):
    async def read_registers(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_config_flow_success(monkeypatch):
    monkeypatch.setattr(cf.serial.tools.list_ports, "comports", lambda: [DummyPort("/dev/ttyUSB0")])
    monkeypatch.setattr(cf, "ModbusProtocol", FakeProtocolOK)

    flow = cf.EctocontrolConfigFlow()
    flow.hass = DummyHass()

    user_input = {const.CONF_PORT: "/dev/ttyUSB0", const.CONF_SLAVE_ID: 1, const.CONF_NAME: "Boiler"}
    result = await flow.async_step_user(user_input)

    assert result["type"] == "create_entry"
    assert result["data"][const.CONF_PORT] == "/dev/ttyUSB0"


@pytest.mark.asyncio
async def test_config_flow_invalid_slave(monkeypatch):
    monkeypatch.setattr(cf.serial.tools.list_ports, "comports", lambda: [DummyPort("/dev/ttyUSB0")])
    flow = cf.EctocontrolConfigFlow()
    flow.hass = DummyHass()

    user_input = {const.CONF_PORT: "/dev/ttyUSB0", const.CONF_SLAVE_ID: 0}
    result = await flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert "invalid_slave" in result.get("errors", {}).values()


@pytest.mark.asyncio
async def test_config_flow_duplicate_detection(monkeypatch):
    monkeypatch.setattr(cf.serial.tools.list_ports, "comports", lambda: [DummyPort("/dev/ttyUSB0")])
    monkeypatch.setattr(cf, "ModbusProtocol", FakeProtocolOK)

    existing = DummyEntry({const.CONF_PORT: "/dev/ttyUSB0", const.CONF_SLAVE_ID: 2})
    flow = cf.EctocontrolConfigFlow()
    flow.hass = DummyHass(entries=[existing])

    user_input = {const.CONF_PORT: "/dev/ttyUSB0", const.CONF_SLAVE_ID: 2}
    result = await flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert "already_configured" in result.get("errors", {}).values()


@pytest.mark.asyncio
async def test_config_flow_cannot_connect(monkeypatch):
    monkeypatch.setattr(cf.serial.tools.list_ports, "comports", lambda: [DummyPort("/dev/ttyUSB0")])
    monkeypatch.setattr(cf, "ModbusProtocol", FakeProtocolFailConnect)

    flow = cf.EctocontrolConfigFlow()
    flow.hass = DummyHass()

    user_input = {const.CONF_PORT: "/dev/ttyUSB0", const.CONF_SLAVE_ID: 1}
    result = await flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert "cannot_connect" in result.get("errors", {}).values()


@pytest.mark.asyncio
async def test_config_flow_no_response(monkeypatch):
    monkeypatch.setattr(cf.serial.tools.list_ports, "comports", lambda: [DummyPort("/dev/ttyUSB0")])
    monkeypatch.setattr(cf, "ModbusProtocol", FakeProtocolNoResponse)

    flow = cf.EctocontrolConfigFlow()
    flow.hass = DummyHass()

    user_input = {const.CONF_PORT: "/dev/ttyUSB0", const.CONF_SLAVE_ID: 1}
    result = await flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert "cannot_connect" in result.get("errors", {}).values()
