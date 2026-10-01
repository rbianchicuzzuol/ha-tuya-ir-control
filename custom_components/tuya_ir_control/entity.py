from homeassistant.helpers.entity import Entity
from .const import DOMAIN
class TuyaIREntity(Entity):
    _attr_has_entity_name=True
    def __init__(self, entry_id, hub_id, remote):
        self.entry_id=entry_id; self.hub_id=hub_id; self.remote=remote
        self._attr_device_info={'identifiers':{(DOMAIN,hub_id)},'name':'Tuya IR Control Hub','manufacturer':'Tuya'}
