"""Native MQTT Discovery for catalog and learned controls."""
import asyncio
import hashlib
import json
import logging
import os
import ssl
from contextlib import suppress
from pathlib import Path
import aiohttp
from control_runtime import atomic_json,MODES,FANS

_LOGGER=logging.getLogger(__name__)

class MQTTControls:
    def __init__(self,controls,options,session,registry='/data/mqtt_registry.json'):
        self.controls,self.opts,self.session=controls,options,session
        hub=hashlib.sha256(str(controls.tuya.device).encode()).hexdigest()[:20]
        self.base='tuya_ir/'+hub;self.client_id='tuya_ir_'+hub
        self.registry=Path(registry)
        try:self.known=set(json.loads(self.registry.read_text()))
        except (OSError,ValueError,TypeError):self.known=set()
        self.config_cache={};self.state_cache={};self.routes={};self.sync_lock=asyncio.Lock()
        self.last_command_error=None

    def discovery(self):
        configs={};routes={}
        for c in self.controls.inventory():
            if not c.get('remote_id'):continue
            node=self.controls.node(c);base=self.base+'/'+node
            device={'identifiers':[node],'name':c.get('name') or 'Controle IR','manufacturer':'Tuya','model':c.get('type') or 'IR','sw_version':'Tuya IR Control 0.4.0'}
            def command(kind,target=None):
                topic=base+'/command/'+kind
                routes[topic]=(c['id'],target or kind)
                return topic
            def config(component,key,name,extra):
                data={'name':name,'unique_id':node+'_'+key,'device':device,'availability':[{'topic':self.base+'/availability'},{'topic':base+'/available'}],'availability_mode':'all',
                      'qos':0,'retain':False,**extra}
                configs['homeassistant/'+component+'/'+node+'/'+key+'/config']=data
            if c['ac']:
                config('climate','climate',None,{
                    'temperature_command_topic':command('temperature'),'temperature_state_topic':base+'/state',
                    'temperature_state_template':'{{ value_json.temperature }}',
                    'mode_command_topic':command('mode'),'mode_state_topic':base+'/state','mode_state_template':'{{ value_json.mode }}',
                    'fan_mode_command_topic':command('fan'),'fan_mode_state_topic':base+'/state','fan_mode_state_template':'{{ value_json.fan }}',
                    'power_command_topic':command('power'),'payload_on':'ON','payload_off':'OFF',
                    'modes':['off',*MODES],'fan_modes':list(FANS),
                    'min_temp':16,'max_temp':30,'temp_step':1,'precision':1,'temperature_unit':'C',
                    'optimistic':False,'json_attributes_topic':base+'/state','json_attributes_template':'{{ value_json.attributes | tojson }}',
                })
                for kind,name in [('temperature_up','Aumentar temperatura'),('temperature_down','Diminuir temperatura')]:
                    config('button',kind,name,{'command_topic':command(kind),'payload_press':'PRESS','icon':'mdi:thermometer-plus' if kind.endswith('up') else 'mdi:thermometer-minus'})
            for k in c.get('keys',[]):
                kid=self.controls.key_id(c,k)
                safe='key_'+hashlib.sha256(kid.encode()).hexdigest()[:20]
                config('button',safe,k.get('name') or k.get('key_name') or k.get('key') or 'Tecla',{
                    'command_topic':command(safe,'key_'+kid),'payload_press':'PRESS','icon':'mdi:remote'})
        return configs,routes

    async def sync(self,client,force=False):
        async with self.sync_lock:
            await self.controls.refresh()
            configs,routes=self.discovery()
            # Only a successful inventory refresh can prove remote deletion.
            # Locals are always authoritative; cloud refresh preserves its cache.
            stale=self.known-set(configs) if self.controls.catalog_complete else set()
            for topic in stale:
                await client.publish(topic,'',qos=1,retain=True)
                self.config_cache.pop(topic,None)
            for topic,config in configs.items():
                encoded=json.dumps(config,ensure_ascii=False)
                if force or self.config_cache.get(topic)!=encoded:
                    await client.publish(topic,encoded,qos=1,retain=True)
                    self.config_cache[topic]=encoded
            self.routes=routes
            known=(self.known-stale)|set(configs)
            if known!=self.known:
                self.known=known;atomic_json(self.registry,sorted(self.known))
            active={self.controls.node(c):c for c in self.controls.inventory() if c.get('remote_id')}
            nodes={topic.split('/')[-3] for topic in self.known}|set(active)
            for node in nodes:
                c=active.get(node)
                ready=c is not None and self.controls.tuya.configured() and (c['source']=='custom' or c.get('ready',True))
                await client.publish(self.base+'/'+node+'/available','online' if ready else 'offline',qos=1,retain=True)
            await self.publish_states(client,force)
            await client.publish(self.base+'/availability','online',qos=1,retain=True)

    async def publish_states(self,client,force=False):
        for c in self.controls.inventory():
            if c['ac'] and c.get('remote_id'):
                topic=self.base+'/'+self.controls.node(c)+'/state'
                encoded=json.dumps(self.controls.ac_state(c['remote_id']),ensure_ascii=False)
                if force or self.state_cache.get(topic)!=encoded:
                    await client.publish(topic,encoded,qos=1,retain=True)
                    self.state_cache[topic]=encoded

    async def receive(self,client,message):
        topic=str(message.topic)
        if topic=='homeassistant/status':
            if message.payload==b'online':await self.sync(client,force=True)
            return
        # Never replay retained actions after reconnect/startup.
        if message.retain or topic not in self.routes:return
        if len(message.payload)>128:return
        try:
            value=message.payload.decode('utf-8').strip()
            cid,kind=self.routes[topic]
            await self.controls.command(cid,kind,value)
            self.last_command_error=None
        except Exception as exc:
            self.last_command_error='Comando não enviado/confirmado. Confira o controle, o valor e a conexão Tuya.'
            _LOGGER.warning('Tuya IR: comando MQTT recusado/falhou (%s).',type(exc).__name__)
        # Report only state actually accepted, including a partially completed
        # mode/power sequence. Failed actions never get an optimistic success.
        await self.publish_states(client)
        await client.publish(self.base+'/command_result',json.dumps({'ok':self.last_command_error is None,'error':self.last_command_error}),qos=0,retain=False)

    async def broker_options(self):
        host=str(self.opts.get('mqtt_host','')).strip()
        if host:
            return {'hostname':host,'port':int(self.opts.get('mqtt_port',1883)),
                    'username':self.opts.get('mqtt_username') or None,'password':self.opts.get('mqtt_password') or None,
                    'tls_context':ssl.create_default_context() if self.opts.get('mqtt_tls') else None}
        token=os.environ.get('SUPERVISOR_TOKEN')
        if not token:raise ValueError('Serviço MQTT automático indisponível.')
        async with self.session.get('http://supervisor/services/mqtt',headers={'Authorization':'Bearer '+token},timeout=aiohttp.ClientTimeout(total=10),allow_redirects=False) as response:
            if response.status!=200:raise ValueError('Serviço MQTT automático indisponível.')
            result=await response.json()
        data=result.get('data',result)
        if result.get('result','ok')!='ok' or not data.get('host'):raise ValueError('Serviço MQTT automático indisponível.')
        return {'hostname':data['host'],'port':int(data['port']),'username':data.get('username') or None,'password':data.get('password') or None,
                'tls_context':ssl.create_default_context() if data.get('ssl') else None}

    async def connected(self,client):
        await client.subscribe('homeassistant/status',qos=0)
        await client.subscribe(self.base+'/+/command/+',qos=0)
        await self.sync(client,force=True)
        self.controls.mqtt_connected=True;self.controls.mqtt_error=None
        async def messages():
            async for message in client.messages:await self.receive(client,message)
        async def updates():
            while True:
                await asyncio.sleep(5)
                await self.sync(client)
        tasks=[asyncio.create_task(messages()),asyncio.create_task(updates())]
        try:
            done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for task in done:task.result()
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)

    async def run(self):
        import aiomqtt
        while True:
            try:
                options=await self.broker_options()
                async with aiomqtt.Client(**options,identifier=self.client_id,keepalive=30,timeout=10,
                        will=aiomqtt.Will(self.base+'/availability','offline',qos=1,retain=True)) as client:
                    try:await self.connected(client)
                    finally:
                        self.controls.mqtt_connected=False
                        with suppress(Exception):await client.publish(self.base+'/availability','offline',qos=1,retain=True,timeout=3)
            except asyncio.CancelledError:raise
            except Exception as exc:
                self.controls.mqtt_connected=False
                self.controls.mqtt_error='Falha no MQTT. Confira o serviço do Supervisor ou configure a conexão manual nas opções do App.'
                _LOGGER.warning('Tuya IR: conexão MQTT falhou (%s); nova tentativa em 15s.',type(exc).__name__)
                await asyncio.sleep(15)
