# Copilot Instructions for Ectocontrol Modbus Adapter v2

This document provides guidance for GitHub Copilot when working on this Home Assistant HACS integration project.

## Project Overview

**Ectocontrol Modbus Adapter v2** is a Home Assistant custom component that communicates with gas boilers (Ectocontrol) via RS-485 Modbus RTU protocol. It exposes boiler sensors, controls, and diagnostics as Home Assistant entities.

**Key Technologies:**
- Python 3.10+
- Home Assistant Core (2024.1+)
- `modbus-tk>=1.1.5` (Modbus RTU communication)
- `pyserial>=3.5` (Serial port I/O)
- `pytest>=9.0.2` + `pytest-asyncio>=1.3.0` (testing)

---

## Architecture & Design Principles

### 1. Layered Architecture

The codebase follows a **3-layer architecture** with clear separation of concerns:

```
┌─────────────────────────────────────┐
│  Home Assistant Entities             │
│  (sensor, switch, number, climate)  │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│  DataUpdateCoordinator               │
│  (polling, caching, availability)   │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│  BoilerGateway                       │
│  (register mapping, scaling, logic) │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│  ModbusProtocol                      │
│  (async RTU communication)           │
└─────────────────────────────────────┘
```

**Rules:**
- Entities should **never directly access** `ModbusProtocol`. Always go through `BoilerGateway`.
- `BoilerGateway` reads from cache populated by `DataUpdateCoordinator`, never directly reads registers.
- All writes go through `BoilerGateway` async helpers (e.g., `set_ch_setpoint()`, `set_circuit_enable_bit()`).
- Errors in lower layers should return `None` or `False` rather than raising exceptions.

### 2. Modbus Register Mapping

**Key Addresses** (all 16-bit registers unless noted):

```
0x0010  Status & Adapter Type (REGISTER_STATUS)
0x0011  HW/SW Version
0x0012-0x0013  Uptime (high/low words)
0x0018  CH Temperature (i16, ÷10 °C)
0x0019  DHW Temperature (u16, ÷10 °C)
0x001A  Pressure (u8 MSB, ÷10 bar)
0x001B  Flow Rate (u8 MSB, ÷10 L/min)
0x001C  Modulation Level (u8 MSB, %)
0x001D  States: burner/heating/DHW (bitfield)
0x001E  Main Error Code (u16)
0x001F  Additional Error Code (u16)
0x0020  Outdoor Temperature (i8 MSB, °C)
0x0026  CH Setpoint Active (i16, 1/256 °C)
0x0031  CH Setpoint (i16, ÷10 °C)
0x0032  Emergency CH Setpoint
0x0033  CH Min Limit (u8)
0x0034  CH Max Limit (u8)
0x0035  DHW Min Limit (u8)
0x0036  DHW Max Limit (u8)
0x0037  DHW Setpoint (u8, °C)
0x0038  Max Modulation (u8, %)
0x0039  Circuit Enable Flags (bitfield: bit0=heating, bit1=dhw)
0x0080  Command Register (2=reboot, 3=reset errors)
0x0081  Command Result Register
```

**Invalid/Unsupported Markers:**
- `0x7FFF` (16-bit signed): No sensor or error
- `0xFF` (8-bit unsigned): Unsupported/unavailable
- `0x7F` (8-bit signed): Invalid

When reading a register with an invalid marker, **return `None`** so Home Assistant shows the entity as unavailable.

### 3. Scaling & Unit Conversion

Apply scaling in `BoilerGateway` getters, not in entity code:

```python
# Temperature: divide by 10
raw = 291  # from register
celsius = raw / 10.0  # 29.1°C

# Modulation: direct percentage
percent = msb  # 75 = 75%

# Pressure: MSB only, divide by 10
msb = (raw >> 8) & 0xFF  # extract MSB
bar = msb / 10.0  # 12 (0x0C) = 1.2 bar

# Bitfield: extract bits
lsb = raw & 0xFF
burner_on = bool(lsb & 0x01)  # bit 0
heating_enabled = bool((lsb >> 1) & 0x01)  # bit 1
```

### 4. Async Patterns

**All blocking operations (serial I/O, Modbus reads/writes) must use `asyncio`:**

```python
# ✅ CORRECT: Use run_in_executor for sync modbus-tk calls
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, self.client.read_holding_registers, slave, addr, count)

# ❌ WRONG: Never block the event loop directly
result = self.client.read_holding_registers(slave, addr, count)  # blocks!
```

**Lock pattern for concurrent access:**

```python
async with self._lock:
    # Serialize modbus operations to avoid conflicts on half-duplex RS-485
    result = await loop.run_in_executor(None, ...)
```

