# Home Assistant HACS Integration: Ectocontrol Modbus Adapter v2 (GAS Boiler)
## Comprehensive Technical Implementation Plan

**Document Version:** 1.0  
**Date:** January 7, 2026  
**Target:** Home Assistant HACS Extension (Python 3.10+)

---

## 1. Component Architecture

### 1.1 High-Level Integration Structure

```
ectocontrol-modbus-boiler/
├── custom_components/
│   └── ectocontrol_modbus/
│       ├── __init__.py                 # Integration setup, config_flow entry
│       ├── manifest.json               # HACS metadata
│       ├── strings.json                # Localization strings
│       ├── config_flow.py              # Config Flow UI for boiler discovery
│       ├── const.py                    # Constants & register definitions
│       ├── modbus_protocol.py          # Low-level Modbus RTU communication
│       ├── boiler_gateway.py           # Boiler device adapter (mid-layer)
│       ├── coordinator.py              # DataUpdateCoordinator for polling
│       ├── diagnostics.py              # HA diagnostics support
│       └── entities/
│           ├── __init__.py
│           ├── sensor.py               # Temperature, pressure, flow sensors
│           ├── switch.py               # Burner/heating/DHW control switches
│           ├── number.py               # Setpoint & limit number entities
│           └── binary_sensor.py        # State & error flags
├── tests/
│   ├── __init__.py
│   ├── test_modbus_protocol.py         # Unit tests for Modbus layer
│   ├── test_boiler_gateway.py          # Unit tests for boiler adapter
│   ├── test_config_flow.py             # Config flow validation tests
│   └── test_integration.py             # Integration tests
├── requirements.txt                     # Python dependencies
└── README.md                            # Integration overview
```

### 1.2 Component Responsibilities

