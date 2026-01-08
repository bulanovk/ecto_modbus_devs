# Design & Architecture Guide

## Project Overview

**Ectocontrol Modbus Adapter v2** is a Home Assistant custom integration that exposes gas boiler status and controls via RS-485 Modbus RTU protocol.

- **Target**: Home Assistant 2025.12+
- **Python**: 3.13+
- **Protocol**: Modbus RTU (19200 baud, no parity)
- **Hardware**: Ectocontrol Modbus Adapter v2 connected to boiler via RS-485

---

## Layered Architecture

The integration uses a **3-layer architecture** for clean separation of concerns:

### Layer 1: Hardware Communication — `ModbusProtocol`

**File**: `modbus_protocol.py`

Thin async wrapper around `modbus-tk` RTU client:
- **Responsibility**: Serial port I/O, frame construction, error translation
- **API**: `connect()`, `disconnect()`, `read_registers()`, `read_input_registers()`, `write_registers()`, `write_register()`
- **Error handling**: Returns `None` on timeout/Modbus error; never raises exceptions
- **Concurrency**: Single async lock to serialize operations on half-duplex RS-485
- **Execution model**: Wraps sync `modbus-tk` calls in `asyncio.run_in_executor()` to avoid blocking event loop

### Layer 2: Device Abstraction — `BoilerGateway`

**File**: `boiler_gateway.py`

High-level boiler state adapter:
- **Responsibility**: Register mapping, scaling, unit conversion, device logic
- **API**:
  - **Read helpers** (return from cache, never block): `get_ch_temperature()`, `get_pressure()`, `get_burner_on()`, etc.
  - **Write helpers** (async): `set_ch_setpoint()`, `set_circuit_enable_bit()`, `reboot_adapter()`, etc.
- **Cache**: Populated by `DataUpdateCoordinator`, not by `BoilerGateway` directly
- **Data flow**: Entities → Gateway getters → Cache (populated by Coordinator)
- **Scaling rules**: Apply all ÷10, ÷256, bitfield extraction here; entities use raw values

**Example getter**:
```python
def get_ch_temperature(self) -> Optional[float]:
    raw = self._get_reg(REGISTER_CH_TEMP)
    if raw is None or raw == 0x7FFF:
        return None
    if raw >= 0x8000:
        raw = raw - 0x10000  # Signed interpretation
    return raw / 10.0
```

### Layer 3: Home Assistant Integration — Coordinator & Entities

**Files**: `coordinator.py`, `entities/*.py`

- **Coordinator** (`BoilerDataUpdateCoordinator`):
  - Periodically reads all registers (0x0010..0x0026) in a single batch
  - Updates `gateway.cache` with results
  - Tracks update success/failure; marks device unavailable after 3 consecutive failures
  - Polling interval: 15 seconds (configurable in `const.py`)

- **Entities** (Sensor, Switch, Number, BinarySensor, Climate, Button):
  - Read-only access to gateway cache via gateway getters
  - Write operations call gateway async helpers then refresh coordinator
  - All entities extend `CoordinatorEntity` for automatic availability tracking
  - All entities have unique ID in format `ectocontrol_{slave_id}_{feature}`

**Example entity flow**:
```python
class CHTemperatureSensor(CoordinatorEntity, SensorEntity):
    @property
    def native_value(self):
        return self.coordinator.gateway.get_ch_temperature()  # Read from cache via gateway
    
    @property
    def available(self):
        return self.coordinator.last_update_success  # Coordinator tracks availability
```

---

## Data Flow Diagram

```
┌─────────────────────────────┐
│   Home Assistant Entities   │
│  (Sensor, Switch, Climate)  │
└────────────┬────────────────┘
             │ (read via gateway getters)
             │ (write via gateway helpers)
             │
┌────────────▼────────────────┐
│   DataUpdateCoordinator     │
│  (polls every 15s, caches)  │
└────────────┬────────────────┘
             │ (updates gateway.cache)
             │
┌────────────▼────────────────┐
│   BoilerGateway             │
│  (register → value scaling) │
└────────────┬────────────────┘
             │ (reads from cache)
             │ (writes via protocol)
             │
┌────────────▼────────────────┐
│   ModbusProtocol            │
│  (RTU frame I/O)            │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│   Serial Port (19200, RTU)  │
│   ↔ Boiler via RS-485       │
└─────────────────────────────┘
```

---

## Register Mapping

All Modbus registers are 16-bit unless otherwise noted.

### Status & Configuration (Read-Only)

| Address | Name | Type | Scale | Invalid | Purpose |
|---------|------|------|-------|---------|---------|
| 0x0010 | Status | u16 | 1 | — | Adapter type (bits 0-2), comm OK (bit 3), reboot code (MSB) |
| 0x0011 | Version | u16 | 1 | 0xFFFF | HW (MSB), SW (LSB) |
| 0x0018 | CH Temp | i16 | ÷10 | 0x7FFF | Heating circuit water temperature (°C) |
| 0x0019 | DHW Temp | u16 | ÷10 | 0x7FFF | Domestic hot water temperature (°C) |
| 0x001A | Pressure | u8 (MSB) | ÷10 | 0xFF | System pressure (bar) |
| 0x001B | Flow | u8 (MSB) | ÷10 | 0xFF | DHW flow rate (L/min) |
| 0x001C | Modulation | u8 (MSB) | 1 | 0xFF | Burner modulation level (%) |
| 0x001D | States | u8 (LSB) | 1 | — | Bit0=burner, Bit1=heating, Bit2=DHW |
| 0x001E | Main Error | u16 | 1 | 0xFFFF | Error code from boiler |
| 0x001F | Add Error | u16 | 1 | 0xFFFF | Additional error details |
| 0x0020 | Outdoor Temp | i8 (MSB) | 1 | 0x7F | Outside temperature (°C) |
| 0x0026 | CH Setpoint Active | i16 | ÷256 | 0x7FFF | Active CH setpoint (1/256 °C precision) |

