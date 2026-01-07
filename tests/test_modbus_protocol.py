import asyncio
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ectocontrol_modbus.modbus_protocol import ModbusProtocol


@pytest.mark.asyncio
async def test_connect_and_disconnect(monkeypatch):
    mock_master = MagicMock()
    mock_master.open = MagicMock()
    mock_master.close = MagicMock()

    async def fake_connect(self):
        return True

    # Patch _connect_sync to return our mock master
    with patch.object(ModbusProtocol, "_connect_sync", return_value=mock_master):
        protocol = ModbusProtocol("/dev/ttyUSB0")
        ok = await protocol.connect()
        assert ok
        assert protocol.is_connected
        await protocol.disconnect()
        assert not protocol.is_connected


@pytest.mark.asyncio
async def test_read_registers_returns_list(monkeypatch):
    protocol = ModbusProtocol("/dev/ttyUSB0")
    mock_master = MagicMock()
    # execute should return a sequence of ints
    mock_master.execute = MagicMock(return_value=(291,))
    protocol.client = mock_master

    res = await protocol.read_registers(1, 0x0018, 1)
    assert res == [291]