### 5. Error Handling Strategy

**Protocol/Modbus errors return `None` or `False`:**

```python
async def read_registers(self, slave_id, start_addr, count, timeout=None):
    # On timeout, ModbusError, or any exception → return None
    try:
        ...
    except modbus.ModbusError:
        _LOGGER.error("...")
        return None  # Entity will show unavailable
```

**Coordinator marks device unavailable after 3 consecutive failures:**

```python
class BoilerDataUpdateCoordinator(DataUpdateCoordinator):
    async def _async_update_data(self):
        regs = await self.gateway.protocol.read_registers(...)
        if regs is None:
            raise UpdateFailed("No response")
        # Coordinator automatically tracks this; device → unavailable if threshold hit
```

---

## Coding Standards

### File Organization

1. **`const.py`** — All register addresses, domain, config keys, polling intervals
2. **`modbus_protocol.py`** — Async wrapper around modbus-tk, connection lifecycle
3. **`boiler_gateway.py`** — Register mapping, getters (read-only, cached), write helpers
4. **`coordinator.py`** — `DataUpdateCoordinator` subclass, polling logic
5. **`config_flow.py`** — Port selection, slave ID validation, connection test
6. **`__init__.py`** — Entry setup/unload, platform forwarding, services
7. **`diagnostics.py`** — Diagnostics export hook
8. **`entities/*.py`** — Sensor, switch, number, binary_sensor, climate, button entities

### Python Style

- Use **type hints** on all function signatures
- **Async functions** for I/O, state updates, or coordinator calls
- **Private methods** prefixed with `_` (e.g., `_read_register_cached`)
- **Logging**: Use module-level `_LOGGER = logging.getLogger(__name__)`
- **Docstrings**: One-liner for simple methods; full docstring for complex logic

### Imports

```python
from __future__ import annotations

from typing import Optional, List, Dict
import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, REGISTER_CH_TEMP
```

### Entity Unique IDs

All entities **must** have a unique ID in format: `{DOMAIN}_{slave_id}_{feature}`

```python
@property
def unique_id(self) -> str:
    return f"ectocontrol_{self.coordinator.gateway.slave_id}_ch_temperature"
```

This ensures entities persist across restarts and renames.

---

## Testing Conventions

### Test File Structure

- **`test_modbus_protocol.py`** — Connection, read/write, timeout, error handling
- **`test_boiler_gateway.py`** — Register scaling, getters, bitfield logic
- **`test_coordinator*.py`** — Polling, caching, refresh behavior
- **`test_config_flow.py`** — Port validation, slave ID uniqueness, connection test
- **`test_entities*.py`** — Entity state, properties, write actions
- **`test_init*.py`** — Setup/unload, service registration
- **`test_integration*.py`** — Full flow with mocked Modbus slave

### Mock/Fake Objects

Use simple `Fake*` classes for testing (no MagicMock for critical objects):

```python
class FakeGateway:
    def __init__(self):
        self.slave_id = 1
        self.cache = {}
    
    def get_ch_temperature(self):
        return 21.5  # Fixed return for consistent testing
    
    async def set_ch_setpoint(self, raw):
        self.last_set_raw = raw
        return True

class DummyCoordinator:
    def __init__(self, gateway):
        self.gateway = gateway
    
    async def async_request_refresh(self):
        self.refreshed = True
```

### Async Test Marker

```python
@pytest.mark.asyncio
async def test_my_async_function():
    result = await my_function()
    assert result == expected
```

### Running Tests

```bash
# All tests
pytest -q

# Specific test file
pytest tests/test_entities_climate.py -v

# With coverage
pytest --cov=custom_components --cov-report=html
```

---

## Adding New Features

### Adding a New Sensor

1. **Add register constant** in `const.py`:
   ```python
   REGISTER_NEW_SENSOR = 0x00XX
   ```

2. **Add gateway getter** in `boiler_gateway.py`:
   ```python
   def get_new_sensor(self) -> Optional[float]:
       raw = self._get_reg(REGISTER_NEW_SENSOR)
       if raw is None or raw == 0x7FFF:
           return None
       return raw / 10.0  # Apply scaling
   ```

3. **Add entity** in `entities/sensor.py`:
   ```python
   class NewSensor(CoordinatorEntity, SensorEntity):
       @property
       def unique_id(self) -> str:
           return f"{DOMAIN}_{self.coordinator.gateway.slave_id}_new_sensor"
       
       @property
       def native_value(self):
           return self.coordinator.gateway.get_new_sensor()
   ```

4. **Register in platform setup**:
   ```python
   async def async_setup_entry(hass, entry, async_add_entities):
       ...
       async_add_entities([NewSensor(coordinator)])
   ```

