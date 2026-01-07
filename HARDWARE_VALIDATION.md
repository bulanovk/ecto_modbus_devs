# Hardware Validation Checklist — RS-485 (Ectocontrol Modbus Adapter v2)

Purpose: provide a repeatable checklist to validate wiring, serial settings, and integration behaviour when connecting the Ectocontrol Modbus Adapter v2 (RS-485 Modbus RTU).

Safety & prerequisites
- Power off equipment before wiring changes.
- Use proper PPE if working in utility/boiler cabinets.
- Have a known-good USB↔RS-485 adapter (FTDI or CP210x recommended).
- Tools: multimeter, oscilloscope or logic analyzer (optional), serial terminal program (e.g., `minicom`, `PuTTY`, `mode`/`screen`), Home Assistant test environment.

Wiring & physical checks
- Identify A/B terminals on adapter and converter. Mark polarity.
- Verify RS-485 pair continuity with multimeter (no shorts to ground).
- Check adapter and boiler share a common reference/ground if required by hardware.
- Termination: place 120 Ω termination resistor across A/B at the far end (only at extremes of bus).
- Biasing: ensure proper bias resistors or pull-up/pull-down are present (adapter or interface board may include them). If multiple nodes, use one bias network on bus.
- Cabling: use twisted pair for A/B, keep length and routing away from mains and motor wiring.

Serial settings verification
- Default expected: 19200 baud, 8 data bits, No parity, 1 stop bit (19200 8N1). Confirm device documentation.
- Confirm slave/unit ID used by device (commonly 1–247).
- Use a serial terminal or `mbpoll` / `modpoll` to test basic read:
  - Example read holding registers (address 0x0010, count 1):
    - `modpoll -m rtu -a <unit> -b 19200 -p none -s 1 -r 16 /dev/ttyUSB0` (adjust for tool)
- If you cannot connect, try common alternate baudrates (9600, 38400) if supported.

Half-duplex / Direction control
- Verify the USB↔RS485 adapter supports automatic direction control (recommended).
- If using manual DE/RE pins, ensure driver toggling is implemented or test with adapter that handles it automatically.
- Observe bus with oscilloscope/logic analyzer when issuing requests to ensure TX/RX toggling and expected timing.

Functional tests (step-by-step)
1. At rest, no activity: check bus idle line voltage (depends on biasing).
2. Simple read test (modbus function 0x03): read known register (0x0010).
   - Expect a valid Modbus response; note raw register value.
3. Batch read test: read 23 registers 0x0010..0x0026 and verify expected lengths and plausible values.
4. Write test (if safe): write a non-destructive register (e.g., a setpoint) and read back to verify.
   - If writes affect physical outputs, prepare safe state and monitoring.
5. Service command: trigger integration-level `reboot_adapter`/`reset_boiler_errors` via Home Assistant and verify adapter behavior (if applicable).

Timeout and error handling
- Introduce simulated noise or disconnect the device and verify integration recovers gracefully (timeouts, retries).
- Verify that coordinator retries and logs informative messages when the device is unresponsive.

Logging & diagnostics
- Enable debug logging for the integration (`custom_components.ectocontrol_modbus` logger) during tests.
- Collect Home Assistant logs and raw serial captures (if available) for failed scenarios.
- Use `async_get_config_entry_diagnostics` diagnostics API to capture gateway cache and protocol state.

Troubleshooting checklist
- No response: verify serial settings, wiring polarity, slave ID, and termination/bias.
- CRC/garbage: check parity/stopbits and physical layer noise; confirm termination and shield connections.
- Intermittent responses: check grounding, cable routing, and adapter direction control timing.
- Writes fail: confirm device allows writes to target register, unit ID and any write-protection settings.

Acceptance criteria
- Able to read the full register block (0x0010..0x0026) reliably at configured scan interval.
- Integration entities in Home Assistant reflect expected values and update on polls.
- Writes and service commands complete successfully and device returns to normal operation.
- Clear logs and diagnostics available for future troubleshooting.

Notes
- When performing any write or reboot commands on production boilers, follow local safety procedures and obtain necessary permissions.
- For complex issues, use an oscilloscope or logic analyzer to capture Modbus frames and timing.