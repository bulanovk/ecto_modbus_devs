# Refactoring Plan: Sequential Register Reads Option

## Overview
Add an optional configuration to read Modbus registers sequentially (one by one) instead of in a single bulk read operation. This is useful when:
- The Modbus adapter has issues with multi-register reads
- You need individual retry logic per register
- You want to isolate failing registers

## Current Architecture (No Change)
```
Coordinator → Bulk Read (0x0010-0x0026, 23 regs) → Gateway Cache → Entities
```
- Single polling point: `BoilerDataUpdateCoordinator` polls registers every 15 seconds
- Cache-based: Entities read from `gateway.cache` populated by coordinator
- All entities extend `CoordinatorEntity`

## New Option: Sequential Reads
```
Coordinator → Sequential Reads (23 individual reads) → Gateway Cache → Entities
```
- Same architecture, just different read strategy in coordinator
- When enabled, each register is read individually with its own retry logic
- Entities remain unchanged

---

## Critical Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| [const.py](custom_components/ectocontrol_modbus/const.py) | Add | `CONF_SEQUENTIAL_READS` constant |
| [config_flow.py](custom_components/ectocontrol_modbus/config_flow.py) | Modify | Add sequential reads option to config UI |
| [coordinator.py](custom_components/ectocontrol_modbus/coordinator.py) | Modify | Add sequential read logic alongside bulk read |
| [__init__.py](custom_components/ectocontrol_modbus/__init__.py) | Modify | Pass config option to coordinator |

**No changes needed to:**
- `modbus_protocol.py` - existing single-register reads work fine
- `boiler_gateway.py` - cache-based getters unchanged
- `sensor.py`, `binary_sensor.py`, `switch.py`, `number.py`, `climate.py`, `button.py` - all unchanged

---

## Implementation

### Step 1: Add Configuration Constant
**File:** `custom_components/ectocontrol_modbus/const.py`

```python
CONF_SEQUENTIAL_READS = "sequential_reads"
DEFAULT_SEQUENTIAL_READS = False  # Default to bulk reads (current behavior)
```

### Step 2: Update Config Flow
**File:** `custom_components/ectocontrol_modbus/config_flow.py`

Add checkbox option to the config schema:

```python
# In the options step or config schema
vol.Optional(
    CONF_SEQUENTIAL_READS,
    default=False,
): bool
```

Add to strings.json for localization:
```json
{
  "step": {
    "user": {
      "data": {
        "sequential_reads": "Read registers sequentially (slower but more reliable)"
      }
    }
  }
}
```

### Step 3: Update Coordinator
**File:** `custom_components/ectocontrol_modbus/coordinator.py`

Add sequential read option and logic:

```python
class BoilerDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that polls Modbus registers and updates the `BoilerGateway` cache."""

    def __init__(
        self,
        hass,
        gateway,
        name: str,
        update_interval: timedelta = DEFAULT_SCAN_INTERVAL,
        retry_count: int = 3,
        sequential_reads: bool = False,  # NEW PARAMETER
    ):
        self.gateway = gateway
        self.name = name
        self.retry_count = retry_count
        self.sequential_reads = sequential_reads  # NEW
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Dict[int, int]:
        """Fetch data from Modbus and update gateway cache.

        Reads registers 0x0010..0x0026 in either:
        - Bulk mode: Single multi-register command (current behavior)
        - Sequential mode: Individual reads for each register (new option)

        Implements configurable retry logic for transient failures.
        """
        if self.sequential_reads:
            return await self._read_sequential()
        else:
            return await self._read_bulk()

    async def _read_bulk(self) -> Dict[int, int]:
        """Read all registers in a single bulk operation (current behavior)."""
        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                # Start address 0x0010, count 23 (0x0010..0x0026)
                regs = await self.gateway.protocol.read_registers(
                    self.gateway.slave_id, 0x0010, 23, timeout=3.0
                )
                if regs is None:
                    raise UpdateFailed("No response from device")

                data = {}
                base = 0x0010
                for i, v in enumerate(regs):
                    data[base + i] = v

                # Update gateway cache
                self.gateway.cache = data

                # Log retry recovery
                if attempt > 0:
                    _LOGGER.info("Recovered after %d retry attempts", attempt)

                return data

            except asyncio.TimeoutError as err:
                last_error = err
                if attempt < self.retry_count:
                    _LOGGER.warning(
                        "Timeout polling device (attempt %d/%d), retrying...",
                        attempt + 1,
                        self.retry_count + 1,
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
            except UpdateFailed:
                raise
            except Exception as err:
                last_error = err
                if attempt < self.retry_count:
                    _LOGGER.warning(
                        "Error polling boiler (attempt %d/%d): %s, retrying...",
                        attempt + 1,
                        self.retry_count + 1,
                        err,
                    )
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue

        _LOGGER.error("Unexpected error polling boiler after %d attempts: %s", self.retry_count + 1, last_error)
        raise UpdateFailed(f"Unexpected error: {last_error}")

    async def _read_sequential(self) -> Dict[int, int]:
        """Read registers one by one with individual retry logic.

        This is slower but more reliable when:
        - The adapter has issues with multi-register reads
        - Individual registers may fail independently
        - You need to isolate which register is causing issues
        """
        data = {}
        base = 0x0010
        count = 23

        for offset in range(count):
            addr = base + offset
            last_error = None

            for attempt in range(self.retry_count + 1):
                try:
                    regs = await self.gateway.protocol.read_registers(
                        self.gateway.slave_id, addr, 1, timeout=3.0
                    )

                    if regs is None:
                        raise UpdateFailed(f"No response for register 0x{addr:04X}")

                    data[addr] = regs[0]

                    if attempt > 0:
                        _LOGGER.debug("Register 0x%04X recovered after %d retries", addr, attempt)

                    break  # Success, move to next register

                except asyncio.TimeoutError as err:
                    last_error = err
                    if attempt < self.retry_count:
                        _LOGGER.debug(
                            "Timeout reading register 0x%04X (attempt %d/%d), retrying...",
                            addr, attempt + 1, self.retry_count + 1
                        )
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                except UpdateFailed:
                    last_error = err
                    if attempt < self.retry_count:
                        _LOGGER.debug(
                            "Error reading register 0x%04X (attempt %d/%d), retrying...",
                            addr, attempt + 1, self.retry_count + 1
                        )
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                except Exception as err:
                    last_error = err
                    if attempt < self.retry_count:
                        _LOGGER.warning(
                            "Error reading register 0x%04X (attempt %d/%d): %s, retrying...",
                            addr, attempt + 1, self.retry_count + 1, err
                        )
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue

            else:
                # All retries exhausted for this register
                _LOGGER.error(
                    "Failed to read register 0x%04X after %d attempts: %s",
                    addr, self.retry_count + 1, last_error
                )
                # Continue with next register - partial data is better than no data
                continue

        # Update gateway cache with whatever we successfully read
        self.gateway.cache = data

        if len(data) < count:
            _LOGGER.warning(
                "Sequential read completed with %d/%d registers successfully read",
                len(data), count
            )

        return data
```

