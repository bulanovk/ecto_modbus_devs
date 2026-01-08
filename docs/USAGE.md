# User Guide & Installation

## Overview

The **Ectocontrol Modbus Adapter v2** integration allows you to monitor and control your gas boiler directly from Home Assistant. It provides sensors for temperature, pressure, and flow readings, along with switches and buttons to enable/disable circuits and commands.

---

## Requirements

### Hardware

- **Home Assistant** (2024.1 or later)
- **Ectocontrol Modbus Adapter v2** connected to your boiler via RS-485
- **Serial connection** to Home Assistant:
  - USB to RS-485 converter (e.g., `CH340` or `FTDI FT232`) connected to Home Assistant host
  - Or native serial port on Raspberry Pi / NUC

### Software

- Home Assistant running on Linux, Raspberry Pi, or equivalent
- HACS installed and configured (recommended)

---

## Installation

### Option 1: Install via HACS (Recommended)

1. **Open Home Assistant** → Settings → Devices & Services → Custom repositories
2. **Add custom repository**:
   - **Repository URL**: `https://github.com/your-username/ectocontrol-modbus-boiler`
   - **Category**: Integration
3. **Click "Install"** from the repository card
4. **Restart Home Assistant**
5. Go to Settings → Devices & Services → **+ Create Automation** → search for **"Ectocontrol"**

### Option 2: Manual Installation

