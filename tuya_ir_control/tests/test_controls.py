import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from aiohttp import web,ClientSession
from aiohttp.test_utils import TestClient,TestServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'rootfs/app'))
from control_runtime import Controls
from mqtt_control import MQTTControls

class Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store={'controls':[{'id':'ac1','name':'Ar do quarto','protocol':'ac_structured','type':'Ar-condicionado','remote_id':'ac-rid','category_id':5,'keys':[{'id':'preset','name':'23 °C','kind':'ac','code':'temp','value':23}]},{'id':'tv1','name':'TV sala','protocol':'raw','remote_id':'tv-rid','category_id':1,'keys':[{'id':'power','name':'Ligar','code':'PRIVATE-IR-CODE'}]}]}
        self.t=SimpleNamespace(device='mock-hub',configured=lambda:True,ac_command=AsyncMock(return_value=True),send_raw=AsyncMock(return_value=True),send_key=AsyncMock(return_value=True),remotes=AsyncMock(return_value=[{'remote_id':'ac-rid','category_id':5,'remote_name':'Ar duplicado'},{'remote_id':'catalog-ac','category_id':5,'remote_name':'Ar catálogo'},{'remote_id':'catalog-tv','category_id':1,'remote_name':'TV catálogo'}]),keys=AsyncMock(return_value={'key_list':[{'key_id':7,'key':'vol+','key_name':'Volume +'}]}))
        self.c=Controls(self.t,lambda:self.store,self.root/'state.json')
        self.m=MQTTControls(self.c,{},None,self.root/'registry.json')
        self.client=SimpleNamespace(publish=AsyncMock(),subscribe=AsyncMock())
    def tearDown(self):self.temp.cleanup()
    async def test_discovery_grouping_and_all_controls(self):
        await self.c.refresh(force=True)
        configs,routes=self.m.discovery()
        climates=[v for k,v in configs.items() if '/climate/' in k]
        self.assertEqual(len(climates),2)
        self.assertEqual(len(configs),9) # 2 climates + 4 step buttons + 3 keys
        self.assertEqual(len({x['unique_id'] for x in configs.values()}),9)
        self.assertEqual(len({tuple(x['device']['identifiers']) for x in configs.values()}),4)
        for x in climates:
            self.assertEqual((x['min_temp'],x['max_temp'],x['temp_step']),(16,30,1))
            self.assertFalse(x['optimistic']);self.assertFalse(x['retain']);self.assertEqual(x['qos'],0)
            self.assertNotIn('current_temperature_topic',x)
        self.assertNotIn('PRIVATE-IR-CODE',str(configs));self.assertTrue(routes)
        self.t.ac_command.assert_not_called();self.t.send_raw.assert_not_called();self.t.send_key.assert_not_called()
    async def test_temperature_and_relative_commands_shared_state(self):
        await self.c.command('custom:ac1','temperature','25.0')
        self.t.ac_command.assert_awaited_with('ac-rid','temp',25)
        await self.c.command('custom:ac1','temperature_up','PRESS')
        self.assertEqual(self.c.ac_state('ac-rid')['temperature'],26)
        await self.c.command('custom:ac1','temperature_down','PRESS')
        self.assertEqual(self.c.ac_state('ac-rid')['temperature'],25)
        self.assertTrue(self.c.ac_state('ac-rid')['attributes']['estado_estimado'])
        restored=Controls(self.t,lambda:self.store,self.root/'state.json')
        self.assertEqual(restored.ac_state('ac-rid')['temperature'],25)
    async def test_rapid_relative_updates_serialized(self):
        await self.c.send_ac('ac-rid','temp',20)
        await asyncio.gather(*(self.c.command('custom:ac1','temperature_up','PRESS') for _ in range(5)))
        self.assertEqual(self.c.ac_state('ac-rid')['temperature'],25)
    async def test_invalid_temperatures_and_boundaries_no_send(self):
        for value in ('nan','inf','23.5','0','31','bad',True):
            with self.assertRaises(ValueError):await self.c.send_ac('ac-rid','temp',value)
        self.t.ac_command.assert_not_called()
        await self.c.send_ac('ac-rid','temp',30);self.t.ac_command.reset_mock()
        with self.assertRaises(ValueError):await self.c.command('custom:ac1','temperature_up','PRESS')
        self.t.ac_command.assert_not_called()
    async def test_false_success_does_not_change_state(self):
        self.t.ac_command.return_value=False
        with self.assertRaises(RuntimeError):await self.c.send_ac('ac-rid','temp',19)
        self.assertEqual(self.c.ac_state('ac-rid')['temperature'],24)
        self.assertIsNone(self.c.ac_state('ac-rid')['attributes']['ultimo_comando'])
    async def test_mode_and_fan_translation(self):
        await self.c.command('custom:ac1','mode','heat')
        self.assertEqual(self.t.ac_command.call_args_list,[unittest.mock.call('ac-rid','mode',1),unittest.mock.call('ac-rid','power',1)])
        self.assertEqual(self.c.ac_state('ac-rid')['mode'],'heat')
        await self.c.command('custom:ac1','fan','medium')
        self.assertEqual(self.c.ac_state('ac-rid')['fan'],'medium')
        await self.c.command('custom:ac1','mode','off')
        self.assertEqual(self.c.ac_state('ac-rid')['mode'],'off')
    async def test_failed_mode_sequence_does_not_claim_power_on(self):
        self.t.ac_command.side_effect=[True,RuntimeError('mock failure')]
        with self.assertRaises(RuntimeError):await self.c.command('custom:ac1','mode','cool')
        self.assertIsNone(self.c.ac_state('ac-rid')['mode'])
    async def test_raw_and_catalog_keys_routed_correctly(self):
        await self.c.refresh(force=True)
        await self.c.command('custom:tv1','key_power','PRESS')
        self.t.send_raw.assert_awaited_once_with('tv-rid','PRIVATE-IR-CODE')
        await self.c.command('catalog:catalog-tv','key_7','PRESS')
        self.t.send_key.assert_awaited_once_with('catalog-tv',1,7,'vol+')
        with self.assertRaises(ValueError):await self.c.command('custom:tv1','temperature','25')
    async def test_retained_and_unknown_mqtt_commands_ignored(self):
        await self.m.sync(self.client)
        _,self.m.routes=self.m.discovery()
        topic=next(k for k,v in self.m.routes.items() if v==('custom:tv1','key_power'))
        for message in (SimpleNamespace(topic=topic,payload=b'PRESS',retain=True),SimpleNamespace(topic='other/hub/command',payload=b'PRESS',retain=False)):
            await self.m.receive(self.client,message)
        self.t.send_raw.assert_not_called();self.t.ac_command.assert_not_called()
        await self.m.receive(self.client,SimpleNamespace(topic=topic,payload=b'PRESS',retain=False))
        self.t.send_raw.assert_awaited_once()
    async def test_deleted_key_command_refused_even_before_refresh(self):
        await self.m.sync(self.client)
        topic=next(k for k,v in self.m.routes.items() if v==('custom:tv1','key_power'))
        self.store['controls'][1]['keys']=[]
        await self.m.receive(self.client,SimpleNamespace(topic=topic,payload=b'PRESS',retain=False))
        self.t.send_raw.assert_not_called();self.assertTrue(self.m.last_command_error)
    async def test_renamed_keeps_id_deleted_publishes_discovery_tombstone(self):
        await self.m.sync(self.client)
        configs,_=self.m.discovery();topic=next(k for k,v in configs.items() if v['name']=='Ligar')
        unique=configs[topic]['unique_id']
        self.store['controls'][1]['keys'][0]['name']='Power sala'
        await self.m.sync(self.client)
        self.assertEqual(self.m.discovery()[0][topic]['unique_id'],unique)
        self.client.publish.reset_mock();self.store['controls'][1]['keys']=[]
        await self.m.sync(self.client)
        self.assertIn(unittest.mock.call(topic,'',qos=1,retain=True),self.client.publish.call_args_list)
    async def test_restart_cloud_failure_does_not_remove_known_entities(self):
        await self.m.sync(self.client)
        known=set(self.m.known)
        fresh=Controls(self.t,lambda:self.store,self.root/'state.json');self.t.remotes.side_effect=RuntimeError('mock network')
        mqtt=MQTTControls(fresh,{},None,self.root/'registry.json')
        self.client.publish.reset_mock();await mqtt.sync(self.client)
        self.assertTrue(known<=mqtt.known)
        self.assertFalse(any(x.args[1]=='' for x in self.client.publish.call_args_list))
        missing_node=self.c.node(next(c for c in self.c.catalog if c['remote_id']=='catalog-ac'))
        self.assertIn(unittest.mock.call(mqtt.base+'/'+missing_node+'/available','offline',qos=1,retain=True),self.client.publish.call_args_list)
    async def test_ha_birth_republishes_without_sending_ir(self):
        await self.m.sync(self.client);self.client.publish.reset_mock()
        await self.m.receive(self.client,SimpleNamespace(topic='homeassistant/status',payload=b'online',retain=False))
        self.assertEqual(len([x for x in self.client.publish.call_args_list if x.args[0].endswith('/config')]),9)
        self.t.send_raw.assert_not_called();self.t.ac_command.assert_not_called()
    async def test_http_temperature_uses_same_state_as_mqtt(self):
        import server
        app=web.Application();app.router.add_post('/api/ac/{rid}/command',server.ac_command);app.router.add_get('/api/ac/{rid}/state',server.ac_state)
        with patch.object(server,'R',self.c):
            async with TestClient(TestServer(app)) as client:
                response=await client.post('/api/ac/ac-rid/command',json={'code':'temp','value':27})
                self.assertTrue((await response.json())['ok'])
                response=await client.get('/api/ac/ac-rid/state')
                self.assertEqual((await response.json())['data']['temperature'],27)
                self.t.ac_command.reset_mock()
                response=await client.post('/api/ac/ac-rid/command',json={'code':'temp','value':42})
                self.assertEqual(response.status,400);self.t.ac_command.assert_not_called()
    async def test_malformed_mqtt_payload_is_not_sent(self):
        await self.m.sync(self.client)
        topic=next(k for k,v in self.m.routes.items() if v==('custom:ac1','temperature'))
        await self.m.receive(self.client,SimpleNamespace(topic=topic,payload=b'{"temperature":25}',retain=False))
        self.t.ac_command.assert_not_called();self.assertTrue(self.m.last_command_error)
    async def test_manual_broker_options(self):
        m=MQTTControls(self.c,{'mqtt_host':'broker.local','mqtt_port':1884,'mqtt_username':'user','mqtt_password':'secret'},None,self.root/'other.json')
        options=await m.broker_options()
        self.assertEqual(options['hostname'],'broker.local');self.assertEqual(options['port'],1884)
        self.assertEqual(options['password'],'secret')
    async def test_invalid_catalog_response_preserves_entities(self):
        await self.m.sync(self.client);known=set(self.m.known)
        self.t.remotes.return_value={'unexpected':'data'}
        await self.c.refresh(force=True);self.client.publish.reset_mock();await self.m.sync(self.client)
        self.assertEqual(self.m.known,known)
        self.assertFalse(any(x.args[1]=='' for x in self.client.publish.call_args_list))
    async def test_catalog_key_failure_preserves_existing_buttons(self):
        await self.m.sync(self.client);known=set(self.m.known)
        self.t.keys.side_effect=RuntimeError('mock network')
        await self.c.refresh(force=True);await self.m.sync(self.client)
        self.assertEqual(self.m.known,known)
        self.assertTrue(self.c.cloud_error)
    async def test_auto_broker_service_credentials(self):
        received=[]
        async def service(request):
            received.append(request.headers.get('Authorization'))
            return web.json_response({'result':'ok','data':{'host':'core-mosquitto','port':'1883','username':'automatic','password':'private','ssl':False}})
        app=web.Application();app.router.add_get('/services/mqtt',service)
        async with TestServer(app) as server,ClientSession() as session:
            class Routed:
                def get(self,url,**kwargs):return session.get(str(server.make_url('/services/mqtt')),**kwargs)
            m=MQTTControls(self.c,{},Routed(),self.root/'newregistry.json')
            with patch.dict('os.environ',{'SUPERVISOR_TOKEN':'test-token'}):options=await m.broker_options()
        self.assertEqual(options['hostname'],'core-mosquitto');self.assertEqual(options['password'],'private')
        self.assertEqual(received,['Bearer test-token'])
    async def test_real_mqtt_client_discovery_and_shutdown_over_local_tcp(self):
        publications=[];subscriptions=[];connections=[]
        async def handle(reader,writer):
            try:
                while True:
                    header=(await reader.readexactly(1))[0];length=0;multiplier=1
                    while True:
                        digit=(await reader.readexactly(1))[0];length+=(digit&127)*multiplier
                        if not digit&128:break
                        multiplier*=128
                    payload=await reader.readexactly(length);kind=header>>4
                    if kind==1:
                        connections.append(payload);writer.write(b'\x20\x02\x00\x00')
                    elif kind==8:
                        size=int.from_bytes(payload[2:4],'big');subscriptions.append(payload[4:4+size].decode());writer.write(b'\x90\x03'+payload[:2]+b'\x00')
                    elif kind==3:
                        size=int.from_bytes(payload[:2],'big');topic=payload[2:2+size].decode();offset=2+size
                        if (header>>1)&3:
                            mid=payload[offset:offset+2];offset+=2;writer.write(b'\x40\x02'+mid)
                        publications.append((topic,payload[offset:].decode(),bool(header&1)))
                    elif kind==12:writer.write(b'\xd0\x00')
                    elif kind==14:break
                    await writer.drain()
            except (asyncio.IncompleteReadError,ConnectionError):pass
            finally:writer.close();await writer.wait_closed()
        server=await asyncio.start_server(handle,'127.0.0.1',0)
        m=MQTTControls(self.c,{'mqtt_host':'127.0.0.1','mqtt_port':server.sockets[0].getsockname()[1]},None,self.root/'tcptest.json')
        task=asyncio.create_task(m.run())
        try:
            async with asyncio.timeout(5):
                while not self.c.mqtt_connected:await asyncio.sleep(.01)
            self.assertEqual(len([x for x in publications if x[0].endswith('/config')]),9)
            self.assertIn(m.base+'/+/command/+',subscriptions)
            self.assertTrue(any(b'offline' in x for x in connections))
            self.t.send_raw.assert_not_called();self.t.ac_command.assert_not_called();self.t.send_key.assert_not_called()
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            server.close();await server.wait_closed()
        self.assertEqual(publications[-1],(m.base+'/availability','offline',True))
    async def test_startup_normalizes_ids_without_overwriting_corrupt_data(self):
        import server
        path=self.root/'controls.json'
        path.write_text('{corrupt existing data')
        with patch.object(server,'DATA',path),patch.object(server,'opts',return_value={'mqtt_enabled':False}),patch.object(server,'R',self.c):
            lifecycle=server.lifecycle({})
            await lifecycle.__anext__();await lifecycle.aclose()
            self.assertEqual(path.read_text(),'{corrupt existing data')
            path.write_text(json.dumps({'controls':[{'name':'Legado','keys':[{'name':'Power','code':'private'}]}]}))
            lifecycle=server.lifecycle({})
            await lifecycle.__anext__();await lifecycle.aclose()
            data=json.loads(path.read_text())
            self.assertTrue(data['controls'][0]['id']);self.assertTrue(data['controls'][0]['keys'][0]['id'])
            self.assertEqual(server.load_store(),data)
        self.t.ac_command.assert_not_called();self.t.send_raw.assert_not_called()
