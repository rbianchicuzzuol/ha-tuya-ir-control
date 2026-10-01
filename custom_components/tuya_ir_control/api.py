from __future__ import annotations
import hashlib, hmac, json, time, uuid

class TuyaApiError(Exception):
    pass

class TuyaIRApi:
    def __init__(self, session, endpoint, access_id, access_secret):
        self.s=session; self.endpoint=endpoint.rstrip('/'); self.cid=access_id; self.secret=access_secret; self.token=None; self.exp=0

    def _sign(self, method, path, body="", token=""):
        t=str(int(time.time()*1000)); nonce=uuid.uuid4().hex
        body_hash=hashlib.sha256(body.encode()).hexdigest()
        string_to_sign=f"{method}\n{body_hash}\n\n{path}"
        msg=f"{self.cid}{token}{t}{nonce}{string_to_sign}"
        sign=hmac.new(self.secret.encode(), msg.encode(), hashlib.sha256).hexdigest().upper()
        return {"client_id":self.cid,"sign":sign,"t":t,"sign_method":"HMAC-SHA256","nonce":nonce, **({"access_token":token} if token else {})}

    async def _request(self, method, path, data=None, auth=True):
        if auth: await self._ensure_token()
        body=json.dumps(data,separators=(',',':'),ensure_ascii=False) if data is not None else ""
        headers=self._sign(method,path,body,self.token if auth else "")
        if body: headers['Content-Type']='application/json'
        async with self.s.request(method,self.endpoint+path,headers=headers,data=body or None,timeout=20) as r:
            obj=await r.json(content_type=None)
        if not obj.get('success'):
            raise TuyaApiError(f"{obj.get('code')}: {obj.get('msg')}")
        return obj.get('result')

    async def _ensure_token(self):
        if self.token and time.time()<self.exp-60: return
        result=await self._request('GET','/v1.0/token?grant_type=1',auth=False)
        self.token=result['access_token']; self.exp=time.time()+int(result.get('expire_time',3600))

    async def device(self,d): return await self._request('GET',f'/v1.0/devices/{d}')
    async def remotes(self,d): return await self._request('GET',f'/v2.0/infrareds/{d}/remotes')
    async def keys(self,d,r): return await self._request('GET',f'/v2.0/infrareds/{d}/remotes/{r}/keys')
    async def send_key(self,d,r,category,key_id,key): return await self._request('POST',f'/v2.0/infrareds/{d}/remotes/{r}/raw/command',{'category_id':category,'key_id':key_id,'key':key})

    async def learning_codes(self,d,r): return await self._request('GET',f'/v2.0/infrareds/{d}/remotes/{r}/learning-codes')
    async def send_learning_code(self,d,r,code): return await self._request('POST',f'/v2.0/infrareds/{d}/remotes/{r}/learning-codes',{'code':code})

    async def ac_status(self,d,r): return await self._request('GET',f'/v2.0/infrareds/{d}/remotes/{r}/ac/status')
    async def ac_value(self,d,r,code,value): return await self._request('POST',f'/v2.0/infrareds/{d}/air-conditioners/{r}/command',{'code':code,'value':value})

    async def categories(self,d): return await self._request('GET',f'/v2.0/infrareds/{d}/categories')
    async def brands(self,d,c): return await self._request('GET',f'/v2.0/infrareds/{d}/categories/{c}/brands')
    async def indexes(self,d,c,b): return await self._request('GET',f'/v2.0/infrareds/{d}/categories/{c}/brands/{b}/remote-indexs')
    async def add_remote(self,d,payload): return await self._request('POST',f'/v2.0/infrareds/{d}/remotes',payload)
    async def delete_remote(self,d,r): return await self._request('DELETE',f'/v2.0/infrareds/{d}/remotes/{r}')
    async def rename_remote(self,d,r,name): return await self._request('PUT',f'/v2.0/infrareds/{d}/remotes/{r}',{'remote_name':name})

    # IR learning APIs. API Explorer defines `state` as the boolean request field.
    async def learning_state(self,d,enabled):
        return await self._request('PUT',f'/v2.0/infrareds/{d}/learning-state',{'state': bool(enabled)})

    # Get Learned Remote Control Code requires infrared_id + learning_time.
    async def learned_code(self,d,learning_time):
        return await self._request('GET',f'/v2.0/infrareds/{d}/learning-codes?learning_time={int(learning_time)}')

    # Save Learning Code: saves a DIY learned remote payload (category/brand/name/codes[]).
    async def save_learning(self,d,payload):
        return await self._request('POST',f'/v2.0/infrareds/{d}/learning-codes',payload)
