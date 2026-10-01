from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN,PLATFORMS
from .api import TuyaIRApi
async def async_setup_entry(hass, entry):
    api=TuyaIRApi(async_get_clientsession(hass),entry.data['endpoint'],entry.data['access_id'],entry.data['access_secret'])
    hass.data.setdefault(DOMAIN,{})[entry.entry_id]={'api':api,'device_id':entry.data['device_id']}
    await hass.config_entries.async_forward_entry_setups(entry,PLATFORMS)
    return True
async def async_unload_entry(hass,entry):
    ok=await hass.config_entries.async_unload_platforms(entry,PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id,None)
    return ok
