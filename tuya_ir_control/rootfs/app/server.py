import asyncio, hashlib, hmac, json, os, time, uuid
from pathlib import Path
from urllib.parse import urlencode
import aiohttp
from aiohttp import web
from control_runtime import Controls, atomic_json, integer

DATA=Path(os.environ.get('TUYA_IR_STORE','/data/custom_controls.json'))
OPTIONS=Path(os.environ.get('TUYA_IR_OPTIONS','/data/options.json'))

def opts():
    try: return json.loads(OPTIONS.read_text())
    except Exception: return {}

def load_store():
    try:
        data=json.loads(DATA.read_text())
        if not isinstance(data,dict): data={'controls':[]}
        data.setdefault('controls',[])
        # Each custom control is independent. Never merge/deduplicate by category_id.
        seen=set()
        for c in data['controls']:
            if not c.get('id') or c.get('id') in seen: c['id']=uuid.uuid4().hex
            seen.add(c['id'])
            c.setdefault('keys',[])
            for k in c['keys']:
                if not k.get('id'):k['id']=uuid.uuid4().hex
        return data
    except Exception: return {'controls':[]}

def save_store(x):
    atomic_json(DATA,x)

class Tuya:
    def __init__(self):
        o=opts(); self.endpoint=o.get('endpoint','').rstrip('/'); self.cid=o.get('access_id',''); self.secret=o.get('access_secret',''); self.device=o.get('device_id',''); self.token=None; self.exp=0
    def configured(self): return all([self.endpoint,self.cid,self.secret,self.device])
    def sign(self,method,path,body='',token=''):
        t=str(int(time.time()*1000)); nonce=uuid.uuid4().hex; bh=hashlib.sha256(body.encode()).hexdigest(); sts=f'{method}\n{bh}\n\n{path}'; msg=f'{self.cid}{token}{t}{nonce}{sts}'
        sig=hmac.new(self.secret.encode(),msg.encode(),hashlib.sha256).hexdigest().upper()
        h={'client_id':self.cid,'sign':sig,'t':t,'sign_method':'HMAC-SHA256','nonce':nonce}
        if token:h['access_token']=token
        if body:h['Content-Type']='application/json'
        return h
    async def request(self,method,path,data=None,auth=True):
        if auth: await self.ensure_token()
        body=json.dumps(data,separators=(',',':'),ensure_ascii=False) if data is not None else ''
        async with aiohttp.ClientSession() as s:
            async with s.request(method,self.endpoint+path,headers=self.sign(method,path,body,self.token if auth else ''),data=body or None,timeout=20) as r:
                obj=await r.json(content_type=None)
        if not obj.get('success'): raise RuntimeError(f"{obj.get('code')}: {obj.get('msg')}")
        return obj.get('result')
    async def ensure_token(self):
        if self.token and time.time()<self.exp-60:return
        z=await self.request('GET','/v1.0/token?grant_type=1',auth=False); self.token=z['access_token']; self.exp=time.time()+int(z.get('expire_time',3600))
    async def remotes(self): return await self.request('GET',f'/v2.0/infrareds/{self.device}/remotes')
    async def keys(self,r): return await self.request('GET',f'/v2.0/infrareds/{self.device}/remotes/{r}/keys')
    async def send_key(self,r,c,kid,key): return await self.request('POST',f'/v2.0/infrareds/{self.device}/remotes/{r}/raw/command',{'category_id':c,'key_id':kid,'key':key})
    async def send_raw(self,r,code): return await self.request('POST',f'/v2.0/infrareds/{self.device}/remotes/{r}/learning-codes',{'code':code})
    async def save_learning(self,p): return await self.request('POST',f'/v2.0/infrareds/{self.device}/learning-codes',p)
    async def update_learning(self,r,p): return await self.request('PUT',f'/v2.0/infrareds/{self.device}/remotes/{r}/learning-codes',p)
    async def learning(self,state): return await self.request('PUT',f'/v2.0/infrareds/{self.device}/learning-state',{'state':bool(state)})
    async def learned(self,lt): return await self.request('GET',f'/v2.0/infrareds/{self.device}/learning-codes?learning_time={int(lt)}')
    async def categories(self): return await self.request('GET',f'/v2.0/infrareds/{self.device}/categories')
    async def brands(self,c): return await self.request('GET',f'/v2.0/infrareds/{self.device}/categories/{c}/brands')
    async def indexes(self,c,b): return await self.request('GET',f'/v2.0/infrareds/{self.device}/categories/{c}/brands/{b}/remote-indexs')
    async def add_remote(self,p): return await self.request('POST',f'/v2.0/infrareds/{self.device}/remotes',p)
    async def ac_test(self,p): return await self.request('POST',f'/v2.0/infrareds/{self.device}/air-conditioners/testing/command',p)
    async def ac_command(self,r,code,value): return await self.request('POST',f'/v2.0/infrareds/{self.device}/air-conditioners/{r}/command',{'code':code,'value':value})
    async def rename(self,r,n): return await self.request('PUT',f'/v2.0/infrareds/{self.device}/remotes/{r}',{'remote_name':n})
    async def delete(self,r): return await self.request('DELETE',f'/v2.0/infrareds/{self.device}/remotes/{r}')