### Step 4: Update __init__.py
**File:** `custom_components/ectocontrol_modbus/__init__.py`

Pass the config option to the coordinator:

```python
from .const import (
    # ... existing imports ...
    CONF_SEQUENTIAL_READS,
    DEFAULT_SEQUENTIAL_READS,
)

async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    # ... existing code ...

    sequential_reads = entry.data.get(CONF_SEQUENTIAL_READS, DEFAULT_SEQUENTIAL_READS)

    coordinator = BoilerDataUpdateCoordinator(
        hass,
        gateway,
        name=f"{DOMAIN}_{slave}",
        update_interval=timedelta(seconds=polling_interval),
        retry_count=retry_count,
        sequential_reads=sequential_reads,  # NEW PARAMETER
    )
```

Also handle options update:

```python
async def async_reload_entry(hass: HomeAssistant, entry) -> bool:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)
```

---

## Performance Comparison

| Mode | Read Time (23 registers) | Reliability | Use Case |
|------|-------------------------|-------------|----------|
| **Bulk** | ~12ms (single transaction) | All or nothing | Normal operation, reliable adapters |
| **Sequential** | ~276ms (23 × 12ms) | Partial data possible | Problematic adapters, debugging |

**Sequential mode with delays** (optional enhancement):
- Add configurable delay between reads (e.g., 50ms)
- Total time: 23 × (12ms + 50ms) = ~1.4 seconds
- Useful for adapters that need time between transactions

---

## Optional Enhancement: Per-Register Intervals

If you want even more control, you could define which registers to read and how often:

```python
# Example configuration
REGISTER_READS = [
    (0x0018, 15),  # CH Temperature - every 15s
    (0x0019, 30),  # DHW Temperature - every 30s
    (0x001A, 60),  # Pressure - every 60s
    # ... etc
]
```

This would require more significant changes but provides fine-grained control over polling frequency.

---

## Verification Plan

### Unit Tests
1. **Test Bulk Read Mode**: Verify existing behavior unchanged
2. **Test Sequential Read Mode**: Verify all registers read individually
3. **Test Partial Failure**: Verify sequential mode continues on individual register failure
4. **Test Retry Logic**: Verify retries work per-register in sequential mode

### Integration Tests
1. **Test Config Flow**: Verify checkbox appears and saves correctly
2. **Test Mode Switching**: Verify bulk vs sequential mode works
3. **Test Cache Population**: Verify gateway cache populated correctly in both modes

### Manual Testing (Real Hardware)
1. **Test Bulk Mode**: Verify normal operation (default)
2. **Test Sequential Mode**: Verify all registers read correctly
3. **Test Fault Isolation**: Simulate a bad register, verify others still read
4. **Performance Test**: Measure time difference between modes

### Success Criteria
- [ ] Bulk mode unchanged (backward compatible)
- [ ] Sequential mode reads registers individually
- [ ] Partial data returned when some registers fail
- [ ] Configuration option works in UI
- [ ] Performance as expected (sequential slower but functional)

---

## Rollback Plan
If issues occur:
1. Default to `sequential_reads=False` maintains current behavior
2. Users can opt-in to sequential mode via config
3. No breaking changes to existing installations

---

## Summary

This is a **minimal change** that:
- Adds an optional configuration for sequential register reads
- Keeps all existing architecture unchanged
- Maintains backward compatibility (bulk mode is default)
- Provides better fault isolation for problematic adapters

**No changes needed to:**
- Entity files (sensor.py, binary_sensor.py, switch.py, etc.)
- Gateway methods
- Modbus protocol layer