1. **Download** the latest release from [GitHub Releases](https://github.com/your-username/ectocontrol-modbus-boiler/releases)
2. **Extract** `ectocontrol_modbus` folder to `~/.homeassistant/custom_components/`
3. **Restart Home Assistant**
4. Go to Settings → Devices & Services → **+ Create Automation** → search for **"Ectocontrol"**

---

## Configuration

### Step 1: Add Integration

1. **Settings** → **Devices & Services** → **+ Create Automation**
2. Search for **"Ectocontrol Modbus"** and click **Create**

### Step 2: Select Serial Port

- **Port**: Select the serial port connected to your Modbus adapter
  - Linux: `/dev/ttyUSB0`, `/dev/ttyUSB1`
  - Windows: `COM3`, `COM4`
  - Raspberry Pi: `/dev/ttyUSB0` (if using USB converter)

**Common ports**:
```bash
# List available ports (on Linux/macOS)
ls -la /dev/ttyUSB*
ls -la /dev/ttyAMA*

# List available ports (on Windows PowerShell)
[System.IO.Ports.SerialPort]::GetPortNames()
```

### Step 3: Set Slave ID

- **Modbus Slave ID**: Usually `1` (default)
  - Check your boiler documentation or Modbus adapter manual
  - Valid range: 1–32

### Step 4: Provide Name

- **Device Name**: Friendly name for your boiler (e.g., "Kitchen Boiler", "Main Heating")
- This name appears in entity names and the UI

### Step 5: Connection Test

The integration automatically tests the connection by reading the adapter status register (0x0010). If successful, you'll see:

```
✓ Connection successful
```

If it fails:
- Check serial port and baud rate settings
- Verify Modbus adapter is powered on and connected
- Review [Troubleshooting](#troubleshooting)

### Step 6: Add Integration

Click **Create** to finalize. The integration will start polling your boiler immediately.

---

## Available Entities

Once configured, the following entities are automatically created:

### Sensors (Read-Only)

| Entity | Description | Unit | Update |
|--------|-------------|------|--------|
| **CH Temperature** | Heating circuit water temperature | °C | Every 15s |
| **DHW Temperature** | Domestic hot water temperature | °C | Every 15s |
| **Pressure** | System pressure | bar | Every 15s |
| **Flow Rate** | DHW flow rate | L/min | Every 15s |
| **Modulation** | Burner modulation level | % | Every 15s |
| **Outdoor Temperature** | Outside air temperature | °C | Every 15s |
| **CH Setpoint Active** | Currently active heating setpoint | °C | Every 15s |
| **Main Error Code** | Error from boiler (0 if OK) | — | Every 15s |
| **Add Error Code** | Additional error details | — | Every 15s |
| **Manufacturer Code** | Boiler manufacturer code | — | Every 15s |
| **Model Code** | Boiler model code | — | Every 15s |

### Binary Sensors (State Flags)

| Entity | Description | State |
|--------|-------------|-------|
| **Burner On** | Burner ignition active | on/off |
| **Heating Enabled** | Heating circuit enabled | on/off |
| **DHW Enabled** | Hot water circuit enabled | on/off |

### Switches (Control)

| Entity | Description | Action |
|--------|-------------|--------|
| **Heating Enable** | Enable/disable heating circuit | toggle |
| **DHW Enable** | Enable/disable hot water circuit | toggle |

### Numbers (Setpoints & Limits)

| Entity | Description | Range | Step | Unit |
|--------|-------------|-------|------|------|
| **CH Setpoint** | Heating circuit target temperature | -10 to 100 | 0.004 | °C |
| **CH Min Limit** | Minimum allowed heating temperature | 0–100 | 1 | °C |
| **CH Max Limit** | Maximum allowed heating temperature | 0–100 | 1 | °C |
| **DHW Setpoint** | Hot water target temperature | 0–100 | 1 | °C |
| **Max Modulation** | Maximum burner modulation | 0–100 | 1 | % |

### Climate Entity (Thermostat)

| Entity | Description | Modes |
|--------|-------------|-------|
| **Boiler** | Primary climate control | Heat / Off |

**Features**:
- Set target temperature
- View current temperature
- Toggle heating on/off
- See burner activity (heating/idle)

### Buttons (Commands)

| Entity | Description | Action |
|--------|-------------|--------|
| **Reboot Adapter** | Restart the Modbus adapter | Press to reboot |
| **Reset Boiler Errors** | Clear boiler error codes | Press to reset |

---

## Usage Examples

### Example 1: Monitor Temperature in Lovelace

Create a custom card in Lovelace to display boiler temperatures:

```yaml
type: entities
title: Boiler Status
entities:
  - entity_id: sensor.boiler_ch_temperature
    name: CH Temperature
  - entity_id: sensor.boiler_dhw_temperature
    name: DHW Temperature
  - entity_id: sensor.boiler_pressure
    name: Pressure
  - entity_id: binary_sensor.boiler_burner_on
    name: Burner Active
```

### Example 2: Create Automation to Monitor Temperature

```yaml
alias: Boiler Temperature Alert
description: Alert if boiler temperature exceeds threshold
trigger:
  - platform: numeric_state
    entity_id: sensor.boiler_ch_temperature
    above: 80
action:
  - service: persistent_notification.create
    data:
      message: "Boiler temperature is {{ states('sensor.boiler_ch_temperature') }}°C"
      title: "⚠️ High Boiler Temperature"
```

### Example 3: Automation to Adjust Setpoint

```yaml
alias: Reduce Heating in Summer
description: Lower heating setpoint on warm days
trigger:
  - platform: numeric_state
    entity_id: sensor.weather_temperature
    above: 25
action:
  - service: number.set_value
    target:
      entity_id: number.boiler_ch_setpoint
    data:
      value: 40
```

### Example 4: Manual Reboot Command

Call the service directly via Developer Tools:

```yaml
service: button.press
target:
  entity_id: button.boiler_reboot_adapter
```

---

## Troubleshooting

### Integration Not Appearing

**Symptom**: After installation, integration doesn't show in Settings → Devices & Services

**Solution**:
1. Restart Home Assistant completely (Settings → System → Restart)
2. Verify `custom_components/ectocontrol_modbus/` folder exists
3. Check `home-assistant.log` for import errors:
   ```yaml
   logger:
     logs:
       custom_components.ectocontrol_modbus: debug
   ```

### Connection Failed

**Symptom**: "Cannot connect to boiler" error during setup

**Causes & Fixes**:
1. **Wrong serial port**
   - List available ports: `ls /dev/ttyUSB*`
   - Verify USB adapter is connected
   - On Windows, check Device Manager → Ports

2. **Wrong baud rate or slave ID**
   - Check boiler/adapter manual (default: 19200, slave ID 1)
   - Try slave ID 1–5 if unsure

3. **Adapter not powered**
   - Verify power LED on Modbus adapter is lit
   - Check RS-485 wiring to boiler

4. **Serial port permissions (Linux)**
   ```bash
   sudo usermod -a -G dialout homeassistant
   sudo systemctl restart home-assistant
   ```

### Entities Show "Unavailable"

**Symptom**: All sensors show "unavailable" or "unknown"

**Causes**:
1. **Coordinator polling failed**
   - Check `home-assistant.log` for errors
   - Increase polling interval in `const.py` (if boiler is slow)
   - Restart integration: Settings → Devices & Services → Ectocontrol → Reload

2. **Modbus timeout**
   - Verify RS-485 cable quality (reduce cable length if possible)
   - Check for electrical noise near RS-485 lines

3. **Device unavailability**
   - After 3 consecutive polling failures, entities become unavailable
   - Manually reload: Settings → Devices & Services → Ectocontrol → ⋮ → Reload

### "Modbus error" in Logs

**Symptom**: Repeated errors like `Modbus error reading 0x0010`

**Causes**:
1. **CRC mismatch**: Serial cable interference
   - Try shorter or shielded cable
   - Move USB adapter away from power lines

2. **Invalid slave ID**: Boiler doesn't respond to configured slave ID
   - Verify slave ID matches adapter (see manual or configuration)

3. **Baud rate mismatch**: Adapter runs at different baud rate
   - Default: 19200 (check adapter manual)
   - Some adapters allow configuration via dip switches

### Automation Not Triggering

**Symptom**: Automation with `sensor.boiler_*` trigger doesn't fire

**Solution**:
1. Verify sensor updates every 15 seconds (check entity history)
2. Check automation trigger threshold is correct
3. Reload automation: Developer Tools → YAML → Reload Automations

---

## Maintenance

### Regular Monitoring

- Check boiler error codes monthly (Main Error, Add Error sensors)
- Monitor pressure trends (should be stable 1–2 bar)
- Verify CH/DHW temperatures are in expected ranges

### Resetting Error Codes

If boiler displays error code:
1. Go to Home Assistant Dashboard
2. Find **Reset Boiler Errors** button
3. Press it
4. Check error sensors — should return to 0

### Updating Integration

If using HACS:
1. HACS → Custom repositories → Ectocontrol
2. Click **Check for updates**
3. Click **Upgrade** if available
4. Restart Home Assistant

If manual installation:
1. Download latest release
2. Replace `custom_components/ectocontrol_modbus/` folder
3. Restart Home Assistant

---

## Support & Reporting Issues

- **Documentation**: See [docs/](../docs/) folder
- **Bug Reports**: [GitHub Issues](https://github.com/your-username/ectocontrol-modbus-boiler/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/your-username/ectocontrol-modbus-boiler/discussions)
- **Debug Logs**: [Troubleshooting](#troubleshooting) section

---

## FAQ

**Q: Can I control the boiler temperature from Home Assistant?**
A: Yes! Use the `Boiler` climate entity or adjust `CH Setpoint` number entity.

**Q: Does the integration support multiple boilers?**
A: Yes! Add multiple Ectocontrol devices via separate serial ports or by configuring different slave IDs on the same port.

**Q: What's the polling interval?**
A: Default is 15 seconds. Adjust in `const.py` → `DEFAULT_SCAN_INTERVAL` if needed.

**Q: Can I use this on Raspberry Pi?**
A: Yes! Use a USB RS-485 converter connected to any USB port, or use the onboard UART with a hardware converter.

**Q: What if my boiler has a different register layout?**
A: Edit `const.py` and `boiler_gateway.py` to match your boiler's registers. See [BUILD.md](BUILD.md) for adding new sensors.