T=Tuya()
R=Controls(T,load_store,os.environ.get("TUYA_IR_AC_STATE","/data/ac_state.json"))
def ok(data=None): return web.json_response({'ok':True,'data':data})
def err(e,status=400): return web.json_response({'ok':False,'error':str(e)},status=status)
def code_from(z):
    if isinstance(z,str): return z
    if isinstance(z,dict):
        for k in ('code','learning_code','key_code'):
            if z.get(k): return z[k]
        for v in z.values():
            c=code_from(v)
            if c:return c
    if isinstance(z,list):
        for v in z:
            c=code_from(v)
            if c:return c
    return ''

async def index(req): return web.FileResponse('/app/index.html')
async def health(req): return web.Response(text='ok')
async def state(req):
    try:
        await R.refresh(force=True)
        inventory=R.inventory()
        rs=[{'remote_id':c['remote_id'],'remote_name':c['name'],'category_id':c['category_id'],'brand_name':c.get('brand_name','Tuya')} for c in inventory if c['source']=='catalog']
        return ok({'configured':T.configured(),'device_id':T.device,'remotes':rs,'controls':load_store()['controls'],
            'mqtt_enabled':R.mqtt_enabled,'mqtt_connected':R.mqtt_connected,'mqtt_error':R.mqtt_error,'cloud_error':R.cloud_error})
    except Exception as e:return err(e)
async def ac_state(req):
    return ok(R.ac_state(req.match_info['rid']))
async def remote_details(req):
    try:
        z=await T.keys(req.match_info['rid']); return ok((z or {}).get('key_list',[]) if isinstance(z,dict) else (z or []))
    except Exception as e:return err(e)
async def send_catalog(req):
    try:
        x=await req.json(); return ok(await T.send_key(x['remote_id'],int(x['category_id']),x.get('key_id'),x['key']))
    except Exception as e:return err(e)
async def learn_start(req):
    try:
        lt=int(time.time()*1000); await T.learning(True); return ok({'learning_time':lt})
    except Exception as e:return err(e)
async def learn_read(req):
    try:
        z=await T.learned(int(req.query['learning_time'])); return ok({'raw':z,'code':code_from(z)})
    except Exception as e:return err(e)
async def learn_stop(req):
    try:return ok(await T.learning(False))
    except Exception as e:return err(e)
async def raw_send(req):
    try:
        x=await req.json(); return ok(await T.send_raw(x['remote_id'],x['code']))
    except Exception as e:return err(e)
async def custom_create(req):
    try:
        x=await req.json(); s=load_store()
        c={'id':uuid.uuid4().hex,'name':x['name'].strip(),'type':x.get('type','DIY'),'reference_type':x.get('reference_type') or x.get('type','DIY'),'category_id':x.get('category_id'),'remote_id':x.get('remote_id'),'protocol':x.get('protocol','raw'),'brand_id':x.get('brand_id'),'brand_name':x.get('brand_name'),'remote_index':x.get('remote_index'),'keys':[]}
        s['controls'].append(c); save_store(s); return ok(c)
    except Exception as e:return err(e)
async def custom_delete(req):
    s=load_store(); target=next((c for c in s['controls'] if c['id']==req.match_info['cid']),None)
    if target and target.get('remote_id'):
        try: await T.delete(target['remote_id'])
        except Exception: pass
    s['controls']=[c for c in s['controls'] if c['id']!=req.match_info['cid']]; save_store(s); return ok()
