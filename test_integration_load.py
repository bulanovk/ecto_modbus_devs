#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to verify the Ectocontrol Modbus integration loads correctly.

This script checks:
1. All modules can be imported
2. Platform async_setup_entry functions exist and are callable
3. Basic entity classes can be instantiated

Run with: python test_integration_load.py
"""
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("Ectocontrol Modbus Integration Load Test")
print("=" * 60)

# Test 1: Import core modules
print("\n[1/4] Testing core module imports...")
try:
    from custom_components.ectocontrol_modbus.const import DOMAIN, REGISTER_CH_TEMP
    from custom_components.ectocontrol_modbus.modbus_protocol import ModbusProtocol
    from custom_components.ectocontrol_modbus.boiler_gateway import BoilerGateway
    from custom_components.ectocontrol_modbus.coordinator import BoilerDataUpdateCoordinator
    print("  [OK] Core modules imported successfully")
    print(f"  [OK] DOMAIN = {DOMAIN}")
    print(f"  [OK] REGISTER_CH_TEMP = 0x{REGISTER_CH_TEMP:04X}")
except ImportError as e:
    print(f"  [FAIL] Failed to import core modules: {e}")
    sys.exit(1)

# Test 2: Import platform modules
print("\n[2/4] Testing platform module imports...")
platforms = ["sensor", "binary_sensor", "switch", "number", "climate", "button"]
for platform in platforms:
    try:
        module = __import__(
            f"custom_components.ectocontrol_modbus.{platform}",
            fromlist=["async_setup_entry"]
        )
        if hasattr(module, "async_setup_entry"):
            print(f"  [OK] {platform}.py: async_setup_entry found")
        else:
            print(f"  [FAIL] {platform}.py: async_setup_entry NOT found")
            sys.exit(1)
    except ImportError as e:
        print(f"  [FAIL] Failed to import {platform}.py: {e}")
        sys.exit(1)

# Test 3: Test entity class instantiation
print("\n[3/4] Testing entity class instantiation...")

# Create fake coordinator and gateway for testing
class FakeProtocol:
    port = "/dev/ttyUSB0"

class FakeGateway:
    slave_id = 1
    protocol = FakeProtocol()
    cache = {}

    def get_ch_temperature(self):
        return 21.5

    def get_burner_on(self):
        return True

    def get_ch_setpoint_active(self):
        return 22.0

    def get_ch_setpoint(self):
        return 21.0

    def get_heating_enabled(self):
        return True

    def get_dhw_enabled(self):
        return False

class FakeCoordinator:
    gateway = FakeGateway()

try:
    from custom_components.ectocontrol_modbus.sensor import BoilerSensor
    sensor = BoilerSensor(FakeCoordinator(), "get_ch_temperature", "Test", "C")
    print(f"  [OK] BoilerSensor instantiated: {sensor._attr_name}")

    from custom_components.ectocontrol_modbus.binary_sensor import BoilerBinarySensor
    binary = BoilerBinarySensor(FakeCoordinator(), "get_burner_on", "Burner")
    print(f"  [OK] BoilerBinarySensor instantiated: {binary._attr_name}")

    from custom_components.ectocontrol_modbus.switch import CircuitSwitch
    switch = CircuitSwitch(FakeCoordinator(), bit=0)
    print(f"  [OK] CircuitSwitch instantiated: {switch._attr_name}")

    from custom_components.ectocontrol_modbus.climate import BoilerClimate
    climate = BoilerClimate(FakeCoordinator())
    print(f"  [OK] BoilerClimate instantiated: {climate._attr_name}")

    from custom_components.ectocontrol_modbus.button import RebootAdapterButton
    button = RebootAdapterButton(FakeCoordinator())
    print(f"  [OK] RebootAdapterButton instantiated: {button._attr_name}")

    from custom_components.ectocontrol_modbus.number import CHSetpointNumber
    number = CHSetpointNumber(FakeCoordinator())
    print(f"  [OK] CHSetpointNumber instantiated: {number._attr_name}")

except Exception as e:
    print(f"  [FAIL] Failed to instantiate entity: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Verify gateway methods exist
print("\n[4/4] Testing BoilerGateway methods...")
required_getters = [
    "get_ch_temperature",
    "get_dhw_temperature",
    "get_pressure",
    "get_flow_rate",
    "get_modulation_level",
    "get_outdoor_temperature",
    "get_ch_setpoint_active",
    "get_ch_setpoint",
    "get_burner_on",
    "get_heating_enabled",
    "get_dhw_enabled",
]

required_setters = [
    "set_ch_setpoint",
    "set_dhw_setpoint",
    "set_max_modulation",
    "set_circuit_enable_bit",
    "reboot_adapter",
    "reset_boiler_errors",
]

missing = []
for method in required_getters + required_setters:
    if not hasattr(BoilerGateway, method):
        missing.append(method)

if missing:
    print(f"  [FAIL] Missing methods: {', '.join(missing)}")
    sys.exit(1)
else:
    print(f"  [OK] All {len(required_getters)} getter methods present")
    print(f"  [OK] All {len(required_setters)} setter methods present")

# Summary
print("\n" + "=" * 60)
print("[SUCCESS] All tests passed!")
print("=" * 60)
print("\nThe integration structure is correct and ready to use.")
print("\nNext steps:")
print("1. Copy the 'ectocontrol_modbus' folder to:")
print("   <home_assistant_config>/custom_components/")
print("2. Restart Home Assistant")
print("3. Add the integration via Settings > Devices & Services")
print("=" * 60)
