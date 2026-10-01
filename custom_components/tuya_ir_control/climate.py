from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from .const import DOMAIN
from .entity import TuyaIREntity

async def async_setup_entry(hass,entry,async_add_entities):
    d=hass.data[DOMAIN][entry.entry_id]
    rs=await d['api'].remotes(d['device_id'])
    async_add_entities([IRClimate(entry.entry_id,d['device_id'],r,d['api']) for r in rs if int(r.get('category_id',0))==5])

class IRClimate(TuyaIREntity,ClimateEntity):
    _attr_temperature_unit=UnitOfTemperature.CELSIUS
    _attr_supported_features=ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes=[HVACMode.OFF,HVACMode.COOL,HVACMode.HEAT,HVACMode.AUTO,HVACMode.DRY,HVACMode.FAN_ONLY]
    _attr_min_temp=16; _attr_max_temp=30; _attr_target_temperature_step=1

    def __init__(self,e,h,r,api):
        super().__init__(e,h,r); self.api=api
        self._attr_name=r['remote_name']; self._attr_unique_id=f"{h}_{r['remote_id']}_climate"
        self._attr_target_temperature=22; self._attr_hvac_mode=HVACMode.COOL

    async def async_added_to_hass(self):
        try:
            st=await self.api.ac_status(self.hub_id,self.remote['remote_id'])
            if st:
                self._attr_target_temperature=float(st.get('temp',22))
                mode=int(st.get('mode',0)); power=str(st.get('power','1')) not in ('0','false','False')
                modes={0:HVACMode.COOL,1:HVACMode.HEAT,2:HVACMode.AUTO,3:HVACMode.FAN_ONLY,4:HVACMode.DRY}
                self._attr_hvac_mode=modes.get(mode,HVACMode.COOL) if power else HVACMode.OFF
        except Exception:
            pass

    async def async_set_temperature(self,**kwargs):
        v=int(kwargs[ATTR_TEMPERATURE])
        await self.api.ac_value(self.hub_id,self.remote['remote_id'],'temp',v)
        self._attr_target_temperature=v; self.async_write_ha_state()

    async def async_set_hvac_mode(self,hvac_mode):
        if hvac_mode==HVACMode.OFF:
            await self.api.ac_value(self.hub_id,self.remote['remote_id'],'power',0)
        else:
            mode_map={HVACMode.COOL:0,HVACMode.HEAT:1,HVACMode.AUTO:2,HVACMode.FAN_ONLY:3,HVACMode.DRY:4}
            await self.api.ac_value(self.hub_id,self.remote['remote_id'],'power',1)
            if hvac_mode in mode_map:
                await self.api.ac_value(self.hub_id,self.remote['remote_id'],'mode',mode_map[hvac_mode])
        self._attr_hvac_mode=hvac_mode; self.async_write_ha_state()
