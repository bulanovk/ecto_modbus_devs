# Testing Alignment Plan

This document provides a step-by-step plan to align the existing test suite with the guidelines specified in [TESTING.md](TESTING.md).

---

## Prerequisites & Environment Setup

### Python Version Requirement

**Required: Python 3.13+**

The integration requires Python 3.13 or higher. Verify your Python version before running tests:

```bash
# Check Python version
python --version
# or
python3 --version

# Expected output: Python 3.13.x or higher
```

If you need to install Python 3.13:
- **Windows**: Download from [python.org](https://www.python.org/downloads/)
- **Linux**: `sudo apt install python3.13` or use deadsnakes PPA
- **macOS**: `brew install python@3.13`

---

### Virtual Environment (venv) Setup

**IMPORTANT: Always use the `.venv` virtual environment when running tests.**

#### Initial Setup (First Time Only)

```bash
# Navigate to project root
cd /path/to/modbus

# Create virtual environment with Python 3.13
python3.13 -m venv .venv

# Activate the virtual environment
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### Activating the Virtual Environment (Each Session)

**Before running any tests or Python commands:**

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

**Your prompt should show `(.venv)` when the environment is active:**

```
(.venv) PS C:\projects\modbus>
(.venv) user@host:~/projects/modbus$
```

#### Deactivating the Virtual Environment

```bash
deactivate
```

---

### Verifying Your Environment

Before starting the alignment work, verify your environment is correctly set up:

```bash
# 1. Ensure virtual environment is active
# Prompt should show (.venv)

# 2. Check Python version
python --version
# Expected: Python 3.13.x

# 3. Verify pytest is installed from venv
pip show pytest
# Should show pytest info, not "Package not found"

# 4. Verify test discovery works
pytest --collect-only
# Should list all test files
```

---

### Common Environment Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError` | venv not activated or dependencies not installed | Activate venv and run `pip install -r requirements.txt` |
| Wrong Python version | System Python instead of venv | Activate venv and verify with `python --version` |
| Tests not found | Incorrect pytest.ini or test discovery issue | Verify pytest.ini has `testpaths = tests` |
| Import errors | PYTHONPATH issue | Ensure pytest.ini has `pythonpath = .` |

---

### Quick Environment Checklist

Before starting any work in this plan:

- [ ] Python 3.13+ installed
- [ ] Virtual environment created (`python3.13 -m venv .venv`)
- [ ] Virtual environment activated (prompt shows `(.venv)`)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Can run `pytest --collect-only` successfully

---

## Executive Summary

After reviewing the current test suite against the TESTING.md guidelines, the following key areas require alignment:

| Area | Current State | Required State | Priority |
|------|---------------|----------------|----------|
| **pytest.ini** | Missing asyncio config | Add asyncio_mode and loop_scope | High |
| **Config Flow Tests** | String comparison, dummy fakes | FlowResultType enum, MockConfigEntry | High |
| **Options Flow** | Missing tests | Add options flow tests | High |
| **Reconfigure Flow** | Missing tests | Add reconfigure flow tests | High |
| **Entity Tests** | Missing device_info, unavailable state tests | Add comprehensive entity tests | Medium |
| **Type Hints** | Missing on test functions | Add type hints to all tests | Low |

---

## Phase 1: Infrastructure Configuration

### Step 1.1: Update pytest.ini

**Prerequisites:**
- Ensure virtual environment is activated: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/macOS)
- Verify Python 3.13+ is being used: `python --version`

**Current Issues:**
- Missing `asyncio_mode = auto`
- Missing `asyncio_default_fixture_loop_scope = function`
- Missing `testpaths = tests`

**Action Required:**

Update [pytest.ini](../pytest.ini) to include:

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
pythonpath = .
filterwarnings =
    ignore:CSR support in pyOpenSSL is deprecated.:DeprecationWarning:josepy.util
    ignore:CSR support in pyOpenSSL is deprecated.:DeprecationWarning:acme.crypto_util
    ignore:Inheritance class HomeAssistantApplication from web.Application is discouraged:DeprecationWarning:homeassistant.components.http
