from homeassistant.components.remote import RemoteEntity
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .entity import TuyaIREntity

async def async_setup_entry(hass,entry,async_add_entities):
    d=hass.data[DOMAIN][entry.entry_id]; remotes=await d['api'].remotes(d['device_id'])
    async_add_entities([IRRemote(entry.entry_id,d['device_id'],r,d['api']) for r in remotes if int(r.get('category_id',0))!=5])

class IRRemote(TuyaIREntity,RemoteEntity):
    def __init__(self,e,h,r,api):
        super().__init__(e,h,r); self.api=api
        self._attr_name=r['remote_name']; self._attr_unique_id=f"{h}_{r['remote_id']}_remote"; self._attr_is_on=True

    async def _all_commands(self):
        standard=[]; learned=[]
        try:
            result=await self.api.keys(self.hub_id,self.remote['remote_id'])
            standard=(result or {}).get('key_list',[]) if isinstance(result,dict) else []
        except Exception:
            pass
        try:
            learned=await self.api.learning_codes(self.hub_id,self.remote['remote_id']) or []
        except Exception:
            pass
        return standard, learned

    async def _send_one(self, cmd):
        standard,learned=await self._all_commands(); wanted=str(cmd).lower()
        k=next((x for x in standard if str(x.get('key','')).lower()==wanted or str(x.get('key_name','')).lower()==wanted),None)
        if k:
            return await self.api.send_key(self.hub_id,self.remote['remote_id'],self.remote['category_id'],k.get('key_id'),k.get('key'))
        k=next((x for x in learned if str(x.get('key','')).lower()==wanted or str(x.get('key_name','')).lower()==wanted),None)
        if k:
            return await self.api.send_learning_code(self.hub_id,self.remote['remote_id'],k['code'])
        raise HomeAssistantError(f'Comando IR não encontrado: {cmd}')

    async def async_send_command(self,command,**kwargs):
        for cmd in command:
            await self._send_one(cmd)

    async def _power(self):
        standard,learned=await self._all_commands()
        aliases=('power','on/off','liga/desliga','on','off')
        for collection in (standard,learned):
            for k in collection:
                if str(k.get('key','')).lower() in aliases or str(k.get('key_name','')).lower() in aliases:
                    if collection is standard:
                        return await self.api.send_key(self.hub_id,self.remote['remote_id'],self.remote['category_id'],k.get('key_id'),k.get('key'))
                    return await self.api.send_learning_code(self.hub_id,self.remote['remote_id'],k['code'])
        raise HomeAssistantError('Este controle não possui uma tecla Power/On-Off identificável. Use remote.send_command com o nome da tecla.')

    async def async_turn_on(self, **kwargs):
        await self._power(); self._attr_is_on=True; self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._power(); self._attr_is_on=False; self.async_write_ha_state()
