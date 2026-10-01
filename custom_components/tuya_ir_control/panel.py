from __future__ import annotations
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN

PANEL_URL='/tuya_ir_control_static'

def _ctx(hass, entry_id=None):
    data=hass.data[DOMAIN]
    if entry_id and entry_id in data: return data[entry_id]
    return next(iter(data.values()))

async def async_setup_panel(hass):
    await hass.http.async_register_static_paths([StaticPathConfig(PANEL_URL, __file__.rsplit('/',1)[0]+'/www', False)])
    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=DOMAIN,
        webcomponent_name='tuya-ir-panel',
        module_url=PANEL_URL + '/tuya-ir-panel.js?v=0.2.6',
        sidebar_title='Tuya IR',
        sidebar_icon='mdi:remote',
        embed_iframe=False,
        require_admin=True,
    )

    @websocket_api.async_response
    async def overview(hass, connection, msg):
        # Keep the first panel request deliberately lightweight. Some Tuya
        # learning-code endpoints are slow/unsupported and used to leave the UI
        # waiting for the entire overview forever.
        d=_ctx(hass,msg.get('entry_id')); api=d['api']; hub=d['device_id']
        remotes=await api.remotes(hub)
        connection.send_result(msg['id'],{'hub':hub,'remotes':remotes or []})
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/overview',vol.Optional('entry_id'):str})(overview))

    @websocket_api.async_response
    async def details(hass, connection, msg):
        d=_ctx(hass,msg.get('entry_id')); api=d['api']; hub=d['device_id']; r=msg['remote']
        out={'keys':[], 'learned':[], 'status':{}}
        if int(r.get('category_id',0))==5:
            try: out['status']=await api.ac_status(hub,r['remote_id']) or {}
            except Exception as e: out['status_error']=str(e)
            # Also expose the catalog keys for AC remotes. Extra functions such as
            # display/LED/swing/turbo may exist even though climate only uses the
            # standardized power/mode/temp/wind API.
            try:
                z=await api.keys(hub,r['remote_id']); out['keys']=(z or {}).get('key_list',[]) if isinstance(z,dict) else []
            except Exception as e: out['keys_error']=str(e)
        else:
            try:
                z=await api.keys(hub,r['remote_id']); out['keys']=(z or {}).get('key_list',[]) if isinstance(z,dict) else []
            except Exception as e: out['keys_error']=str(e)
            # Only query learned codes for DIY remotes. Querying this endpoint for
            # every library remote is unnecessary and can be very slow.
            if int(r.get('brand_id',0) or 0)==999999:
                try: out['learned']=await api.learning_codes(hub,r['remote_id']) or []
                except Exception as e: out['learned_error']=str(e)
        connection.send_result(msg['id'],out)
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/details',vol.Optional('entry_id'):str,vol.Required('remote'):dict})(details))

    @websocket_api.async_response
    async def send(hass,connection,msg):
        d=_ctx(hass); api=d['api']; hub=d['device_id']
        if msg.get('learned'): res=await api.send_learning_code(hub,msg['remote_id'],msg['code'])
        else: res=await api.send_key(hub,msg['remote_id'],msg['category_id'],msg.get('key_id'),msg['key'])
        connection.send_result(msg['id'],res)
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/send',vol.Required('remote_id'):str,vol.Required('category_id'):int,vol.Optional('key_id'):object,vol.Required('key'):str,vol.Optional('learned',default=False):bool,vol.Optional('code'):str})(send))

    @websocket_api.async_response
    async def ac(hass,connection,msg):
        d=_ctx(hass); res=await d['api'].ac_value(d['device_id'],msg['remote_id'],msg['code'],msg['value']); connection.send_result(msg['id'],res)
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/ac',vol.Required('remote_id'):str,vol.Required('code'):str,vol.Required('value'):object})(ac))

    @websocket_api.async_response
    async def rename(hass,connection,msg):
        d=_ctx(hass); res=await d['api'].rename_remote(d['device_id'],msg['remote_id'],msg['name']); connection.send_result(msg['id'],res)
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/rename',vol.Required('remote_id'):str,vol.Required('name'):str})(rename))

    @websocket_api.async_response
    async def delete(hass,connection,msg):
        d=_ctx(hass); res=await d['api'].delete_remote(d['device_id'],msg['remote_id']); connection.send_result(msg['id'],res)
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/delete',vol.Required('remote_id'):str})(delete))

    @websocket_api.async_response
    async def catalog(hass,connection,msg):
        d=_ctx(hass); api=d['api']; hub=d['device_id']; action=msg['action']
        if action=='categories': res=await api.categories(hub)
        elif action=='brands': res=await api.brands(hub,msg['category_id'])
        elif action=='indexes': res=await api.indexes(hub,msg['category_id'],msg['brand_id'])
        else: raise ValueError('ação inválida')
        connection.send_result(msg['id'],res)
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/catalog',vol.Required('action'):vol.In(['categories','brands','indexes']),vol.Optional('category_id'):int,vol.Optional('brand_id'):int})(catalog))

    @websocket_api.async_response
    async def add(hass,connection,msg):
        d=_ctx(hass); res=await d['api'].add_remote(d['device_id'],msg['payload']); connection.send_result(msg['id'],res)
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/add',vol.Required('payload'):dict})(add))

    @websocket_api.async_response
    async def learning(hass,connection,msg):
        d=_ctx(hass); api=d['api']; hub=d['device_id']; action=msg['action']
        if action=='start':
            learning_time=int(msg.get('learning_time') or __import__('time').time()*1000)
            await api.learning_state(hub,True)
            res={'learning_time':learning_time,'active':True}
        elif action=='stop': res=await api.learning_state(hub,False)
        elif action=='read': res=await api.learned_code(hub,msg['learning_time'])
        elif action=='save': res=await api.save_learning(hub,msg['payload'])
        connection.send_result(msg['id'],res)
    websocket_api.async_register_command(hass, websocket_api.websocket_command({vol.Required('type'):f'{DOMAIN}/learning',vol.Required('action'):vol.In(['start','stop','read','save']),vol.Optional('payload'):dict,vol.Optional('learning_time'):int})(learning))

async def async_remove(hass):
    async_remove_panel(hass, DOMAIN)