```

**Files to modify:** [pytest.ini](../pytest.ini)

**Verification:** Run `pytest --collect-only` to ensure tests are discovered correctly.

---

## Phase 2: Config Flow Test Alignment

### Step 2.1: Replace String Comparison with FlowResultType Enum

**Current Issue:**
In [test_config_flow.py](../tests/test_config_flow.py:68):
```python
assert result["type"] == "create_entry"  # String comparison
```

**Action Required:**

1. Add import at top of file:
```python
from homeassistant.data_entry_flow import FlowResultType
```

2. Replace all string comparisons with enum values:

| Line | Before | After |
|------|--------|-------|
| 68 | `assert result["type"] == "create_entry"` | `assert result["type"] == FlowResultType.CREATE_ENTRY` |
| 81 | `assert result["type"] == "form"` | `assert result["type"] == FlowResultType.FORM` |
| 97 | `assert result["type"] == "form"` | `assert result["type"] == FlowResultType.FORM` |
| 112 | `assert result["type"] == "form"` | `assert result["type"] == FlowResultType.FORM` |
| 127 | `assert result["type"] == "form"` | `assert result["type"] == FlowResultType.FORM` |

**Files to modify:** [tests/test_config_flow.py](../tests/test_config_flow.py)

---

### Step 2.2: Replace Dummy Classes with MockConfigEntry

**Current Issues:**
- Uses `DummyEntry`, `DummyHass`, `DummyConfigEntries` dummy classes
- Missing proper HA test integration with `hass` fixture
- Missing `auto_enable_custom_integrations` fixture

**Action Required:**

1. Add new imports (replace current imports at top):
```python
import pytest
from homeassistant import config_entries, setup
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

cf = importlib.import_module("custom_components.ectocontrol_modbus.config_flow")
const = importlib.import_module("custom_components.ectocontrol_modbus.const")
```

2. Add auto-enable custom integrations fixture:
```python
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable custom integrations (required for HA >= 2021.6.0b0)."""
    yield
```

3. Add mock_serial_ports fixture:
```python
@pytest.fixture
def mock_serial_ports(monkeypatch):
    """Mock serial port listing."""
    monkeypatch.setattr(
        "custom_components.ectocontrol_modbus.config_flow.serial.tools.list_ports.comports",
        lambda: [DummyPort("/dev/ttyUSB0")]
    )
```

4. Refactor test functions to use `hass` fixture and `MockConfigEntry`:

**Before:**
```python
@pytest.mark.asyncio
async def test_config_flow_success(monkeypatch):
    monkeypatch.setattr(cf.serial.tools.list_ports, "comports", lambda: [DummyPort("/dev/ttyUSB0")])
    monkeypatch.setattr(cf, "ModbusProtocol", FakeProtocolOK)

    flow = cf.EctocontrolConfigFlow()
    flow.hass = DummyHass()

    user_input = {const.CONF_PORT: "/dev/ttyUSB0", const.CONF_SLAVE_ID: 1, const.CONF_NAME: "Boiler"}
    result = await flow.async_step_user(user_input)

    assert result["type"] == "create_entry"
```

**After:**
```python
@pytest.mark.asyncio
async def test_config_flow_success(hass: HomeAssistant, mock_serial_ports, monkeypatch) -> None:
    """Test successful config flow - CREATE action."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    monkeypatch.setattr(cf, "ModbusProtocol", FakeProtocolOK)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {const.CONF_PORT: "/dev/ttyUSB0", const.CONF_SLAVE_ID: 1, const.CONF_NAME: "Boiler"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Boiler"
    assert result["data"][const.CONF_PORT] == "/dev/ttyUSB0"
