from homeassistant.components.button import ButtonEntity
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN
from .entity import TuyaIREntity

async def async_setup_entry(hass,entry,async_add_entities):
    d=hass.data[DOMAIN][entry.entry_id]; out=[]; desired=set()
    for r in await d['api'].remotes(d['device_id']):
        if int(r.get('category_id',0))==5: continue
        try:
            result=await d['api'].keys(d['device_id'],r['remote_id'])
            keys=(result or {}).get('key_list',[]) if isinstance(result,dict) else []
        except Exception: keys=[]
        try: learned=await d['api'].learning_codes(d['device_id'],r['remote_id']) or []
        except Exception: learned=[]

        # Some Tuya DIY remotes expose the same learned command through both APIs.
        # Keep one Home Assistant button per visible command, preferring learned data.
        learned_labels={(k.get('key_name') or k.get('key') or '').strip().casefold() for k in learned}
        seen=set()
        for k in learned:
            label=(k.get('key_name') or k.get('key') or 'IR').strip()
            sig=label.casefold()
            if sig in seen: continue
            seen.add(sig)
            ent=IRButton(entry.entry_id,d['device_id'],r,k,d['api'],True)
            desired.add(ent.unique_id); out.append(ent)
        for k in keys:
            label=(k.get('key_name') or k.get('key') or 'IR').strip()
            sig=label.casefold()
            if sig in seen or sig in learned_labels: continue
            seen.add(sig)
            ent=IRButton(entry.entry_id,d['device_id'],r,k,d['api'],False)
            desired.add(ent.unique_id); out.append(ent)

    # Remove stale button registry entries left by older versions. This only touches
    # button entities owned by this config entry/integration.
    registry=er.async_get(hass)
    for reg in list(er.async_entries_for_config_entry(registry,entry.entry_id)):
        if reg.domain=='button' and reg.platform==DOMAIN and reg.unique_id not in desired:
            registry.async_remove(reg.entity_id)

    async_add_entities(out)

class IRButton(TuyaIREntity,ButtonEntity):
    def __init__(self,e,h,r,k,api,learned):
        super().__init__(e,h,r); self.k=k; self.api=api; self.learned=learned
        label=k.get('key_name') or k.get('key') or 'IR'
        self._attr_name=f"{r['remote_name']} {label}"
        kid=k.get('learn_id') if learned else k.get('key_id',k.get('id'))
        # If Tuya omits an ID for a learned key, use its stable code/key as fallback.
        if kid is None: kid=k.get('code') or k.get('key') or label
        self._attr_unique_id=(f"{h}_{r['remote_id']}_learned_{kid}" if learned else f"{h}_{r['remote_id']}_{kid}")

    async def async_press(self):
        if self.learned:
            await self.api.send_learning_code(self.hub_id,self.remote['remote_id'],self.k['code'])
        else:
            await self.api.send_key(self.hub_id,self.remote['remote_id'],self.remote['category_id'],self.k.get('key_id'),self.k.get('key'))
