import asyncio
from unittest.mock import MagicMock, patch, call

import pytest
import modbus_tk.defines as cst

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


@pytest.mark.asyncio
async def test_write_register_uses_single_register_function():
    """Test that write_register uses WRITE_SINGLE_REGISTER (0x06) not WRITE_MULTIPLE_REGISTERS (0x10)."""
    protocol = ModbusProtocol("/dev/ttyUSB0")
    mock_master = MagicMock()
    mock_master.execute = MagicMock()
    protocol.client = mock_master

    # Write a single register
    result = await protocol.write_register(1, 0x0031, 220)

    # Verify the write succeeded
    assert result is True

    # Verify execute was called with WRITE_SINGLE_REGISTER (0x06)
    mock_master.execute.assert_called_once()
    args = mock_master.execute.call_args[0]
    assert args[0] == 1  # slave_id
    assert args[1] == cst.WRITE_SINGLE_REGISTER  # function code 0x06
    assert args[2] == 0x0031  # register address
    assert args[3] == 220  # value to write
