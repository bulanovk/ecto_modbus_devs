"""Constants for the Ectocontrol Modbus integration."""
from datetime import timedelta

DOMAIN = "ectocontrol_modbus"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"
CONF_NAME = "name"
CONF_DEBUG_MODBUS = "debug_modbus"
CONF_POLLING_INTERVAL = "polling_interval"
CONF_RETRY_COUNT = "retry_count"
CONF_READ_TIMEOUT = "read_timeout"

# Modbus parameters
MODBUS_BAUDRATE = 19200
MODBUS_TIMEOUT = 2.0
MODBUS_RETRY_COUNT = 3
MODBUS_READ_TIMEOUT = 3.0

# Serial port patterns to include (USB adapters, RS-485 converters, hardware serial)
# Linux: ttyUSB* (USB-Serial), ttyACM* (USB CDC), ttyAMA* (Raspberry Pi UART)
# Windows: COM*
# macOS: cu.* or tty.*
SERIAL_PORT_PATTERNS = [
    "/dev/ttyUSB*",   # Linux USB-Serial adapters (FTDI, CP210x, CH340, etc.)
    "/dev/ttyACM*",   # Linux USB CDC devices (Arduino, etc.)
    "/dev/ttyAMA*",   # Raspberry Pi hardware UART
    "/dev/ttyS*",     # Linux hardware serial ports
    "COM*",           # Windows COM ports
    "/dev/cu.*",      # macOS serial ports (call-out)
    "/dev/tty.*",     # macOS serial ports (terminal)
]

# Generic Device Information Registers (0x0000-0x0003)
# Per MODBUS_PROTOCOL.md section 3.0 - common to all Ectocontrol devices
REGISTER_RESERVED = 0x0000
REGISTER_UID = 0x0001           # u24 (3 bytes): unique device identifier
REGISTER_ADDRESS = 0x0002       # MSB: reserved, LSB: device Modbus address (0x01-0x20)
REGISTER_TYPE_CHANNELS = 0x0003 # MSB: device type, LSB: channel count (1-10)

# Device Type Codes (from MODBUS_PROTOCOL.md section 3.0)
DEVICE_TYPE_OPENTHERM_V1 = 0x11     # OpenTherm Adapter v1 (discontinued)
DEVICE_TYPE_OPENTHERM_V2 = 0x14     # OpenTherm Adapter v2 (current)
DEVICE_TYPE_EBUS = 0x15             # eBus Adapter
DEVICE_TYPE_NAVIEN = 0x16           # Navien Adapter
DEVICE_TYPE_TEMP_SENSOR = 0x22      # Temperature Sensor
DEVICE_TYPE_HUMIDITY_SENSOR = 0x23  # Humidity Sensor
DEVICE_TYPE_CONTACT_SENSOR = 0x50   # Universal Contact Sensor
DEVICE_TYPE_CONTACT_SPLITTER = 0x59 # 10-channel Contact Sensor Splitter
DEVICE_TYPE_RELAY_2CH = 0xC0        # 2-channel Relay Control Block
DEVICE_TYPE_RELAY_10CH = 0xC1       # 10-channel Relay Control Block

DEVICE_TYPE_NAMES = {
    0x11: "OpenTherm Adapter v1",
    0x14: "OpenTherm Adapter v2",
    0x15: "eBus Adapter",
    0x16: "Navien Adapter",
    0x22: "Temperature Sensor",
    0x23: "Humidity Sensor",
    0x50: "Contact Sensor",
    0x59: "Contact Splitter 10ch",
    0xC0: "Relay Block 2ch",
    0xC1: "Relay Block 10ch",
}

# Status & Diagnostics Register addresses (0x0010+)
REGISTER_STATUS = 0x0010
REGISTER_VERSION = 0x0011
REGISTER_UPTIME = 0x0012
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
REGISTER_CH_MIN = 0x0033
REGISTER_CH_MAX = 0x0034
REGISTER_DHW_MIN = 0x0035
REGISTER_DHW_MAX = 0x0036
REGISTER_DHW_SETPOINT = 0x0037
REGISTER_MAX_MODULATION = 0x0038
REGISTER_CIRCUIT_ENABLE = 0x0039

REGISTER_COMMAND = 0x0080
REGISTER_COMMAND_RESULT = 0x0081

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