```

**Files to modify:** [tests/test_config_flow.py](../tests/test_config_flow.py)

---

### Step 2.3: Add Options Flow Tests

**Current Issue:**
Missing options flow tests for modifying polling interval and retry count.

**Action Required:**

Add the following test function to [test_config_flow.py](../tests/test_config_flow.py):

```python
@pytest.mark.asyncio
async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow - MODIFY polling interval and retry count."""
    # Create and add mock config entry
    mock_config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        data={
            const.CONF_PORT: "/dev/ttyUSB0",
            const.CONF_SLAVE_ID: 1,
            const.CONF_NAME: "Boiler"
        },
        options={
            const.CONF_POLLING_INTERVAL: 15,
            const.CONF_RETRY_COUNT: 3
        }
    )
    mock_config_entry.add_to_hass(hass)

    # 1. Initialize options flow
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # 2. Submit updated options
    user_input = {
        const.CONF_POLLING_INTERVAL: 30,
        const.CONF_RETRY_COUNT: 5
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input
    )

    # 3. Wait for completion and verify
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[const.CONF_POLLING_INTERVAL] == 30
    assert mock_config_entry.options[const.CONF_RETRY_COUNT] == 5
```

**Files to modify:** [tests/test_config_flow.py](../tests/test_config_flow.py)

---

### Step 2.4: Add Reconfigure Flow Tests

**Current Issue:**
Missing reconfigure flow tests for modifying core settings (port, slave_id).

**Action Required:**

Add the following test function to [test_config_flow.py](../tests/test_config_flow.py):

```python
@pytest.mark.asyncio
async def test_reconfigure_flow(hass: HomeAssistant, mock_serial_ports, monkeypatch) -> None:
    """Test reconfigure flow - MODIFY core settings (port, slave_id)."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    # Create existing entry
    mock_config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        data={
            const.CONF_PORT: "/dev/ttyUSB0",
            const.CONF_SLAVE_ID: 1,
            const.CONF_NAME: "Boiler"
        }
    )
    mock_config_entry.add_to_hass(hass)

    monkeypatch.setattr(cf, "ModbusProtocol", FakeProtocolOK)

    # 1. Initiate reconfigure
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE},
        data=mock_config_entry
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # 2. Submit updated settings
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            const.CONF_PORT: "/dev/ttyUSB1",
            const.CONF_SLAVE_ID: 2
        }
    )

    # 3. Verify entry was updated and reloaded
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[const.CONF_PORT] == "/dev/ttyUSB1"
    assert mock_config_entry.data[const.CONF_SLAVE_ID] == 2
```

**Files to modify:** [tests/test_config_flow.py](../tests/test_config_flow.py)

---

### Step 2.5: Add Type Hints to Config Flow Tests

**Action Required:**

Add type hints to all test function signatures:

| Function | Current Signature | Updated Signature |
|----------|-------------------|-------------------|
| `test_config_flow_success` | `async def test_config_flow_success(monkeypatch):` | `async def test_config_flow_success(hass: HomeAssistant, mock_serial_ports, monkeypatch) -> None:` |
| `test_config_flow_invalid_slave` | `async def test_config_flow_invalid_slave(monkeypatch):` | `async def test_config_flow_invalid_slave(hass: HomeAssistant, mock_serial_ports) -> None:` |
| `test_config_flow_duplicate_detection` | `async def test_config_flow_duplicate_detection(monkeypatch):` | `async def test_config_flow_duplicate_detection(hass: HomeAssistant, mock_serial_ports, monkeypatch) -> None:` |
| `test_config_flow_cannot_connect` | `async def test_config_flow_cannot_connect(monkeypatch):` | `async def test_config_flow_cannot_connect(hass: HomeAssistant, mock_serial_ports, monkeypatch) -> None:` |
| `test_config_flow_no_response` | `async def test_config_flow_no_response(monkeypatch):` | `async def test_config_flow_no_response(hass: HomeAssistant, mock_serial_ports, monkeypatch) -> None:` |

**Files to modify:** [tests/test_config_flow.py](../tests/test_config_flow.py)

---

## Phase 3: Entity Test Alignment

### Step 3.1: Update FakeGateway for device_info Tests

**Current Issue:**
`FakeGateway` doesn't have protocol/port info needed for `device_info` tests.

**Action Required:**

Update the `FakeGateway` class in [test_entities.py](../tests/test_entities.py):

```python
class FakeGateway:
    def __init__(self):
        self.slave_id = 1
        self.cache = {0x001D: 0}
        self.last_set_raw = None
        self.circuit_written = None
        # Add protocol mock for device_info tests
        self.protocol = type('obj', (object,), {'port': 'mock_port'})