async def custom_rename(req):
    x=await req.json(); s=load_store()
    for c in s['controls']:
        if c['id']==req.match_info['cid']:
            c['name']=x['name'].strip()
            if c.get('remote_id'):
                try: await T.rename(c['remote_id'],c['name'])
                except Exception: pass
    save_store(s); return ok()
def learning_payload(c, extra=None):
    keys=list(c.get('keys',[]))
    if extra: keys.append(extra)
    payload={'remote_name':c['name'],'codes':[{'category_id':c.get('category_id'),'key_name':k['name'],'key':k.get('key') or k['name'],'code':k['code']} for k in keys]}
    if c.get('category_id') is not None: payload['category_id']=int(c['category_id'])
    payload['brand_name']='DIY'
    return payload
async def ensure_diy_remote(c, code, key_name='Teste'):
    if c.get('remote_id'): return c['remote_id']
    temp={'name':key_name,'key':key_name,'code':code}
    rid=await T.save_learning(learning_payload(c,temp))
    if isinstance(rid,dict): rid=rid.get('remote_id') or rid.get('id') or rid.get('result')
    c['remote_id']=str(rid); return c['remote_id']
async def custom_test(req):
    try:
        x=await req.json(); s=load_store(); c=next((z for z in s['controls'] if z['id']==req.match_info['cid']),None)
        if not c:return err('Controle não encontrado',404)
        rid=await ensure_diy_remote(c,x['code'],x.get('name') or 'Teste'); save_store(s)
        return ok(await T.send_raw(rid,x['code']))
    except Exception as e:return err(e)
async def key_save(req):
    try:
        x=await req.json(); s=load_store()
        for c in s['controls']:
            if c['id']==req.match_info['cid']:
                k={'id':uuid.uuid4().hex,'name':x['name'].strip(),'key':x.get('key') or x['name'].strip(),'code':x['code']}
                if not c.get('remote_id'):
                    await ensure_diy_remote(c,k['code'],k['name'])
                c['keys'].append(k)
                await T.update_learning(c['remote_id'],learning_payload(c))
                save_store(s); return ok(k)
        return err('Controle não encontrado',404)
    except Exception as e:return err(e)
async def key_action(req):
    try:
        x=await req.json(); s=load_store(); cid=req.match_info['cid']; kid=req.match_info['kid']
        for c in s['controls']:
            if c['id']!=cid:continue
            for k in c['keys']:
                if k['id']==kid:
                    if x.get('action')=='send':
                        if c.get('protocol')=='ac_structured' or k.get('kind')=='ac': return ok(await R.send_ac(c['remote_id'],k['code'],k.get('value')))
                        return ok(await T.send_raw(c['remote_id'],k['code']))
                    if x.get('action')=='rename': k['name']=x['name'].strip(); k['key']=k['name']
                    if x.get('action')=='replace': k['code']=x['code']
                    if x.get('action') in ('rename','replace'):
                        if c.get('protocol')!='ac_structured': await T.update_learning(c['remote_id'],learning_payload(c))
                        save_store(s); return ok(k)
            if x.get('action')=='delete':
                c['keys']=[k for k in c['keys'] if k['id']!=kid]
                if c.get('protocol')!='ac_structured' and c.get('remote_id') and c['keys']: await T.update_learning(c['remote_id'],learning_payload(c))
                save_store(s); return ok()
        return err('Tecla não encontrada',404)
    except Exception as e:return err(e)
async def custom_ac_setup(req):
    try:
        x=await req.json()
        payload={'category_id':5,'brand_id':int(x['brand_id']),'remote_index':int(x['remote_index']),'remote_name':x['name'].strip()}
        z=await T.add_remote(payload)
        rid=z
        if isinstance(rid,dict): rid=rid.get('remote_id') or rid.get('id') or rid.get('result')
        if isinstance(rid,dict): rid=rid.get('remote_id') or rid.get('id')
        if not rid: raise RuntimeError(f'A Tuya não retornou remote_id ao adicionar o AC: {z}')
        s=load_store(); c={'id':uuid.uuid4().hex,'name':x['name'].strip(),'type':'Ar-condicionado','reference_type':'Ar-condicionado','category_id':5,'remote_id':str(rid),'protocol':'ac_structured','brand_id':int(x['brand_id']),'brand_name':x.get('brand_name'),'remote_index':int(x['remote_index']),'keys':[]}
        s['controls'].append(c); save_store(s); return ok(c)
    except Exception as e:return err(e)
