import test from 'node:test';
import assert from 'node:assert/strict';
import {fetchRuntime,runtimeEndpoints,runtimeSocketURL,CONNECTION_ERROR,TIMEOUT_ERROR,isConnectionMessage} from '../frontend/src/apiTransport.ts';
import {expiredRuntimeReference,forgetRuntimeReferences,missingSavedConfiguration} from '../frontend/src/runtimeRecovery.ts';
import {APIError} from '../frontend/src/apiResponse.ts';
const noWait=async()=>{};

test('production HTTP stays on the demo origin and streams retain the backend',()=>{
  const endpoints=runtimeEndpoints(true,'https://vivacity-runtime.onrender.com/','https://demo.tryvivacity.com');
  assert.equal(endpoints.http,'https://demo.tryvivacity.com/runtime');
  assert.equal(runtimeSocketURL(endpoints.backend,'example','events',9),'wss://vivacity-runtime.onrender.com/v1/experiments/example/events?after=9');
  assert.equal(runtimeSocketURL(endpoints.backend,'example','live'),'wss://vivacity-runtime.onrender.com/v1/experiments/example/live');
});
test('local development retains the explicitly configured backend',()=>{
  assert.equal(runtimeEndpoints(false,'http://localhost:8000/','http://localhost:5173').http,'http://localhost:8000');
  assert.equal(runtimeEndpoints(false,undefined,'http://localhost:5173').http,'http://127.0.0.1:8000');
});
test('production-build preview uses the local proxy and native local socket',()=>{
  const endpoints=runtimeEndpoints(true,undefined,'http://127.0.0.1:5173');
  assert.equal(endpoints.http,'http://127.0.0.1:5173/runtime');
  assert.equal(runtimeSocketURL(endpoints.backend,'example','live'),'ws://127.0.0.1:8000/v1/experiments/example/live');
});
test('a read recovers from a transport failure without losing capability headers',async()=>{
  let attempts=0;
  const response=await fetchRuntime('/runtime/health',{headers:{'X-Session-Token':'test-capability'}},{wait:noWait,fetcher:async(url,init)=>{
    assert.equal(url,'/runtime/health');assert.equal(init.cache,'no-store');assert.equal(init.headers['X-Session-Token'],'test-capability');
    if(++attempts===1)throw new TypeError('Failed to fetch');return new Response('{"status":"ok"}');
  }});
  assert.equal(attempts,2);assert.deepEqual(await response.json(),{status:'ok'});
});
test('read recovery is bounded and gives an actionable connection error',async()=>{
  let attempts=0;
  await assert.rejects(()=>fetchRuntime('/runtime/health',{}, {wait:noWait,fetcher:async()=>{attempts++;throw new TypeError('Failed to fetch');}}),{message:CONNECTION_ERROR});
  assert.equal(attempts,3);
});
test('temporary upstream gateway errors are retried for reads',async()=>{
  let attempts=0;
  const response=await fetchRuntime('/runtime/health',{}, {wait:noWait,fetcher:async()=>new Response('upstream',{status:++attempts<3?503:200})});
  assert.equal(response.status,200);assert.equal(attempts,3);
});
test('validation errors are returned immediately and retain their body',async()=>{
  let attempts=0;
  const response=await fetchRuntime('/runtime/v1/worlds',{}, {fetcher:async()=>{attempts++;return new Response('{"detail":"invalid config"}',{status:422});}});
  assert.equal(attempts,1);assert.deepEqual(await response.json(),{detail:'invalid config'});
});
test('mutations are never repeated after a lost response or gateway error',async()=>{
  for(const method of ['POST','PATCH']){
    let attempts=0;
    await assert.rejects(()=>fetchRuntime('/runtime/v1/worlds',{method,body:'{}'},{fetcher:async()=>{attempts++;throw new TypeError('lost response');}}),{message:CONNECTION_ERROR});
    assert.equal(attempts,1);
    const response=await fetchRuntime('/runtime/v1/worlds',{method},{fetcher:async()=>{attempts++;return new Response('upstream',{status:503});}});
    assert.equal(response.status,503);assert.equal(attempts,2);
  }
});
test('caller cancellation is preserved without retrying',async()=>{
  const controller=new AbortController();controller.abort();let attempts=0;
  await assert.rejects(()=>fetchRuntime('/runtime/health',{signal:controller.signal},{fetcher:async(url,init)=>{attempts++;init.signal.throwIfAborted();}}),{name:'AbortError'});
  assert.equal(attempts,1);
});
test('a bounded timeout explains the startup delay',async()=>{
  let attempts=0;
  await assert.rejects(()=>fetchRuntime('/runtime/health',{}, {timeoutMs:5,wait:noWait,fetcher:async(url,init)=>{
    attempts++;
    return await new Promise((resolve,reject)=>{
      const hold=setTimeout(()=>resolve(new Response('unexpected')),100);
      init.signal.addEventListener('abort',()=>{clearTimeout(hold);reject(init.signal.reason);},{once:true});
    });
  }}),{message:TIMEOUT_ERROR});
  assert.equal(attempts,3);
});
test('recovery clears transport notices while retaining physics validation errors',()=>{
  for(const message of [CONNECTION_ERROR,TIMEOUT_ERROR,'Failed to fetch','503: The simulation service is temporarily unavailable. Try again.'])assert.equal(isConnectionMessage(message),true);
  assert.equal(isConnectionMessage('422: object exceeds the gripper aperture'),false);
});
test('missing runtime records trigger recovery; ordinary transport and physics errors do not',()=>{
  for(const status of [403,404])assert.equal(expiredRuntimeReference(new APIError(status,'record not found')),true);
  for(const status of [422,429,500,503])assert.equal(expiredRuntimeReference(new APIError(status,'request failed')),false);
  assert.equal(expiredRuntimeReference(new TypeError('Failed to fetch')),false);
});
test('a missing asset during first world creation is an error, not an endless expired-run reset',()=>{
  assert.equal(expiredRuntimeReference(new APIError(404,'missing imported asset'),false),false);
});
test('expired run recovery preserves settings and other runtime identities',()=>{
  const values=new Map([
    ['vivacity:example:session','old-session'],['vivacity:example:token','old-token'],['vivacity:example:world','old-world'],
    ['vivacity:example:settings','{"mass":0.06}'],['vivacity:other:session','other-session'],['vivacity:workspace-capability','workspace-token']]);
  forgetRuntimeReferences({removeItem:key=>values.delete(key)},'example');
  assert.deepEqual([...values.keys()],['vivacity:example:settings','vivacity:other:session','vivacity:workspace-capability']);
});
test('an expired saved configuration can use known physical settings, never bypassing ownership',()=>{
  assert.equal(missingSavedConfiguration(new APIError(404,'missing'),{task:'pick_place'}),true);
  assert.equal(missingSavedConfiguration(new APIError(404,'missing'),undefined),false);
  assert.equal(missingSavedConfiguration(new APIError(403,'forbidden'),{task:'pick_place'}),false);
});