```

**Files to modify:** [tests/test_entities.py](../tests/test_entities.py)

---

### Step 3.2: Update DummyCoordinator for Availability Tests

**Current Issue:**
`DummyCoordinator` doesn't have `last_update_success` attribute needed for availability tests.

**Action Required:**

Update the `DummyCoordinator` class in [test_entities.py](../tests/test_entities.py):

```python
class DummyCoordinator:
    def __init__(self, gateway):
        self.gateway = gateway
        self.last_update_success = True  # Add for availability tests

    async def async_request_refresh(self):
        self.refreshed = True
```

**Files to modify:** [tests/test_entities.py](../tests/test_entities.py)

---

### Step 3.3: Add device_info Property Tests

**Current Issue:**
Missing tests for `device_info` property that ensures proper entity-device association.

**Action Required:**

Add the following test function to [test_entities.py](../tests/test_entities.py):

```python
def test_boiler_sensor_device_info() -> None:
    """Test entity has device_info for proper device association."""
    gw = FakeGateway()
    coord = DummyCoordinator(gw)

    s = BoilerSensor(coord, "get_ch_temperature", "CH Temp", "°C")
    device_info = s.device_info

    assert device_info is not None
    assert device_info["identifiers"] == {(const.DOMAIN, f"mock_port:1")}
```

**Note:** You'll need to import `const`:
```python
import importlib
const = importlib.import_module("custom_components.ectocontrol_modbus.const")
```

**Files to modify:** [tests/test_entities.py](../tests/test_entities.py)

---

### Step 3.4: Add _attr_has_entity_name Verification Tests

**Current Issue:**
Missing verification that `_attr_has_entity_name = True` is set on entity classes.

**Action Required:**

Add the following test function to [test_entities.py](../tests/test_entities.py):

```python
def test_boiler_sensor_has_entity_name() -> None:
    """Test entity has _attr_has_entity_name set to True."""
    gw = FakeGateway()
    coord = DummyCoordinator(gw)

    s = BoilerSensor(coord, "get_ch_temperature", "CH Temp", "°C")
    assert s._attr_has_entity_name is True
```

**Files to modify:** [tests/test_entities.py](../tests/test_entities.py)

---

### Step 3.5: Add Unavailable State Tests

**Current Issue:**
Missing tests for entity unavailable state when coordinator fails.

**Action Required:**

Add the following test function to [test_entities.py](../tests/test_entities.py):

```python
def test_boiler_sensor_unavailable_when_coordinator_fails() -> None:
    """Test entity shows unavailable when coordinator last_update_success is False."""
    gw = FakeGateway()
    coord = DummyCoordinator(gw)
    coord.last_update_success = False

    s = BoilerSensor(coord, "get_ch_temperature", "CH Temp", "°C")
    assert s.available is False