### Control Registers (Read/Write)

| Address | Name | Type | Range | Purpose |
|---------|------|------|-------|---------|
| 0x0031 | CH Setpoint | i16 | 0..1000 | CH target temperature (×10, so raw=450 → 45°C) |
| 0x0032 | Emergency CH | i16 | 0..1000 | Emergency CH setpoint |
| 0x0033 | CH Min Limit | u8 | 0..100 | CH minimum allowed temperature |
| 0x0034 | CH Max Limit | u8 | 0..100 | CH maximum allowed temperature |
| 0x0035 | DHW Min Limit | u8 | 0..100 | DHW minimum allowed temperature |
| 0x0036 | DHW Max Limit | u8 | 0..100 | DHW maximum allowed temperature |
| 0x0037 | DHW Setpoint | u8 | 0..100 | DHW target temperature (°C) |
| 0x0038 | Max Modulation | u8 | 0..100 | Maximum burner modulation level (%) |
| 0x0039 | Circuit Enable | u16 | — | Bit0=heating enable, Bit1=DHW enable |
| 0x0080 | Command | u16 | — | 2=reboot adapter, 3=reset errors |

---

## Configuration Flow

User interaction when setting up the integration:

```
1. User adds integration (Settings → Devices & Services → +)
2. ConfigFlow Step 1: Select serial port (e.g., /dev/ttyUSB0, COM3)
3. ConfigFlow Step 2: Enter Modbus slave ID (1–32)
4. ConfigFlow Step 3: Provide friendly name (e.g., "Kitchen Boiler")
5. ConfigFlow validates:
   - Port exists
   - Slave ID unique for this port
   - Connection test: read register 0x0010 successfully
6. Entry created; async_setup_entry called
7. Entities created and polling begins
```

---

## Error Handling

### Protocol Errors

When `ModbusProtocol` encounters an error (timeout, CRC, Modbus exception):
- Returns `None` (for reads) or `False` (for writes)
- Logs error at `ERROR` level
- Does NOT raise exception

### Gateway Errors

When `BoilerGateway` encounters invalid/unsupported data:
- Returns `None` for sensors (entity shows unavailable)
- Checks for invalid markers: `0x7FFF` (16-bit), `0xFF` (8-bit), `0x7F` (8-bit signed)
- Does NOT raise exception

### Coordinator Errors

When polling fails:
- Raises `UpdateFailed` exception (caught by Home Assistant)
- Coordinator tracks failure count; device unavailable after 3 consecutive failures
- Automatic retry with exponential backoff

### Entity Availability

Entities show `unavailable` state when:
- `coordinator.last_update_success` is `False`
- Sensor getter returns `None` (invalid marker)

---

## Concurrency & Threading

- **Executor**: All `modbus-tk` calls run in executor to avoid blocking HA event loop
- **Locking**: `ModbusProtocol._lock` ensures serial operations don't interleave (RS-485 is half-duplex)
- **Async/Await**: All public APIs use async/await; no synchronous blocking calls
- **Timeout**: 2–3 seconds for individual Modbus operations

---

## Testing Strategy

### Unit Tests

- **`test_modbus_protocol.py`**: Connection, read/write, error handling
- **`test_boiler_gateway.py`**: Scaling, bitfield extraction, cache logic
- **`test_coordinator.py`**: Polling, cache updates, failure tracking
- **`test_config_flow.py`**: Port/slave validation, duplicate detection
- **`test_entities*.py`**: Entity state, properties, write actions

### Integration Tests

- **`test_integration_modbus.py`**: Full setup with mocked RtuMaster
- Verify coordinator polling cycle
- Verify entities receive updates

### Test Patterns

Use `FakeGateway` and `DummyCoordinator` (not MagicMock) for critical logic isolation:

```python
class FakeGateway:
    def get_ch_temperature(self):
        return 21.5
    
    async def set_ch_setpoint(self, raw):
        self.last_set_raw = raw
        return True

# In test:
gateway = FakeGateway()
coordinator = DummyCoordinator(gateway)
entity = BoilerSensor(coordinator)
assert entity.native_value == 21.5
```

---

## Performance Considerations

- **Polling interval**: 15 seconds (covers most user scenarios; configurable)
- **Batch reads**: All sensors read in single multi-register command (0x0010..0x0026 = 23 registers)
- **Lock overhead**: Minimal; typical Modbus round-trip is 100–500 ms
- **Memory**: Cache holds 23 × 2 bytes = 46 bytes per boiler instance
- **Entity updates**: Debounced by coordinator (only on value change or poll cycle)

---

## Future Extensions

- **Auto-discovery**: Scan slave IDs 1–32 to find boilers automatically
- **Multi-register optimization**: Batch multiple setpoint writes into single command
- **Thermostat modes**: HEAT_ONLY, DHW_ONLY, HEAT+DHW
- **Diagnostics enhancements**: Historical error log, burner statistics
- **MQTT bridge**: Publish boiler state to MQTT topics
- **Advanced scheduling**: Time-based setpoint profiles

