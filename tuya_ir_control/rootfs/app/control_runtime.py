"""Shared command handling for UI and MQTT; no command is sent on startup."""
import asyncio
import hashlib
import json
import math
import os
import time
from pathlib import Path

MODES={'cool':0,'heat':1,'auto':2,'fan_only':3,'dry':4}
FANS={'auto':0,'low':1,'medium':2,'high':3}

def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    with temp.open('w') as stream:
        os.chmod(temp,0o600)
        json.dump(data,stream,ensure_ascii=False,indent=2)
        stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)

def list_result(result,keys):
    if isinstance(result,list):return result
    if isinstance(result,dict):
        for key in keys:
            if isinstance(result.get(key),list):return result[key]
    raise ValueError("Resposta de catálogo/teclas incompatível.")

def integer(value,lo,hi):
    if isinstance(value,bool):raise ValueError('Valor inválido.')
    try:number=float(value)
    except (TypeError,ValueError):raise ValueError('Valor inválido.') from None
    if not math.isfinite(number) or not number.is_integer() or not lo<=number<=hi:
        raise ValueError(f'Use um número inteiro entre {lo} e {hi}.')
    return int(number)

class Controls:
    def __init__(self,tuya,load_store,state_path='/data/ac_state.json'):
        self.tuya,self.load_store,self.path=tuya,load_store,Path(state_path)
        try:self.saved=json.loads(self.path.read_text())
        except (OSError,ValueError):self.saved={}
        self.saved=self.saved if isinstance(self.saved,dict) else {}
        self.states=self.saved.setdefault(str(tuya.device),{})
        self.catalog=[];self.cloud_error=None;self.last_refresh=0;self.catalog_complete=False
        self.refresh_lock=asyncio.Lock();self.lock=asyncio.Lock();self.mqtt_connected=False;self.mqtt_error=None;self.mqtt_enabled=False

    def ac_state(self,rid):
        state=self.states.get(str(rid),{})
        power=state.get('power');mode=state.get('mode')
        return {'temperature':state.get('temp',24),
                'mode':'off' if power==0 else next((k for k,v in MODES.items() if v==mode),None) if power==1 else None,
                'fan':next((k for k,v in FANS.items() if v==state.get('wind')),None),
                'attributes':{'estado_estimado':True,'origem':'último comando aceito pela Tuya',
                    'ultimo_comando':state.get('updated_at'),'temperatura_inicial':state.get('temp') is None}}

    async def refresh(self,force=False):
        async with self.refresh_lock:
            await self._refresh(force)

    async def _refresh(self,force):
        if not self.tuya.configured():return
        if not force and time.monotonic()-self.last_refresh<60:return
        self.last_refresh=time.monotonic()
        try:
            remotes=list_result(await self.tuya.remotes(),('remotes','remote_list','list'))
            previous={x['remote_id']:x for x in self.catalog}
            result=[];complete=True
            for remote in remotes:
                rid=str(remote.get('remote_id',remote.get('id','')))
                if not rid:continue
                ac=str(remote.get('category_id'))=='5'
                keys=[];ready=ac
                if not ac:
                    try:
                        keys=list_result(await self.tuya.keys(rid),('key_list','keys','list'));ready=True
                    except Exception:
                        keys=previous.get(rid,{}).get('keys',[]);ready=bool(keys);complete=False
                result.append({**remote,'id':'catalog:'+rid,'remote_id':rid,'name':remote.get('remote_name') or 'Controle Tuya',
                               'type':'Ar-condicionado' if ac else 'Catálogo','category_id':remote.get('category_id'),
                               'ac':ac,'source':'catalog','keys':keys,'ready':ready})
            self.catalog=result;self.catalog_complete=complete
            self.cloud_error=None if complete else "Algumas teclas de catálogo não puderam ser atualizadas; dados conhecidos foram preservados."
        except Exception:
            self.catalog_complete=False
            self.cloud_error='Não foi possível atualizar o catálogo Tuya; controles conhecidos foram preservados.'

    def inventory(self):
        local=[]
        for c in self.load_store().get('controls',[]):
            if not c.get('id'):continue
            local.append({**c,'id':'custom:'+str(c['id']),'custom_id':str(c['id']),
                          'remote_id':str(c.get('remote_id') or ''),'source':'custom',
                          'ac':c.get('protocol')=='ac_structured'})
        linked={c['remote_id'] for c in local if c['remote_id']}
        return local+[c for c in self.catalog if c['remote_id'] not in linked]

    def node(self,control):
        return 'tuya_ir_'+hashlib.sha256((str(self.tuya.device)+'|'+control['id']).encode()).hexdigest()[:24]

    def key_id(self,c,k):
        if c['source']=='custom':return str(k['id'])
        value=k.get('key_id',k.get('id'))
        return str(value) if value is not None else hashlib.sha256(str(k.get('key') or k.get('key_name')).encode()).hexdigest()[:20]

    def find(self,cid):
        return next((c for c in self.inventory() if c['id']==cid),None)

    async def _ac(self,rid,code,value):
        result=await self.tuya.ac_command(rid,code,value)
        if result is False:raise RuntimeError('A Tuya não confirmou o envio do comando.')
        state=self.states.setdefault(str(rid),{})
        state[code]=value;state['updated_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        atomic_json(self.path,self.saved)
        return result

    async def send_ac(self,rid,code,value=None):
        if not any(c['ac'] and c['remote_id']==str(rid) for c in self.inventory()):
            await self.refresh(force=True)
        if not any(c['ac'] and c['remote_id']==str(rid) for c in self.inventory()):raise ValueError('Controle AC estruturado não encontrado.')
        async with self.lock:
            if code in ('temp_up','temp_down'):
                start=self.ac_state(rid)['temperature']
                value=integer(start+(1 if code=='temp_up' else -1),16,30);code='temp'
            if code not in ('power','temp','mode','wind'):raise ValueError('Comando AC inválido.')
            limits={'power':(0,1),'temp':(16,30),'mode':(0,4),'wind':(0,3)}
            value=integer(value,*limits[code])
            return await self._ac(str(rid),code,value)

    async def command(self,cid,kind,value):
        c=self.find(cid)
        if not c or not c['remote_id']:raise ValueError('Controle não encontrado ou sem transporte Tuya.')
        if kind.startswith('key_'):
            key=next((k for k in c.get('keys',[]) if self.key_id(c,k)==kind[4:]),None)
            if not key or value!='PRESS':raise ValueError('Tecla ou comando inválido.')
            if c['ac'] or key.get('kind')=='ac':return await self.send_ac(c['remote_id'],key['code'],key.get('value'))
            async with self.lock:
                if c['source']=='custom':result=await self.tuya.send_raw(c['remote_id'],key['code'])
                else:result=await self.tuya.send_key(c['remote_id'],int(c['category_id']),key.get('key_id',key.get('id')),key.get('key') or key.get('key_name') or 'IR')
                if result is False:raise RuntimeError('A Tuya não confirmou o envio do comando.')
                return result
        if not c['ac']:raise ValueError('Este controle usa sinais aprendidos; não aceita temperatura arbitrária.')
        rid=c['remote_id']
        if kind=='temperature':return await self.send_ac(rid,'temp',integer(value,16,30))
        if kind in ('temperature_up','temperature_down'):
            if value!='PRESS':raise ValueError('Comando inválido.')
            return await self.send_ac(rid,'temp_up' if kind.endswith('up') else 'temp_down')
        if kind=='fan':
            if value not in FANS:raise ValueError('Ventilação inválida.')
            return await self.send_ac(rid,'wind',FANS[value])
        if kind=='power':
            if value not in ('ON','OFF'):raise ValueError('Power inválido.')
            return await self.send_ac(rid,'power',1 if value=='ON' else 0)
        if kind=='mode':
            if value=='off':return await self.send_ac(rid,'power',0)
            if value not in MODES:raise ValueError('Modo inválido.')
            async with self.lock:
                await self._ac(rid,'mode',MODES[value])
                return await self._ac(rid,'power',1)
        raise ValueError('Comando desconhecido.')