async def custom_ac_key(req):
    try:
        x=await req.json(); s=load_store(); c=next((z for z in s['controls'] if z['id']==req.match_info['cid']),None)
        if not c or c.get('protocol')!='ac_structured': return err('Controle AC personalizado não encontrado',404)
        k={'id':uuid.uuid4().hex,'name':x['name'].strip(),'kind':'ac','code':x['code'],'value':x.get('value')}
        c['keys'].append(k); save_store(s); return ok(k)
    except Exception as e:return err(e)
async def catalog(req):
    try:
        a=req.query.get('action')
        if a=='categories':z=await T.categories()
        elif a=='brands':z=await T.brands(int(req.query['category_id']))
        elif a=='indexes':z=await T.indexes(int(req.query['category_id']),int(req.query['brand_id']))
        else:raise RuntimeError('Ação inválida')
        return ok(z)
    except Exception as e:return err(e)

async def ac_test(req):
    try:
        x=await req.json()
        p={'remote_index':int(x['remote_index']),'category_id':int(x['category_id']),'code':x.get('code','power'),'value':x.get('value',1)}
        return ok(await T.ac_test(p))
    except Exception as e:return err(e)
async def ac_command(req):
    try:
        x=await req.json(); return ok(await R.send_ac(req.match_info['rid'],x['code'],x.get('value')))
    except Exception as e:return err(e)

async def remote_add(req):
    try:return ok(await T.add_remote(await req.json()))
    except Exception as e:return err(e)
async def remote_action(req):
    try:
        x=await req.json(); rid=req.match_info['rid']
        if x['action']=='rename':z=await T.rename(rid,x['name'])
        elif x['action']=='delete':z=await T.delete(rid)
        else:raise RuntimeError('Ação inválida')
        return ok(z)
    except Exception as e:return err(e)

app=web.Application()
app.add_routes([web.get('/',index),web.get('/health',health),web.get('/api/state',state),web.get('/api/ac/{rid}/state',ac_state),web.get('/api/remotes/{rid}/keys',remote_details),web.post('/api/send',send_catalog),web.post('/api/raw/send',raw_send),web.post('/api/learning/start',learn_start),web.get('/api/learning/read',learn_read),web.post('/api/learning/stop',learn_stop),web.post('/api/custom',custom_create),web.post('/api/custom/{cid}/rename',custom_rename),web.delete('/api/custom/{cid}',custom_delete),web.post('/api/custom/{cid}/test',custom_test),web.post('/api/custom/{cid}/keys',key_save),web.post('/api/custom/{cid}/ac-keys',custom_ac_key),web.post('/api/custom/ac/setup',custom_ac_setup),web.post('/api/custom/{cid}/keys/{kid}',key_action),web.get('/api/catalog',catalog),web.post('/api/remotes',remote_add),web.post('/api/ac/test',ac_test),web.post('/api/ac/{rid}/command',ac_command),web.post('/api/remotes/{rid}',remote_action)])
async def lifecycle(app):
    # Persist normalized legacy IDs once so MQTT identifiers remain stable.
    if DATA.exists():
        try:original=json.loads(DATA.read_text())
        except (OSError,ValueError):original=None
        if isinstance(original,dict) and isinstance(original.get('controls',[]),list):
            normalized=load_store()
            if normalized!=original:save_store(normalized)
    options=opts();R.mqtt_enabled=options.get('mqtt_enabled',True) is True
    async with aiohttp.ClientSession() as session:
        from mqtt_control import MQTTControls
        publisher=MQTTControls(R,options,session,os.environ.get('TUYA_IR_MQTT_REGISTRY','/data/mqtt_registry.json'))
        task=asyncio.create_task(publisher.run()) if R.mqtt_enabled else None
        try:yield
        finally:
            if task is not None:
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)

app.cleanup_ctx.append(lifecycle)
if __name__=='__main__':web.run_app(app,host='0.0.0.0',port=8099)