5. **Add tests** in `tests/test_entities.py` or new file:
   ```python
   def test_new_sensor_value():
       gw = FakeGateway()
       gw.cache[REGISTER_NEW_SENSOR] = 245
       coord = DummyCoordinator(gw)
       entity = NewSensor(coord)
       assert entity.native_value == 24.5
   ```

### Adding a New Control Switch

1. **Add write helper** in `boiler_gateway.py`:
   ```python
   async def set_new_control(self, enabled: bool) -> bool:
       return await self.set_circuit_enable_bit(2, enabled)  # bit 2
   ```

2. **Add entity** in `entities/switch.py`:
   ```python
   class NewControlSwitch(CoordinatorEntity, SwitchEntity):
       async def async_turn_on(self, **kwargs) -> None:
           await self.coordinator.gateway.set_new_control(True)
           await self.coordinator.async_request_refresh()
   ```

3. **Test** the action and coordinator refresh.

### Adding a New Number Entity

1. **Add register constant** and/or use existing setter in `boiler_gateway.py`
2. **Create NumberEntity subclass**:
   ```python
   class NewSetpointNumber(CoordinatorEntity, NumberEntity):
       @property
       def native_value(self):
           return self.coordinator.gateway.get_new_setpoint()
       
       async def async_set_native_value(self, value: float) -> None:
           raw = int(round(value * SCALE_FACTOR))
           await self.coordinator.gateway.set_new_setpoint(raw)
           await self.coordinator.async_request_refresh()
   ```

---

## Common Patterns & Pitfalls

### ✅ DO

- Always add a `unique_id` property to entities
- Call `async_request_refresh()` after write operations
- Check for invalid markers (`0x7FFF`, `0xFF`) and return `None`
- Use `_LOGGER.error()` for errors, `_LOGGER.debug()` for verbose logs
- Test with `FakeGateway` and `DummyCoordinator` to isolate entity logic
- Wrap modbus-tk calls in `run_in_executor()` to avoid blocking

### ❌ DON'T

- Directly read from `self.coordinator.data` in entity; use `BoilerGateway` getters
- Raise exceptions in `ModbusProtocol` or `BoilerGateway`; return `None`/`False`
- Mix sync and async code without proper `run_in_executor()`
- Hardcode register addresses in entity files; use constants
- Skip tests for new functionality
- Modify registers without going through `BoilerGateway` write helpers

### Register Bitfield Manipulation

```python
# Read, modify, write pattern for 0x0039 (Circuit Enable flags)
current = await self.protocol.read_registers(slave_id, 0x0039, 1)
if current:
    current = current[0]
else:
    current = 0

# Set bit 1 (DHW enable)
newval = current | (1 << 1)  # Set bit
# newval = current & ~(1 << 1)  # Clear bit
# newval = current ^ (1 << 1)  # Toggle bit

await self.protocol.write_register(slave_id, 0x0039, newval)
```

---

## Debugging Tips

1. **Enable debug logging** in Home Assistant configuration:
   ```yaml
   logger:
     logs:
       custom_components.ectocontrol_modbus: debug
   ```

2. **Check Modbus traffic** by adding log statements in `ModbusProtocol`:
   ```python
   _LOGGER.debug(f"Read {count} regs from addr 0x{start_addr:04X}, slave {slave_id}")
   _LOGGER.debug(f"Result: {result}")
   ```

3. **Verify register values** in HA diagnostics or via DevTools → States

4. **Run tests with verbose output**:
   ```bash
   pytest tests/test_modbus_protocol.py -vv
   ```

---

## Resources

- **IMPLEMENTATION_PLAN.md** — Detailed architectural specification
- **PR_CHECKLIST.md** — Outstanding tasks and estimates
- **manifest.json** — Integration metadata, dependencies
- **requirements.txt** — Python package versions
- **Home Assistant Developer Docs** — https://developers.home-assistant.io/
- **modbus-tk Docs** — https://github.com/ljnsn/modbus-tk

---

## Integration Checklist for New Features

- [ ] Register address added to `const.py`
- [ ] `BoilerGateway` getter or write helper implemented
- [ ] Entity class created in appropriate `entities/*.py` file
- [ ] Entity registered in `async_setup_entry()`
- [ ] Unique ID format: `ectocontrol_{slave_id}_{feature}`
- [ ] Unit/scaling applied correctly
- [ ] Invalid markers (`0x7FFF`, `0xFF`) handled → return `None`
- [ ] Tests written (fake gateway, coordinator, entity state/action)
- [ ] Tests pass locally (`pytest -q`)
- [ ] Docstrings and type hints added
- [ ] PR references `PR_CHECKLIST.md` tasks

