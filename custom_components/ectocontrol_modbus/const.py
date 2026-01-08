"""Constants for the Ectocontrol Modbus integration."""
from datetime import timedelta

DOMAIN = "ectocontrol_modbus"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"
CONF_NAME = "name"

# Modbus parameters
MODBUS_BAUDRATE = 19200
MODBUS_TIMEOUT = 2.0
MODBUS_RETRY_COUNT = 3

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

# Register addresses
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
