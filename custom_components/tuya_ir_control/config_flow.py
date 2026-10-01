import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import *
from .api import TuyaIRApi
class Flow(config_entries.ConfigFlow,domain=DOMAIN):
    VERSION=1
    async def async_step_user(self,user_input=None):
        errors={}
        if user_input:
            try:
                api=TuyaIRApi(async_get_clientsession(self.hass),user_input[CONF_ENDPOINT],user_input[CONF_ACCESS_ID],user_input[CONF_ACCESS_SECRET])
                dev=await api.device(user_input[CONF_DEVICE_ID]); await api.remotes(user_input[CONF_DEVICE_ID])
                await self.async_set_unique_id(user_input[CONF_DEVICE_ID]); self._abort_if_unique_id_configured()
                return self.async_create_entry(title=dev.get('custom_name') or dev.get('name') or 'Tuya IR',data=user_input)
            except Exception: errors['base']='cannot_connect'
        schema=vol.Schema({vol.Required(CONF_ACCESS_ID):str,vol.Required(CONF_ACCESS_SECRET):str,vol.Required(CONF_DEVICE_ID):str,vol.Required(CONF_ENDPOINT,default=DEFAULT_ENDPOINT):str})
        return self.async_show_form(step_id='user',data_schema=schema,errors=errors)