```

**Files to modify:** [tests/test_entities.py](../tests/test_entities.py)

---

### Step 3.6: Add Type Hints to Entity Tests

**Action Required:**

Add type hints to all test function signatures:

| Function | Current Signature | Updated Signature |
|----------|-------------------|-------------------|
| `test_boiler_sensor_native_values` | `def test_boiler_sensor_native_values():` | `def test_boiler_sensor_native_values() -> None:` |
| `test_binary_sensor_is_on` | `def test_binary_sensor_is_on():` | `def test_binary_sensor_is_on() -> None:` |
| `test_number_set_and_refresh` | `async def test_number_set_and_refresh():` | `async def test_number_set_and_refresh() -> None:` |
| `test_switch_turn_on_off_and_state` | `async def test_switch_turn_on_off_and_state():` | `async def test_switch_turn_on_off_and_state() -> None:` |
| `test_boiler_sensor_device_info` | `def test_boiler_sensor_device_info():` | `def test_boiler_sensor_device_info() -> None:` |
| `test_boiler_sensor_has_entity_name` | `def test_boiler_sensor_has_entity_name():` | `def test_boiler_sensor_has_entity_name() -> None:` |
| `test_boiler_sensor_unavailable_when_coordinator_fails` | `def test_boiler_sensor_unavailable_when_coordinator_fails():` | `def test_boiler_sensor_unavailable_when_coordinator_fails() -> None:` |

**Files to modify:** [tests/test_entities.py](../tests/test_entities.py)

---

## Phase 4: Review Remaining Entity Test Files

### Step 4.1: Review test_entities_more.py

**Checklist:**

- [ ] Replace string comparisons with `FlowResultType` enum (if any)
- [ ] Add type hints to all test functions
- [ ] Verify proper use of `MockConfigEntry` (if applicable)
- [ ] Add `device_info` property tests (if entities are tested)
- [ ] Add unavailable state tests (if applicable)

**Files to review:** [tests/test_entities_more.py](../tests/test_entities_more.py)

---

### Step 4.2: Review test_entities_climate.py

**Checklist:**

- [ ] Replace string comparisons with `FlowResultType` enum (if any)
- [ ] Add type hints to all test functions
- [ ] Verify proper use of `MockConfigEntry` (if applicable)
- [ ] Add `device_info` property tests
- [ ] Add unavailable state tests
- [ ] Verify climate-specific action tests (turn_on, turn_off, set_temperature)

**Files to review:** [tests/test_entities_climate.py](../tests/test_entities_climate.py)

---

### Step 4.3: Review test_entities_buttons.py

**Checklist:**

- [ ] Replace string comparisons with `FlowResultType` enum (if any)
- [ ] Add type hints to all test functions
- [ ] Verify proper use of `MockConfigEntry` (if applicable)
- [ ] Add `device_info` property tests
- [ ] Add unavailable state tests
- [ ] Verify button press action tests with `async_request_refresh` verification

**Files to review:** [tests/test_entities_buttons.py](../tests/test_entities_buttons.py)

---

## Phase 5: Integration Test Review

### Step 5.1: Review test_integration_modbus.py

**Checklist:**

- [ ] Verify use of `MockConfigEntry` (not dummy classes)
- [ ] Replace string comparisons with `FlowResultType` enum (if any)
- [ ] Add type hints to all test functions
- [ ] Verify proper HA test setup with `hass` fixture
- [ ] Verify entity registry checks use proper HA patterns

**Files to review:** [tests/test_integration_modbus.py](../tests/test_integration_modbus.py)

---

### Step 5.2: Review test_integration_modbus_edgecases.py

**Checklist:**

- [ ] Verify use of `MockConfigEntry` (not dummy classes)
- [ ] Replace string comparisons with `FlowResultType` enum (if any)
- [ ] Add type hints to all test functions
- [ ] Verify proper HA test setup with `hass` fixture
- [ ] Verify edge case coverage (timeout, disconnect, errors)

**Files to review:** [tests/test_integration_modbus_edgecases.py](../tests/test_integration_modbus_edgecases.py)

---

## Phase 6: Verification

**Prerequisites for all verification steps:**
- Ensure virtual environment is activated: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/macOS)
- Verify Python 3.13+ is being used: `python --version`

### Step 6.1: Run Full Test Suite

```bash
# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=custom_components/ectocontrol_modbus --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=custom_components/ectocontrol_modbus --cov-report=html
```

---

### Step 6.2: Run Individual Test Files

```bash
pytest tests/test_config_flow.py -v
pytest tests/test_entities.py -v
pytest tests/test_entities_more.py -v
pytest tests/test_entities_climate.py -v
pytest tests/test_entities_buttons.py -v
pytest tests/test_integration_modbus.py -v
pytest tests/test_integration_modbus_edgecases.py -v
```

---

### Step 6.3: Verify Coverage Goals

| Layer | Target | Command |
|-------|--------|---------|
| Protocol (`modbus_protocol.py`) | >80% | `pytest --cov=custom_components/ectocontrol_modbus/modbus_protocol.py --cov-report=term-missing` |
| Gateway (`boiler_gateway.py`) | >90% | `pytest --cov=custom_components/ectocontrol_modbus/boiler_gateway.py --cov-report=term-missing` |
| Config Flow (`config_flow.py`) | >90% | `pytest --cov=custom_components/ectocontrol_modbus/config_flow.py --cov-report=term-missing` |
| Entities (`entities/*.py`) | >85% | `pytest --cov=custom_components/ectocontrol_modbus/entities --cov-report=term-missing` |
| Coordinator (`coordinator.py`) | >85% | `pytest --cov=custom_components/ectocontrol_modbus/coordinator.py --cov-report=term-missing` |

---

## Implementation Order

To minimize disruption and ensure incremental progress, implement in this order:

| Phase | Step | Description | Estimated Time |
|-------|------|-------------|----------------|
| 0 | - | **Environment Setup** (Python 3.13+ venv activation) | 5 minutes |
| 1 | 1.1 | Update pytest.ini | 5 minutes |
| 2 | 2.1 | Config Flow - FlowResultType enum | 10 minutes |
| 2 | 2.5 | Config Flow - Type hints | 5 minutes |
| 2 | 2.3 | Add options flow tests | 15 minutes |
| 2 | 2.4 | Add reconfigure flow tests | 15 minutes |
| 2 | 2.2 | Config Flow - MockConfigEntry refactor | 30 minutes |
| 3 | 3.1 | Update FakeGateway | 5 minutes |
| 3 | 3.2 | Update DummyCoordinator | 5 minutes |
| 3 | 3.6 | Entity tests - Type hints | 10 minutes |
| 3 | 3.3 | Add device_info tests | 15 minutes |
| 3 | 3.4 | Add _attr_has_entity_name tests | 10 minutes |
| 3 | 3.5 | Add unavailable state tests | 15 minutes |
| 4 | 4.1-4.3 | Review remaining entity files | 30 minutes |
| 5 | 5.1-5.2 | Review integration tests | 20 minutes |
| 6 | 6.1-6.3 | Verification and coverage | 15 minutes |

**Total Estimated Time: ~2 hours**

---

## Testing Checklist Reference

After implementing the plan, verify all items in the TESTING.md checklist are complete:

### Config Flow Tests
- [x] User flow with valid input (success)
- [x] User flow with invalid input (validation errors)
- [x] Connection error handling
- [ ] Authentication error (if applicable) - N/A for this integration
- [x] Duplicate entry detection
- [ ] Options flow (modify settings) - **To be added in Step 2.3**
- [ ] Reconfigure flow (modify core data) - **To be added in Step 2.4**
- [ ] Abort conditions (already configured, incomplete discovery)

### Entity Tests
- [ ] Entity creation during setup - **Covered in integration tests**
- [x] `native_value` property returns correct data
- [ ] `unique_id` format is correct - **Partial coverage**
- [ ] `device_info` property is present - **To be added in Step 3.3**
- [ ] `_attr_has_entity_name = True` - **To be added in Step 3.4**
- [ ] Entity shows unavailable when coordinator fails - **To be added in Step 3.5**
- [x] Write actions (switches, numbers, buttons)
- [ ] `async_request_refresh()` called after writes - **Partial coverage**

### Gateway Tests
- [x] Register scaling (divide by 10, MSB extraction)
- [x] Invalid marker handling (`0x7FFF`, `0xFF`, `0x7F`)
- [x] Bitfield extraction and manipulation
- [x] Write helpers (setpoints, circuit enables)

### Protocol Tests
- [x] Successful connection
- [x] Failed connection
- [x] Read registers success
- [x] Read registers timeout/no response
- [x] Write register success
- [x] Write register failure

---

## Resources

- [TESTING.md](TESTING.md) - Testing Guidelines
- [CLAUDE.md](../CLAUDE.md) - Project Instructions
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)