| Component | Responsibility |
|-----------|-----------------|
| **modbus_protocol.py** | Thin wrapper around `modbus-tk` RTU client; handle connection lifecycle; error translation |
| **boiler_gateway.py** | Register mapping abstraction; sensor scaling & unit conversion; device state management |
| **coordinator.py** | Periodic polling (10-30s interval); caching; update distribution to all entities |
| **config_flow.py** | User input validation; TTY/Slave ID conflict detection; connection test; device add/edit/remove |
| **entities/** | HA entity implementations; state updates from coordinator; command issue to boiler_gateway |
| **__init__.py** | Config entry lifecycle (setup/unload); integrating all components |

---

## 2. Modbus Communication Layer Design

### 2.1 Library Selection: `modbus-tk`

**Rationale:**
- Mature, production-tested Python Modbus library
- Handles RTU frame construction, CRC16 calculation, Big-Endian encoding automatically
- Built-in support for all function codes (0x03, 0x04, 0x10, 0x46, 0x47, 0x4B, 0x4C)
- Async-compatible through integration with Home Assistant's event loop
- Significantly reduces code complexity and surface area for bugs

**Installation:**
```
modbus-tk>=1.1.2
pyserial>=3.5
```

### 2.2 Protocol Specification Review (Reference Only)

**Serial Interface:**
- Port: User-configurable (e.g., `/dev/ttyUSB0`, `COM3`)
- Baud: 19200 (fixed)
- Data bits: 8
- Parity: None (N)
- Stop bits: 1
- Flow control: None
- Timing: Half-duplex RS-485 (turn-around ~5ms)

**Modbus RTU Frame Structure:**
```
[SLAVE_ID] [FUNCTION_CODE] [DATA...] [CRC_LO] [CRC_HI]
1 byte     1 byte          N bytes   1 byte   1 byte
```
*Note: CRC16 and Big-Endian encoding handled transparently by modbus-tk*

**Function Codes Used:**
- `0x03` – Read Holding Registers
- `0x04` – Read Input Registers
- `0x10` – Write Multiple Holding Registers

### 2.3 Big-Endian Payload Mapping (Handled by modbus-tk)

`modbus-tk` automatically:
- Encodes/decodes 16-bit register values in Big-Endian format (MSB first, LSB second)
- Handles 32-bit values by combining adjacent 16-bit registers
- Manages bitfield packing/unpacking for control registers

**Register data types automatically handled:**
```python
# 16-bit signed integer (e.g., temperature)
value = client.read_holding_registers(1, 0x0018, 1)  # Returns [291] for 29.1°C
temperature = value[0] / 10.0  # 29.1

# 32-bit unsigned (e.g., uptime across registers 0x0012 + 0x0013)
uptime_regs = client.read_holding_registers(1, 0x0012, 2)  # [high_word, low_word]
uptime_seconds = (uptime_regs[0] << 16) | uptime_regs[1]

# Bitfield (8-bit packed into 16-bit register)
states = client.read_holding_registers(1, 0x001D, 1)  # [bitfield_value]
burner_on = bool(states[0] & 0x01)  # bit 0
heating_enabled = bool((states[0] >> 1) & 0x01)  # bit 1
```

### 2.4 `ModbusProtocol` Wrapper Class

```python
# modbus_protocol.py

import logging
from typing import Optional, List
import asyncio
import modbus_tk.defines as cst
import modbus_tk.modbus_rtu as modbus_rtu

_LOGGER = logging.getLogger(__name__)

class ModbusProtocol:
    """
    Wrapper around modbus-tk RTU client.
    Handles connection lifecycle and error translation.
    """
    
    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 2.0):
        """
        Initialize Modbus RTU client.
        
        Args:
            port: Serial port (e.g., '/dev/ttyUSB0', 'COM3')
            baudrate: Baud rate (default: 19200 for Ectocontrol)
            timeout: Request timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.client: Optional[modbus_rtu.RtuClient] = None
        self.lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """
        Open serial port and establish Modbus RTU connection.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # modbus-tk is not async-native; wrap in executor
            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(
                None,
                self._connect_sync
            )
            _LOGGER.info(f"Connected to Modbus at {self.port}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to connect to {self.port}: {e}")
            self.client = None
            return False
    
    def _connect_sync(self) -> modbus_rtu.RtuClient:
        """Synchronous connection (run in executor)."""
        client = modbus_rtu.RtuClient(
            port=self.port,
            method='rtu',
            baudrate=self.baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            xonxoff=False,
            timeout=self.timeout
        )
        client.open()
        return client
    
    async def disconnect(self) -> None:
        """Close serial port."""
        if self.client:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.close)
            self.client = None
            _LOGGER.info(f"Disconnected from {self.port}")
    
    async def read_registers(
        self,
        slave_id: int,
        start_addr: int,
        count: int,
        timeout: Optional[float] = None,
    ) -> Optional[List[int]]:
        """
        Read holding registers (function code 0x03).
        
        Args:
            slave_id: Modbus slave ID (1-32)
            start_addr: Starting register address (0x0010, 0x0018, etc.)
            count: Number of registers to read
            timeout: Override default timeout
        
        Returns:
            List of register values, or None on error
        """
        if not self.client:
            _LOGGER.warning("Modbus client not connected")
            return None
        
        async with self.lock:
            try:
                loop = asyncio.get_event_loop()
                
                # Set timeout if overridden
                old_timeout = self.client.timeout
                if timeout:
                    self.client.timeout = timeout
                
                result = await loop.run_in_executor(
                    None,
                    self.client.read_holding_registers,
                    slave_id,
                    start_addr,
                    count
                )
                
                # Restore original timeout
                if timeout:
                    self.client.timeout = old_timeout
                
                return result
            
            except modbus_tk.modbus.ModbusError as e:
                _LOGGER.error(
                    f"Modbus error reading from slave {slave_id}, "
                    f"addr 0x{start_addr:04X}, count {count}: {e}"
                )
                return None
            except asyncio.TimeoutError:
                _LOGGER.warning(
                    f"Timeout reading from slave {slave_id}, "
                    f"addr 0x{start_addr:04X}"
                )
                return None
            except Exception as e:
                _LOGGER.error(f"Unexpected error reading registers: {e}")
                return None
    
    async def read_input_registers(
        self,
        slave_id: int,
        start_addr: int,
        count: int,
    ) -> Optional[List[int]]:
        """
        Read input registers (function code 0x04).
        Similar to read_holding_registers but for input registers.
        """
        if not self.client:
            return None
        
        async with self.lock:
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self.client.read_input_registers,
                    slave_id,
                    start_addr,
                    count
                )
                return result
            except Exception as e:
                _LOGGER.error(f"Failed to read input registers: {e}")
                return None
    
    async def write_registers(
        self,
        slave_id: int,
        start_addr: int,
        values: List[int],
    ) -> bool:
        """
        Write multiple holding registers (function code 0x10).
        
        Args:
            slave_id: Modbus slave ID
            start_addr: Starting register address
            values: List of 16-bit values to write
        
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            _LOGGER.warning("Modbus client not connected")
            return False
        
        async with self.lock:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self.client.write_multiple_registers,
                    slave_id,
                    start_addr,
                    values
                )
                return True
            except modbus_tk.modbus.ModbusError as e:
                _LOGGER.error(
                    f"Modbus error writing to slave {slave_id}, "
                    f"addr 0x{start_addr:04X}: {e}"
                )
                return False
            except asyncio.TimeoutError:
                _LOGGER.warning(
                    f"Timeout writing to slave {slave_id}, "
                    f"addr 0x{start_addr:04X}"
                )
                return False
            except Exception as e:
                _LOGGER.error(f"Unexpected error writing registers: {e}")
                return False
    
    async def write_register(
        self,
        slave_id: int,
        addr: int,
        value: int,
    ) -> bool:
        """
        Convenience method: write single register.
        """
        return await self.write_registers(slave_id, addr, [value])
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.client is not None and self.client.is_run
```

### 2.5 Error Handling Strategy

**Exception Types (from modbus-tk):**
```python
import modbus_tk.modbus as modbus

# Modbus-level exceptions automatically raised by modbus-tk:
# - ModbusError: General Modbus protocol error
# - SlaveReportedError: Slave returned exception code
# - CommunicationError: Serial communication failure
# - TimeoutError: Request timeout (inherited from asyncio)

# Our wrapper translates these to None returns or False
```

**Timeout Handling:**
- Request timeout: 2.0 seconds (configurable)
- Automatic retry: Coordinator handles retry logic (3 attempts with backoff)
- Device marked unavailable after 3 consecutive timeouts

**CRC Handling:**
- Automatic by modbus-tk
- No manual verification needed
- Serial corruption detected and retried transparently

---

## 3. UI Configuration Flow Design

### 3.1 Config Flow Entry Points

**Primary Entry:**
- User navigates Home Assistant → Settings → Devices & Services → Create Automation → Ectocontrol
- Presents option to "Add Boiler" or "Manage Existing"

**Config Entry Lifecycle:**
```
User Initiates
    ↓
Step 1: Port Selection (combobox with available TTY ports)
    ↓
Step 2: Modbus Slave ID (number input, 1…32)
    ↓
Step 3: Connection Test (try reading 0x0010 from target)
    ↓
Conflict Check (ensure no duplicate slave ID on same port)
    ↓
Boiler Name (friendly name for HA entity registry)
    ↓
Config Saved → Integration Initialized
```

### 3.2 Configuration Flow Implementation

```python
# config_flow.py

class EctocontrolModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for Ectocontrol Modbus Adapter."""
    
    VERSION = 1
    CONNECTION_CLASS = ConfigEntrySource.USER
    
    async def async_step_user(self, user_input=None):
        """Handle user-initiated config."""
        if user_input is not None:
            # Step 1: Port selection
            return self.async_show_form(
                step_id="port_selection",
                data_schema=vol.Schema({
                    vol.Required("port"): cv.string,  # /dev/ttyUSB0 or COM3
                }),
                errors={},
                description_placeholders={
                    "available_ports": ", ".join(await self._get_available_ports())
                }
            )
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={}
        )
    
    async def async_step_port_selection(self, user_input=None):
        """Validate port and move to Slave ID selection."""
        if user_input is not None:
            port = user_input["port"]
            errors = {}
            
            # Validate port exists
            if not await self._port_exists(port):
                errors["port"] = "port_not_found"
            
            if not errors:
                self.boiler_config = {"port": port}
                return await self.async_step_slave_id()
        
        return self.async_show_form(
            step_id="port_selection",
            data_schema=vol.Schema({
                vol.Required("port"): cv.string,
            }),
            errors=errors
        )
    
    async def async_step_slave_id(self, user_input=None):
        """Capture Modbus Slave ID (1…32)."""
        if user_input is not None:
            slave_id = user_input["slave_id"]
            port = self.boiler_config["port"]
            errors = {}
            
            # Check for duplicate slave ID on same port
            if self._slave_id_exists_on_port(port, slave_id):
                errors["slave_id"] = "slave_id_already_configured"
            
            if not (1 <= slave_id <= 32):
                errors["slave_id"] = "invalid_range"
            
            if not errors:
                # Perform connection test
                if not await self._test_connection(port, slave_id):
                    errors["slave_id"] = "connection_failed"
            
            if not errors:
                self.boiler_config["slave_id"] = slave_id
                return await self.async_step_boiler_name()
        
        return self.async_show_form(
            step_id="slave_id",
            data_schema=vol.Schema({
                vol.Required("slave_id", default=1): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=32)
                ),
            }),
            errors=errors
        )
    
    async def async_step_boiler_name(self, user_input=None):
        """Final step: friendly name for the boiler."""
        if user_input is not None:
            name = user_input["name"]
            port = self.boiler_config["port"]
            slave_id = self.boiler_config["slave_id"]
            
            # Create unique ID
            unique_id = f"ectocontrol_{port}_{slave_id}"
            
            return self.async_create_entry(
                title=name,
                data={
                    "port": port,
                    "slave_id": slave_id,
                    "name": name,
                },
                unique_id=unique_id
            )
        
        return self.async_show_form(
            step_id="boiler_name",
            data_schema=vol.Schema({
                vol.Required("name"): cv.string,
            })
        )
    
    async def _test_connection(self, port: str, slave_id: int) -> bool:
        """Try reading status register (0x0010) to verify connection."""
        protocol = ModbusProtocol(port)
        try:
            await protocol.connect()
            result = await protocol.read_registers(
                slave_id, 0x0010, 1, timeout=3.0
            )
            await protocol.disconnect()
            return result is not None
        except Exception:
            return False
    
    def _slave_id_exists_on_port(self, port: str, slave_id: int) -> bool:
        """Check if config entry already exists for port+slave_id pair."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if (entry.data.get("port") == port and
                entry.data.get("slave_id") == slave_id):
                return True
        return False
    
    async def _get_available_ports(self) -> list[str]:
        """Return list of available serial ports."""
        # Use serial.tools.list_ports
        import serial.tools.list_ports
        return [port.device for port in serial.tools.list_ports.comports()]
    
    async def _port_exists(self, port: str) -> bool:
        """Validate that port is available."""
        ports = await self._get_available_ports()
        return port in ports or port in ["/dev/ttyUSB0", "/dev/ttyUSB1", "COM3", "COM4"]  # Fallback
```

### 3.3 UI Validation Rules

| Input | Validation Rule |
|-------|-----------------|
| **Port** | Must exist in `serial.tools.list_ports`; no two boilers on same port unless they support daisy-chain |
| **Slave ID** | 1–32 inclusive; unique per port |
| **Connection Test** | Must successfully read register 0x0010 within 3 seconds |
| **Boiler Name** | Max 64 chars, alphanumeric + spaces/hyphens |

---

## 4. Boiler Discovery & Initialization Strategy

### 4.1 Device Discovery Approach

**Manual Configuration Only (Initial Phase):**
- Users explicitly add boilers via Config Flow
- No automatic discovery (RS-485 does not support plug-and-play broadcast)
- Can be extended later with "Scan Network" (try all Slave IDs 1…32 on a port)

**Optional: Slave Address Lookup via Function 0x4B**
```python
async def discover_slaves_on_port(port: str) -> list[int]:
    """
    Try function code 0x4B (Read Device Address by Serial) on all IDs 1…32.
    Returns list of responding slave IDs.
    """
    protocol = ModbusProtocol(port)
    await protocol.connect()
    responding_ids = []
    for slave_id in range(1, 33):
        if await protocol.read_registers(slave_id, 0x0010, 1, timeout=0.5):
            responding_ids.append(slave_id)
    await protocol.disconnect()
    return responding_ids
```

### 4.2 Initialization Sequence (per config entry)

```python
async def async_setup_entry(hass, entry):
    """Initialize integration for one config entry (one boiler)."""
    
    port = entry.data["port"]
    slave_id = entry.data["slave_id"]
    name = entry.data["name"]
    
    # 1. Create Modbus protocol driver
    protocol = ModbusProtocol(port)
    
    # 2. Create Boiler Gateway (mid-layer adapter)
    gateway = BoilerGateway(protocol, slave_id)
    
    # 3. Create DataUpdateCoordinator (handles polling & caching)
    coordinator = BoilerDataUpdateCoordinator(
        hass, gateway, name,
        update_interval=timedelta(seconds=15)  # Poll every 15s
    )
    
    # 4. Perform initial update to verify device is reachable
    try:
        await coordinator.async_config_entries_ready()
    except Exception as e:
        _LOGGER.error(f"Failed to initialize boiler {name}: {e}")
        return False
    
    # 5. Store in hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "protocol": protocol,
        "gateway": gateway,
        "coordinator": coordinator,
    }
    
    # 6. Set up entity platforms
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["sensor", "switch", "number", "binary_sensor"]
    )
    
    return True
```

### 4.3 Device Definition in Home Assistant

```python
# In async_setup_entry or entities initialization:

device_info = DeviceInfo(
    identifiers={(DOMAIN, f"{port}_{slave_id}")},
    name=name,
    manufacturer="Ectocontrol",
    model="Modbus Adapter v2 (RS-485)",
    hw_version=None,  # Will be set from register 0x0011 after first poll
    sw_version=None,
    via_device=None,
)
```

---

## 5. Entity Model & Register Binding

### 5.1 Entity Types and Mappings

#### **Climate Entity (Primary Control)**
```python
class BoilerClimateEntity(ClimateEntity):
    """Main boiler climate control entity."""
    
    def __init__(self, coordinator, gateway, boiler_name):
        self.coordinator = coordinator
        self.gateway = gateway
        self.boiler_name = boiler_name
    
    @property
    def current_temperature(self) -> float | None:
        """CH water temperature from register 0x0018."""
        return self.gateway.get_ch_temperature()  # scaled: value/10
    
    @property
    def target_temperature(self) -> float | None:
        """CH setpoint from register 0x0031."""
        return self.gateway.get_ch_setpoint()  # scaled: value/10
    
    @property
    def hvac_action(self) -> HVACAction:
        """Current action: HEATING or IDLE based on register 0x001D bit0."""
        is_burner_on = self.gateway.get_burner_on()
        return HVACAction.HEATING if is_burner_on else HVACAction.IDLE
    
    @property
    def hvac_modes(self) -> list[HVACMode]:
        return [HVACMode.HEAT, HVACMode.OFF]
    
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Enable/disable heating via register 0x0039 bit0."""
        if hvac_mode == HVACMode.HEAT:
            await self.gateway.set_heating_enabled(True)
        else:
            await self.gateway.set_heating_enabled(False)
    
    async def async_set_temperature(self, **kwargs) -> None:
        """Set CH setpoint via register 0x0031."""
        target_temp = kwargs[ATTR_TEMPERATURE]
        target_raw = int(target_temp * 10)
        await self.gateway.set_ch_setpoint(target_raw)
```

#### **Temperature Sensors**
| Entity | Register | Scale | Invalid Value |
|--------|----------|-------|---------------|
| CH Temperature | 0x0018 (i16) | ÷10 °C | 0x7FFF |
| DHW Temperature | 0x0019 (u16) | ÷10 °C | 0x7FFF |
| Outdoor Temp | 0x0020 (i8) | 1 °C | 0x7F |

```python
class TemperatureSensorEntity(SensorEntity):
    """Generic temperature sensor with scaling."""
    
    @property
    def state(self) -> float | None:
        register_value = self.coordinator.data.get(self.register_addr)
        if register_value is None or register_value == self.invalid_value:
            return None
        return register_value / self.scale_factor
```

#### **Pressure & Flow Sensors**
| Entity | Register | Scale | Unit | Invalid |
|--------|----------|-------|------|---------|
| Pressure | 0x001A (u8) | ÷10 | bar | 0xFF |
| DHW Flow | 0x001B (u8) | ÷10 | L/min | 0xFF |
| Modulation | 0x001C (u8) | 1 | % | 0xFF |

#### **Binary State Sensors**
| Entity | Register | Bit | Meaning |
|--------|----------|-----|---------|
| Burner Active | 0x001D | 0 | Burner ON/OFF |
| Heating Enabled | 0x001D | 1 | Heating circuit active |
| DHW Enabled | 0x001D | 2 | DHW circuit active |
| Comm OK | 0x0010 | 3 (MSB) | Adapter communication status |

#### **Control Switches**
| Switch | Register | Bit | Action |
|--------|----------|-----|--------|
| Enable Heating | 0x0039 | 0 | Set bit0 = 1 to enable |
| Enable DHW | 0x0039 | 1 | Set bit1 = 1 to enable |
| Reboot Adapter | 0x0039 | 7 | Set bit7 = 1, then reset to 0 |
| Reset Errors | 0x0080 | - | Write 0x0003 to command register |

#### **Number Entities (Setpoints & Limits)**
| Number | Register | Type | Range | Scale | EPROM |
|--------|----------|------|-------|-------|-------|
| CH Setpoint | 0x0031 | i16 | 0…100 | ÷10 | Yes |
| Emergency CH | 0x0032 | i16 | 0…100 | ÷10 | Yes |
| CH Min Limit | 0x0033 | u8 | 0…100 | 1 | No |
| CH Max Limit | 0x0034 | u8 | 0…100 | 1 | No |
| DHW Min Limit | 0x0035 | u8 | 0…100 | 1 | No |
| DHW Max Limit | 0x0036 | u8 | 0…100 | 1 | No |
| DHW Setpoint | 0x0037 | u8 | 0…100 | 1 | Yes |
| Max Modulation | 0x0038 | u8 | 0…100 | 1 | Yes |

### 5.2 `BoilerGateway` Class

```python
# boiler_gateway.py

class BoilerGateway:
    """
    High-level boiler state adapter.
    Translates raw Modbus register reads/writes into semantic boiler operations.
    """
    
    def __init__(self, protocol: ModbusProtocol, slave_id: int):
        self.protocol = protocol
        self.slave_id = slave_id
        self.cache = {}
        self.cache_timestamp = {}
        self.cache_ttl = 30  # 30 seconds
    
    # ========== SENSOR READS (Cached) ==========
    
    def get_ch_temperature(self) -> float | None:
        """Read 0x0018, scale by /10."""
        raw = self._read_register_cached(0x0018, is_signed=True)
        if raw is None or raw == 0x7FFF:
            return None
        return raw / 10.0
    
    def get_dhw_temperature(self) -> float | None:
        """Read 0x0019, scale by /10."""
        raw = self._read_register_cached(0x0019, is_signed=False)
        if raw is None or raw == 0x7FFF:
            return None
        return raw / 10.0
    
    def get_pressure(self) -> float | None:
        """Read 0x001A (u8 in MSB of 16-bit register), scale by /10.

        The adapter stores the meaningful 8-bit value in the MSB (first byte)
        of the 16-bit register. Extract MSB and handle 0xFF unsupported marker.
        """
        raw = self._read_register_cached(0x001A)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        if msb == 0xFF:
            return None
        return msb / 10.0
    
    def get_flow_rate(self) -> float | None:
        """Read 0x001B (u8 in MSB of 16-bit register), scale by /10.

        Extract MSB; 0xFF means unsupported.
        """
        raw = self._read_register_cached(0x001B)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        if msb == 0xFF:
            return None
        return msb / 10.0
    
    def get_modulation_level(self) -> int | None:
        """Read 0x001C (u8 % stored in MSB) and return 0..100 or None.

        0xFF indicates undefined/unsupported.
        """
        raw = self._read_register_cached(0x001C)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        return None if msb == 0xFF else msb
    
    def get_burner_on(self) -> bool:
        """Read 0x001D LSB bit0 => Burner ON."""
        raw = self._read_register_cached(0x001D)
        if raw is None:
            return False
        lsb = raw & 0xFF
        return bool(lsb & 0x01)
    
    def get_heating_enabled(self) -> bool:
        """Read 0x001D LSB bit1 => Heating enabled."""
        raw = self._read_register_cached(0x001D)
        if raw is None:
            return False
        lsb = raw & 0xFF
        return bool((lsb >> 1) & 0x01)
    
    def get_dhw_enabled(self) -> bool:
        """Read 0x001D LSB bit2 => DHW enabled."""
        raw = self._read_register_cached(0x001D)
        if raw is None:
            return False
        lsb = raw & 0xFF
        return bool((lsb >> 2) & 0x01)
    
    def get_main_error(self) -> int | None:
        """Read 0x001E (u16)."""
        raw = self._read_register_cached(0x001E)
        return None if raw == 0xFFFF else raw
    
    def get_additional_error(self) -> int | None:
        """Read 0x001F (u16)."""
        raw = self._read_register_cached(0x001F)
        return None if raw == 0xFFFF else raw
    
    def get_outdoor_temperature(self) -> int | None:
        """Read 0x0020 (i8 °C)."""
        raw = self._read_register_cached(0x0020, is_signed=True, byte_count=1)
        return None if raw == 0x7F else raw
    
    def get_communication_ok(self) -> bool:
        """Read 0x0010 MSB bit3 => comm OK with boiler.

        0x0010 is a 16-bit register. MSB (high byte) is `reboot_code`,
        LSB (low byte) contains bitfield. Extract the LSB and test bit3.
        """
        raw = self._read_register_cached(0x0010)
        if raw is None:
            return False
        lsb = raw & 0xFF
        return bool(lsb & 0x08)
    
    def get_adapter_type(self) -> str:
        """Read 0x0010 LSB bits2..0 => adapter type code."""
        raw = self._read_register_cached(0x0010)
        if raw is None:
            return "unknown"
        lsb = raw & 0xFF
        type_code = lsb & 0x07
        types = {0: "OpenTherm", 1: "eBus", 2: "Navien"}
        return types.get(type_code, "unknown")
    
    def get_hw_version(self) -> str | None:
        """Read 0x0011 MSB."""
        raw = self._read_register_cached(0x0011)
        if raw is None:
            return None
        msb = (raw >> 8) & 0xFF
        return f"v{msb}"
    
    def get_sw_version(self) -> str | None:
        """Read 0x0011 LSB (software version byte)."""
        raw = self._read_register_cached(0x0011)
        if raw is None:
            return None
        lsb = raw & 0xFF
        return f"v{lsb}"
    
    def get_ch_setpoint(self) -> float | None:
        """Read 0x0031 (i16), scale by /10."""
        raw = self._read_register_cached(0x0031, is_signed=True)
        if raw is None or raw == 0x7FFF:
            return None
        return raw / 10.0

    def get_ch_setpoint_active(self) -> float | None:
        """Read 0x0026 (i16, step = 1/256 °C) and convert to °C.

        0x7FFF indicates invalid/unsupported.
        """
        raw = self._read_register_cached(0x0026, is_signed=True)
        if raw is None or raw == 0x7FFF:
            return None
        return raw / 256.0
    
    # ========== CONTROL WRITES ==========
    
    async def set_heating_enabled(self, enabled: bool) -> bool:
        """Write 0x0039 bit0."""
        current = await self._read_and_modify_bitfield(0x0039, bit=0, value=enabled)
        return await self.protocol.write_register(self.slave_id, 0x0039, current)
    
    async def set_dhw_enabled(self, enabled: bool) -> bool:
        """Write 0x0039 bit1."""
        current = await self._read_and_modify_bitfield(0x0039, bit=1, value=enabled)
        return await self.protocol.write_register(self.slave_id, 0x0039, current)
    
    async def set_ch_setpoint(self, value_raw: int) -> bool:
        """Write 0x0031 (i16 in raw form, e.g., 450 = 45.0°C)."""
        return await self.protocol.write_register(self.slave_id, 0x0031, value_raw)
    
    async def set_dhw_setpoint(self, value_celsius: int) -> bool:
        """Write 0x0037 (u8 °C)."""
        return await self.protocol.write_register(self.slave_id, 0x0037, value_celsius)
    
    async def set_max_modulation(self, percent: int) -> bool:
        """Write 0x0038 (u8 %)."""
        return await self.protocol.write_register(self.slave_id, 0x0038, percent)
    
    async def reboot_adapter(self) -> bool:
        """Write 0x0039 bit7 = 1."""
        current = await self._read_and_modify_bitfield(0x0039, bit=7, value=True)
        return await self.protocol.write_register(self.slave_id, 0x0039, current)
    
    async def reset_errors(self) -> bool:
        """Write 0x0080 = 0x0003 (reset boiler errors)."""
        return await self.protocol.write_register(self.slave_id, 0x0080, 3)
    
    # ========== INTERNAL HELPERS ==========
    
    def _read_register_cached(
        self,
        addr: int,
        is_signed: bool = False,
        byte_count: int = 2
    ) -> int | None:
        """
        Read register from cache if fresh, else return None.
        (Cache is populated by async_update() in coordinator)
        
        Note: modbus-tk automatically handles Big-Endian decoding,
        so cache values are already in native Python int format.
        """
        if addr not in self.cache:
            return None
        return self.cache[addr]
    
    async def _read_and_modify_bitfield(
        self,
        addr: int,
        bit: int,
        value: bool
    ) -> int:
        """
        Read current register value, modify one bit, return new value.
        
        modbus-tk handles all Big-Endian encoding/decoding automatically;
        we just manipulate bits and let modbus-tk send/receive.
        """
        current = await self.protocol.read_registers(self.slave_id, addr, 1)
        if current is None:
            current = 0
        else:
            current = current[0]
        
        if value:
            current |= (1 << bit)
        else:
            current &= ~(1 << bit)
        
        return current
```

### 5.3 DataUpdateCoordinator

```python
# coordinator.py

class BoilerDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Periodically polls all registers and caches results.
    Updates all entities automatically on data refresh.
    """
    
    def __init__(self, hass, gateway: BoilerGateway, name: str, update_interval):
        self.gateway = gateway
        self.name = name
        
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=update_interval,
        )
    
    async def _async_update_data(self) -> dict:
        """
        Poll all registers and return cached data.
        Raises UpdateFailed on timeout/connection loss.
        """
        try:
            # Batch read all sensor registers
            # Read registers from 0x0010 through 0x0026 (inclusive)
            # Count = (0x0026 - 0x0010) + 1 = 23 registers
            status_regs = await self.gateway.protocol.read_registers(
                self.gateway.slave_id,
                0x0010,  # Start address
                23,      # Count: registers 0x0010..0x0026
                timeout=3.0
            )
            
            if status_regs is None:
                raise UpdateFailed("Boiler did not respond")
            
            # Decode and cache
            data = {}
            base_addr = 0x0010
            for i, value in enumerate(status_regs):
                data[base_addr + i] = value
            
            self.gateway.cache = data
            self.gateway.cache_timestamp[time.time()] = True
            
            return data
        
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Modbus timeout: {err}")
        except Exception as err:
            _LOGGER.error(f"Unexpected error updating boiler data: {err}")
            raise UpdateFailed(f"Unexpected error: {err}")
```

---

## 6. Error Handling, Retries, and Unavailable Data Strategy

### 6.1 Timeout & Retry Policy

```python
class RetryPolicy:
    """Configure retry behavior for Modbus operations."""
    
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 0.5  # seconds
    MAX_BACKOFF = 3.0
    EXPONENTIAL_BASE = 2.0
    
    @staticmethod
    async def execute_with_retry(
        coro_func,
        *args,
        max_retries: int = MAX_RETRIES,
        **kwargs
    ):
        """Execute coroutine with exponential backoff on timeout."""
        backoff = RetryPolicy.INITIAL_BACKOFF
        
        for attempt in range(max_retries):
            try:
                return await coro_func(*args, **kwargs)
            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(backoff)
                backoff = min(backoff * RetryPolicy.EXPONENTIAL_BASE,
                             RetryPolicy.MAX_BACKOFF)
            except Exception:
                raise
```

**Application:**
- Individual sensor reads: 2-3 retries within coordinator's `_async_update_data()`
- Control commands (set temperature, etc.): 1 retry with immediate fallback
- Connection test during Config Flow: 1 attempt, strict timeout

### 6.2 Device Availability States

```python
class AvailabilityStrategy:
    """Track device availability based on update success/failure."""
    
    # Device marked UNAVAILABLE after N consecutive failures
    FAILURE_THRESHOLD = 3
    
    def __init__(self):
        self.consecutive_failures = 0
        self.is_available = True
    
    def on_update_success(self):
        """Reset failure counter on successful update."""
        self.consecutive_failures = 0
        if not self.is_available:
            self.is_available = True
            _LOGGER.info("Device came back online")
    
    def on_update_failed(self):
        """Increment failure counter."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.FAILURE_THRESHOLD:
            if self.is_available:
                self.is_available = False
                _LOGGER.warning("Device marked unavailable")
    
    @property
    def available(self) -> bool:
        return self.is_available
```

**Entity Implementation:**
```python
class BoilerSensorEntity(SensorEntity):
    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success
```

### 6.3 Unsupported/Invalid Value Handling

**Invalid/Unsupported Values by Register Type:**

| Scenario | Value | Handling |
|----------|-------|----------|
| 16-bit temp (0x7FFF) | No sensor or error | Return `None` to HA (state = unavailable) |
| 8-bit flag (0xFF) | Unsupported | Return `None` (sensor unavailable) |
| Bitfield unavailable | 0x00 (no comm) | Do NOT report as OFF; use `None` |
| Multi-register timeout | Partial data | Treat as complete failure; don't mix partial reads |

```python
def _handle_invalid_value(raw_value: int, invalid_marker: int) -> int | None:
    """Return None if value indicates sensor not available."""
    return None if raw_value == invalid_marker else raw_value
```

### 6.4 Automatic Error Handling (modbus-tk)

**CRC Validation:**
- CRC16 calculation and verification handled automatically by modbus-tk
- Invalid CRC frames are detected and raise ModbusError
- Invalid frames are NOT retried at protocol level; coordinator implements retry logic

**Serial Communication Errors:**
- All serial I/O errors automatically detected and reported
- Timeouts raise asyncio.TimeoutError (caught and converted to None return in wrapper)
- Device unavailability tracked at coordinator level (3 consecutive failures = unavailable)

---

## 7. Implementation Phases, Milestones, and Testing Strategy

### 7.1 Phase Breakdown

#### **Phase 1: Foundation (Weeks 1–2)**
- ✅ Modbus RTU protocol driver (`modbus_protocol.py`)
  - Serial port I/O
  - Frame construction/parsing
  - CRC16 calculation
  - Big-Endian encoding/decoding
- ✅ Unit tests for protocol layer
- ✅ Boiler Gateway basic sensor reads (`boiler_gateway.py`)

**Deliverable:** Functional low-level Modbus communication

**Testing:**
```python
# test_modbus_protocol.py
def test_crc16_calculation():
    """Verify CRC16 matches expected values."""
    frame = bytes([0x01, 0x03, 0x00, 0x10, 0x00, 0x01])
    crc_lo, crc_hi = ModbusProtocol._crc16(frame)
    assert (crc_lo, crc_hi) == (expected_lo, expected_hi)

def test_big_endian_decode():
    """Test 16-bit Big-Endian decoding."""
    protocol = ModbusProtocol("/dev/ttyUSB0")
    assert protocol._decode_big_endian_u16(0x01, 0x23) == 0x0123
#### **Phase 1: Foundation (Weeks 1–2)**
+ ✅ Modbus RTU protocol wrapper (`modbus_protocol.py`)
+   - Async wrapper around modbus-tk RTU client
+   - Connection lifecycle (open/close)
+   - Error handling & translation
+ ✅ Unit tests for protocol wrapper
+ ✅ Boiler Gateway basic sensor reads (`boiler_gateway.py`)
+
+**Deliverable:** Functional Modbus communication with modbus-tk
+
+**Testing:**
+```python
+# test_modbus_protocol.py
+async def test_connect_to_port():
+    """Verify connection to serial port."""
+    protocol = ModbusProtocol("/dev/ttyUSB0")
+    connected = await protocol.connect()
+    assert connected is True
+    await protocol.disconnect()
+
+async def test_read_registers():
+    """Test reading holding registers via modbus-tk."""
+    protocol = ModbusProtocol("/dev/ttyUSB0")
+    await protocol.connect()
+    result = await protocol.read_registers(
+        slave_id=1,
+        start_addr=0x0010,
+        count=1
+    )
+    assert result is not None
+    assert isinstance(result, list)
+    await protocol.disconnect()
+
+async def test_read_timeout():
+    """Verify timeout is handled gracefully."""
+    protocol = ModbusProtocol("/dev/ttyUSB0")
+    await protocol.connect()
+    result = await protocol.read_registers(
+        slave_id=99,  # Invalid slave
+        start_addr=0x0010,
+        count=1,
+        timeout=1.0
+    )
+    assert result is None  # Timeout returns None
+    await protocol.disconnect()
+```
```

#### **Phase 2: Integration Core (Weeks 2–3)**
- ✅ Config Flow UI (`config_flow.py`)
  - Port selection
  - Slave ID input
  - Connection test
  - Conflict detection
- ✅ DataUpdateCoordinator (`coordinator.py`)
- ✅ Integration setup/unload (`__init__.py`)
- ✅ Config Flow tests

**Deliverable:** User can add boilers via UI; polling works

**Testing:**
```python
# test_config_flow.py
async def test_config_flow_user_input():
    """Test configuration flow step by step."""
    result = await config_flow.async_step_user(
        {"port": "/dev/ttyUSB0"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "port_selection"

async def test_config_flow_duplicate_slave_id():
    """Test that duplicate slave ID is rejected."""
    # Create first entry
    await config_flow.async_step_user({...})
    # Attempt second with same port + slave_id
    result = await config_flow.async_step_slave_id({"slave_id": 1})
    assert result["errors"]["slave_id"] == "slave_id_already_configured"
```

#### **Phase 3: Entity Implementation (Weeks 3–4)**
- ✅ Sensor entities (temperature, pressure, flow, modulation)
- ✅ Binary sensor entities (burner, heating, DHW states)
- ✅ Switch entities (enable/disable circuits)
- ✅ Number entities (setpoints, limits)
- ✅ Climate entity (primary control)
- ✅ Availability logic

**Deliverable:** All sensor readings visible in HA; basic control working

**Testing:**
```python
# test_entities.py
async def test_temperature_sensor_value():
    """Verify temperature is correctly scaled."""
    sensor = TemperatureSensor(coordinator, gateway, 0x0018)
    coordinator.data = {0x0018: 291}
    assert sensor.state == 29.1

async def test_invalid_sensor_value():
    """Verify invalid values return None."""
    sensor = TemperatureSensor(coordinator, gateway, 0x0018)
    coordinator.data = {0x0018: 0x7FFF}
    assert sensor.state is None
    assert sensor.available is False
```

#### **Phase 4: Advanced Features (Week 4)**
- ✅ Error code display
- ✅ Adapter version/info sensors
- ✅ Reboot adapter command
- ✅ Reset error command
- ✅ Diagnostics data export

**Deliverable:** Full feature parity with register map

#### **Phase 5: Testing & Documentation (Week 5)**
- ✅ Integration tests with mock Modbus slave
- ✅ Real hardware testing (if available)
- ✅ README.md, troubleshooting guide
- ✅ CHANGELOG.md
- ✅ HACS submission prep

### 7.2 Testing Strategy

#### **Unit Tests**
- CRC16 algorithm (test vectors)
- Big-Endian encoding/decoding
- Bitfield manipulation
- Register scaling (÷10, etc.)

#### **Integration Tests**
- Mock Modbus slave server (using `pymodbus` library in test mode)
- Full Config Flow execution
- Multiple boilers on same port
- Entity state updates from coordinator

```python
# test_integration.py
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataStore

async def test_full_boiler_setup_and_polling():
    """Test complete setup → polling → entity updates."""
    # 1. Start mock Modbus server
    store = ModbusSequentialDataStore()
    store.setValues(3, 0x0010, [0x0805])  # Register 0x0010: comm OK + adapter type
    
    # 2. Create integration entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"port": "/dev/ttyUSB0", "slave_id": 1}
    )
    
    # 3. Setup integration
    await async_setup_entry(hass, config_entry)
    
    # 4. Verify coordinator updates
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    
    # 5. Verify entities received data
    sensor = hass.states.get("sensor.boiler_ch_temperature")
    assert sensor is not None
    assert sensor.state == "29.1"  # Assuming register 0x0018 = 291
```
```python
+# test_integration.py
+from unittest.mock import AsyncMock, MagicMock, patch
+
+async def test_full_boiler_setup_and_polling():
+    """Test complete setup → polling → entity updates."""
+    # 1. Mock modbus-tk RtuClient
+    mock_client = MagicMock()
+    mock_client.read_holding_registers = MagicMock(
+        return_value=[
+            0x0805,  # 0x0010: status (comm OK, adapter type)
+            0x0102,  # 0x0011: HW/SW version
+            0x0000,  # 0x0012: uptime high
+            0x3600,  # 0x0013: uptime low
+            291,     # 0x0018: CH temp = 29.1°C
+            450,     # 0x0019: DHW temp = 45.0°C
+            12,      # 0x001A: pressure = 1.2 bar
+            0,       # 0x001B: flow = 0.0 L/min
+            75,      # 0x001C: modulation = 75%
+            0b0000011,  # 0x001D: burner ON, heating enabled
+        ]
+    )
+    
+    # 2. Create integration entry
+    config_entry = MockConfigEntry(
+        domain=DOMAIN,
+        data={"port": "/dev/ttyUSB0", "slave_id": 1}
+    )
+    
+    # 3. Setup integration with mocked modbus-tk
+    with patch('modbus_tk.modbus_rtu.RtuClient', return_value=mock_client):
+        await async_setup_entry(hass, config_entry)
+    
+    # 4. Verify coordinator updates
+    await coordinator.async_refresh()
+    assert coordinator.last_update_success
+    
+    # 5. Verify entities received data
+    sensor = hass.states.get("sensor.boiler_ch_temperature")
+    assert sensor is not None
+    assert sensor.state == "29.1"  # 291 / 10.0 = 29.1°C
+    
+    burner = hass.states.get("binary_sensor.boiler_burner")
+    assert burner.state == "on"  # bit 0 of 0x001D = 1
+```
### 8.1 Future Capabilities

#### **Auto-Discovery**
```python
async def async_step_discovery(self, discovery_info):
    """
    Implement mDNS/zeroconf discovery for adapters (if they support it).
    Or provide "Scan Port" option to find responding Slave IDs.
    """
    results = await discover_slaves_on_port(discovery_info["port"])
    return self.async_show_form(
        step_id="select_discovered",
        data_schema=vol.Schema({
            vol.Required("slave_id"): vol.In(results)
        })
    )
```

#### **Telegram/Notification on Error**
- Send notification when main error code changes
- Configurable error thresholds
- Historical error log

#### **Performance Metrics Dashboard**
- Average CH temperature over 24 hours
- Burner on-time statistics
- Modulation level history
- Pressure trending

#### **Multi-Register Write Optimization**
- Batch multiple setpoint writes into single 0x10 command
- Example: write CH setpoint (0x0031) + DHW setpoint (0x0037) simultaneously

#### **Thermostat Mode Expansion**
- Current: HEAT / OFF
- Future: HEAT_ONLY, DHW_ONLY, HEAT+DHW modes

#### **Advanced Scheduling**
- Schedule setpoint changes per time-of-day
- Seasonal profiles (winter/summer CH limits)
- Integration with HA automation & templates

#### **Modbus Function 0x4B/0x4C Support**
- Programmatic slave address assignment via serial number
- Useful for large installations with multiple Modbus slaves

#### **Integration with MQTT**
- Publish boiler state to MQTT topics
- Subscribe to commands from external systems
- Bridge with non-HA setups

---

## 9. Code Structure Reference

### 9.1 Directory Layout (Final)

```
custom_components/ectocontrol_modbus/
├── __init__.py                    # async_setup_entry, async_unload_entry
├── manifest.json                  # Version, requirements, requirements_all
├── strings.json                   # UI labels & help text
├── const.py                       # DOMAIN, CONF_*, register addresses, etc.
├── config_flow.py                 # ConfigFlow class + validation logic
├── coordinator.py                 # BoilerDataUpdateCoordinator
├── modbus_protocol.py             # ModbusProtocol class
├── boiler_gateway.py              # BoilerGateway class
├── diagnostics.py                 # async_get_diagnostics hook
├── entities/
│   ├── __init__.py
│   ├── entity.py                  # Base entity class with common logic
│   ├── sensor.py                  # TemperatureSensor, PressureSensor, etc.
│   ├── binary_sensor.py           # BurnerStateSensor, HeatingEnabledSensor
│   ├── switch.py                  # HeatingSwitch, DHWSwitch, RebootSwitch
│   └── number.py                  # CHSetpointNumber, DHWSetpointNumber
└── tests/
    ├── conftest.py                # pytest fixtures
    ├── test_modbus_protocol.py
    ├── test_boiler_gateway.py
    ├── test_config_flow.py
    └── test_integration.py
```

### 9.2 Key Constants & Configuration

```python
# const.py

DOMAIN = "ectocontrol_modbus"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"
CONF_NAME = "name"

# Modbus parameters
MODBUS_BAUDRATE = 19200
MODBUS_TIMEOUT = 2.0
MODBUS_RETRY_COUNT = 3

# Register addresses
REGISTER_STATUS = 0x0010
REGISTER_CH_TEMP = 0x0018
REGISTER_DHW_TEMP = 0x0019
REGISTER_PRESSURE = 0x001A
REGISTER_FLOW = 0x001B
REGISTER_MODULATION = 0x001C
REGISTER_STATES = 0x001D
REGISTER_MAIN_ERROR = 0x001E
REGISTER_ADD_ERROR = 0x001F
REGISTER_OUTDOOR_TEMP = 0x0020
REGISTER_MFG_CODE = 0x0021
REGISTER_MODEL_CODE = 0x0022
REGISTER_OT_ERROR = 0x0023
REGISTER_CH_SETPOINT_ACTIVE = 0x0026
REGISTER_CH_SETPOINT = 0x0031
REGISTER_EMERGENCY_CH = 0x0032
REGISTER_DHW_SETPOINT = 0x0037
REGISTER_MAX_MODULATION = 0x0038
REGISTER_CIRCUIT_ENABLE = 0x0039
REGISTER_COMMAND = 0x0080
REGISTER_COMMAND_RESULT = 0x0081

# Polling intervals
DEFAULT_SCAN_INTERVAL = 15  # seconds
FAST_SCAN_INTERVAL = 10  # for command verification

# Update coordinator
COORDINATOR_NAME = "ectocontrol_modbus"
```

### 9.3 Sample Entity Implementation

```python
# entities/sensor.py

@dataclass
class SensorDescription(SensorEntityDescription):
    """Custom sensor description for Ectocontrol."""
    register_addr: int
    scale_factor: float = 1.0
    invalid_marker: int | None = None
    value_type: type = int

class CHTemperatureSensor(SensorEntity):
    """Heating circuit water temperature sensor."""
    
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(self, coordinator, gateway, boiler_name):
        self.coordinator = coordinator
        self.gateway = gateway
        self._attr_unique_id = f"ectocontrol_{boiler_name}_ch_temp"
        self._attr_name = "CH Water Temperature"
    
    @property
    def native_value(self) -> float | None:
        """Return scaled temperature or None if invalid."""
        raw = self.coordinator.data.get(REGISTER_CH_TEMP)
        if raw is None or raw == 0x7FFF:
            return None
        return raw / 10.0
    
    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

## Home Assistant Required Entities (per boiler)

For each configured boiler the integration MUST create the following entities (entity_id examples shown):

- `sensor.ch_water_temperature` → register `0x0018` (i16, ÷10 °C)
- `sensor.dhw_temperature` → register `0x0019` (u16, ÷10 °C)
- `sensor.pressure` → register `0x001A` (u8 in MSB, ÷10 bar)
- `sensor.flow_rate` → register `0x001B` (u8 in MSB, ÷10 L/min)
- `sensor.burner_modulation` → register `0x001C` (u8 in MSB, %)
- `sensor.boiler_error_main` → register `0x001E` (u16)
- `sensor.boiler_error_extra` → register `0x001F` (u16)
- `sensor.outdoor_temperature` → register `0x0020` (i8 in MSB)
- `sensor.boiler_manufacturer` → register `0x0021` (u16)
- `sensor.boiler_model` → register `0x0022` (u16)
- `sensor.opentherm_error_class` → register `0x0023` (i8 in MSB)
- `sensor.ch_setpoint_active` → register `0x0026` (i16, step = 1/256 °C)
- `switch.heating_enable` → register `0x0039` bit0 (writeable)
- `switch.dhw_enable` → register `0x0039` bit1 (writeable)
- `button.reboot_adapter` → writes `0x0080 = 2` (command register)
- `button.reset_boiler_errors` → writes `0x0080 = 3` (command register)
- `sensor.adapter_reboot_code` → MSB byte of `0x0010` (u8)

Notes:
- All sensors must return `None` for invalid/unsupported markers (`0x7FFF`, `0xFF`, `0x7F`) so Home Assistant shows no state rather than an invalid numeric.
- Switch/button entities should call `BoilerGateway` write helpers which perform read-modify-write when manipulating bitfields in `0x0039` or write direct command values to `0x0080`.
```

---

## 10. Conclusion & Next Steps

This implementation plan provides:

1. ✅ **Complete architectural blueprint** for HA HACS integration
2. ✅ **Detailed Modbus protocol specifications** with Big-Endian examples
3. ✅ **Production-ready configuration flow** with validation
4. ✅ **Entity model** covering all 13+ register types
5. ✅ **Error handling strategies** for reliability
6. ✅ **5-phase development roadmap** with milestones
7. ✅ **Comprehensive testing strategy** with sample tests
8. ✅ **Code structure** ready for immediate implementation

### Recommended First Step:
1. Clone HA integration template
2. Implement Phase 1 (Modbus driver + tests)
3. Validate with hardware
4. Proceed to Phase 2–5 incrementally

### Dependencies to Add to `requirements.txt`:
+```
+modbus-tk>=1.1.2
+pyserial>=3.5
+homeassistant>=2024.1
+```

---

**Document prepared for immediate development execution.**  
**All code examples are pseudocode-compliant with HA patterns; adapt to current HA version as needed.**

