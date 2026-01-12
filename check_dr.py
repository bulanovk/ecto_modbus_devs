
try:
    from homeassistant.helpers import device_registry as dr
    print(f"dr has async_get: {hasattr(dr, 'async_get')}")
    print(f"dr has async_get_registry: {hasattr(dr, 'async_get_registry')}")
    print(f"dr dir: {dir(dr)}")
except ImportError as e:
    print(f"ImportError: {e}")
