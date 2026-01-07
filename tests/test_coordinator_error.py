import pytest

from custom_components.ectocontrol_modbus.boiler_gateway import BoilerGateway
from custom_components.ectocontrol_modbus.coordinator import BoilerDataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed


class ProtoNone:
    async def read_registers(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_coordinator_raises_on_no_response():
    proto = ProtoNone()
    gw = BoilerGateway(proto, slave_id=9)
    coord = BoilerDataUpdateCoordinator(hass=None, gateway=gw, name="test")

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
