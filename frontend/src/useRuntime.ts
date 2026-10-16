import { useCallback, useEffect, useRef, useState } from 'react';
import { api, APIError, errorMessage, liveProtocols, liveWebsocketURL, setSessionToken, websocketURL } from './api';
import { simulatedPerception, type Backend, type World, type Experiment, type Branch, type Event, type Dict, type SimulatedPerception } from './domain';
import type { components } from './generated/api';
import {workspaceApi} from './workspaceApi';
import {isConnectionMessage} from './apiTransport';
import {expiredRuntimeReference,forgetRuntimeReferences,missingSavedConfiguration} from './runtimeRecovery';

type Session = components['schemas']['SessionResponse'];
type Live = components['schemas']['LiveState'];
const get=(key:string)=>{try{return localStorage.getItem(`vivacity:${key}`);}catch{return null;}};
const put=(key:string,value:string)=>{try{localStorage.setItem(`vivacity:${key}`,value);}catch{/* Optional persistence. */}};
const pending=new Map<string,Promise<Session>>();
function freshToken(){return crypto.randomUUID().replaceAll('-','')+crypto.randomUUID().replaceAll('-','');}
async function ensureSession(backend:Backend,storageKey:string,config?:Dict,fresh=false,configurationId?:string){
  if(!pending.has(storageKey)){
    const work=(async()=>{
      const id=get(`${storageKey}:session`),token=get(`${storageKey}:token`);
      if(!fresh&&id&&token){setSessionToken(token);try{return await api.session(id);}catch(e){if(!(e instanceof APIError&&[403,404].includes(e.status)))throw e;}}
      let configured:Awaited<ReturnType<typeof workspaceApi.start>>|null=null;
      if(configurationId){
        try{configured=await workspaceApi.start(configurationId,config);}
        catch(e){if(!missingSavedConfiguration(e,config))throw e;}
      }
      const capability=configured?.session_token??freshToken();setSessionToken(capability);
      const session=configured?.session??await api.createSession(backend,capability,config);
      put(`${storageKey}:token`,capability);put(`${storageKey}:session`,session.id);return session;
    })().finally(()=>pending.delete(storageKey));pending.set(storageKey,work);
  }
  return pending.get(storageKey)!;
}
export const isBusy=(e:Experiment|null)=>e?.status==='queued'||e?.status==='running';
export function useRuntime(backend:Backend,templateKey="default",initialConfig?:Dict,configurationId?:string,enabled=true){
  const storageKey=`robotics-v2:${backend}:${templateKey}`;
  const [session,setSession]=useState<Session|null>(null),[world,setWorld]=useState<World|null>(null);
  const [observation,setObservation]=useState<Dict|null>(null),[experiment,setExperiment]=useState<Experiment|null>(null);
  const [perception,setPerception]=useState<SimulatedPerception|null>(null);
  const [branches,setBranches]=useState<Branch[]>([]),[events,setEvents]=useState<Event[]>([]);
  const [online,setOnline]=useState(false),[loaded,setLoaded]=useState(false),[mutating,setMutating]=useState(false);
  const [error,setError]=useState<string|null>(null),[epoch,setEpoch]=useState(0);
  const [recoveryNotice,setRecoveryNotice]=useState<string|null>(null);
  const [stream,setStream]=useState<'connecting'|'live'|'reconnecting'|'idle'>('idle');
  const [liveState,setLiveState]=useState<Live|null>(null);
  const [hostPhysicsLimit,setHostPhysicsLimit]=useState<number|null>(null);
  const currentSession=useRef(session);currentSession.current=session;
  const currentWorld=useRef(world);currentWorld.current=world;
  const currentExperiment=useRef(experiment);currentExperiment.current=experiment;
  const lock=useRef(false),generation=useRef(0);
  const inspecting=useRef(false);
  const stagedConfig=useRef<Dict|null>(null);

  const recoverExpired=useCallback(()=>{
    try{forgetRuntimeReferences(localStorage,storageKey);}catch{/* Optional storage. */}
    ++generation.current;
    currentSession.current=null;currentWorld.current=null;currentExperiment.current=null;
    setSession(null);setWorld(null);setExperiment(null);setBranches([]);setEvents([]);setLiveState(null);
    setOnline(false);setLoaded(false);setError(null);
    setRecoveryNotice('The previous run is no longer available on the server. A fresh world will be initialized; press Start experiments to run it.');
    setEpoch(value=>value+1);
  },[storageKey]);

  useEffect(()=>{
    if(!enabled)return;
    let active=true;
    setHostPhysicsLimit(null);
    const probe=()=>api.health().then(health=>{if(active){setHostPhysicsLimit(health.limits?.max_physics_trials??null);clearInterval(retry);}}).catch(()=>{});
    const retry=setInterval(probe,5000);
    probe();
    return()=>{active=false;clearInterval(retry);};
  },[backend,epoch,enabled]);

  const adopt=useCallback(async(s:Session,version:number)=>{
    if(version!==generation.current)return;
    setSession(s);currentSession.current=s;
    if(currentWorld.current?.id!==s.world_id){
      const w=await api.world(s.world_id),state=await api.state(s.world_id);
      if(version!==generation.current)return;
      currentWorld.current=w;put(`${storageKey}:world`,w.id);setWorld(w);setObservation(state.observation as Dict);
      setPerception(simulatedPerception((state.observation as Dict).perception));setLiveState(null);setBranches([]);
    }
    if(!inspecting.current&&s.experiment_id&&currentExperiment.current?.id!==s.experiment_id){
      const e=await api.experiment(s.experiment_id);
      if(version!==generation.current)return;
      currentExperiment.current=e;setExperiment(e);setBranches([]);setLiveState(null);
    }
  },[backend,storageKey]);

  useEffect(()=>{
    if(!enabled)return;
    const version=++generation.current;let active=true,refreshing=false;
    inspecting.current=false;
    stagedConfig.current=initialConfig??null;
    try{
      const saved=JSON.parse(get(`${storageKey}:settings`)??'null');
      if(saved&&typeof saved==='object'&&!Array.isArray(saved))stagedConfig.current=saved as Dict;
    }catch{/* Ignore invalid optional local preferences. */}
    setWorld(null);currentWorld.current=null;setSession(null);currentSession.current=null;
    setExperiment(null);currentExperiment.current=null;setObservation(null);setPerception(null);setBranches([]);setEvents([]);setLiveState(null);setLoaded(false);setError(null);
    const refresh=async()=>{
      if(refreshing||!active||lock.current)return;refreshing=true;
      try{
        const source=currentSession.current?.id;
        if(source){
          const s=await api.session(source);
          if(!active||lock.current||source!==currentSession.current?.id)return;
          await adopt(s,version);
        }else if(currentWorld.current){
          await api.health();
        }else{
          // Opening a lab initializes or restores its world, never an experiment.
          const id=get(`${storageKey}:session`),token=get(`${storageKey}:token`),worldId=get(`${storageKey}:world`);
          let restored:Session|null=null;
          if(id&&token){
            setSessionToken(token);
            try{
              restored=await api.session(id);
              // A reload does not renew an old autonomous run without consent.
              if(['active','stopping'].includes(restored.status))restored=await api.stopSession(id);
            }catch(e){if(!(e instanceof APIError&&[403,404].includes(e.status)))throw e;}
          }
          if(!active||lock.current)return;
          if(restored&&(!worldId||worldId===restored.world_id))await adopt(restored,version);
          else{
            let w:World|null=null;
            if(worldId){try{w=await api.world(worldId);}catch(e){if(!(e instanceof APIError&&[403,404].includes(e.status)))throw e;}}
            w??=await api.create(backend,stagedConfig.current??initialConfig);
            const state=await api.state(w.id);
            if(!active||lock.current||version!==generation.current)return;
            put(`${storageKey}:world`,w.id);currentWorld.current=w;setWorld(w);setObservation(state.observation as Dict);
            setPerception(simulatedPerception((state.observation as Dict).perception));
          }
        }
        if(active&&version===generation.current){setOnline(true);setLoaded(true);setError(previous=>isConnectionMessage(previous)?null:previous);}
      }catch(e){if(active&&version===generation.current){
        if(expiredRuntimeReference(e,Boolean(currentSession.current||currentWorld.current||currentExperiment.current)))recoverExpired();
        else{setError(errorMessage(e));setOnline(false);setLoaded(true);}
      }}
      finally{refreshing=false;}
    };
    refresh();const interval=setInterval(refresh,1000);
    return()=>{active=false;clearInterval(interval);};
  },[backend,storageKey,initialConfig,epoch,adopt,recoverExpired,enabled]);

  useEffect(()=>{
    const id=experiment?.id;if(!id||!enabled)return;
    let active=true,terminal=false,refreshing=false,sequence=-1,eventCursor=0,lastBranches=0;
    let eventSocket:WebSocket|null=null,liveSocket:WebSocket|null=null;
    let reconnect:ReturnType<typeof setTimeout>|null=null;
    const append=(incoming:Event[])=>setEvents(old=>[...new Map([...old,...incoming].map(e=>[e.seq,e])).values()].sort((a,b)=>a.seq-b.seq).slice(-160));
    const measured=(live:Live|null)=>{
      if(!active||!live||live.schema_version!=='vivacity.live/1.0'||live.sequence<=sequence)return;
      sequence=live.sequence;setLiveState(live);setObservation(live.frame as Dict);
    };
    const refresh=async()=>{
      if(!active||refreshing||terminal)return;refreshing=true;
      try{
        const e=await api.experiment(id);
        if(!active)return;setOnline(true);setError(previous=>isConnectionMessage(previous)?null:previous);currentExperiment.current=e;setExperiment(e);
        const batch=await api.events(id,eventCursor);if(active&&batch.length){append(batch);eventCursor=batch.at(-1)!.seq;}
        measured(await api.live(id));
        if(isBusy(e)&&Date.now()-lastBranches>5000){
          const b=await api.branches(id);if(active)setBranches(b);lastBranches=Date.now();
        }
        if(!isBusy(e)){
          const b=await api.branches(id),w=await api.world(e.world_id);
          if(!active)return;setBranches(b);setWorld(w);currentWorld.current=w;
          const state=await api.state(w.id);
          if(active){
            setPerception(simulatedPerception((state.observation as Dict).perception));
            if(sequence<0)setObservation(state.observation as Dict);
          }
          terminal=true;setStream('idle');eventSocket?.close();liveSocket?.close();
        }
      }catch(e){if(active){
        if(expiredRuntimeReference(e)){terminal=true;eventSocket?.close();liveSocket?.close();recoverExpired();}
        else{setError(errorMessage(e));setStream('reconnecting');}
      }}
      finally{refreshing=false;}
    };
    const connect=()=>{
      if(!active||terminal)return;setStream('connecting');
      liveSocket=new WebSocket(liveWebsocketURL(id),liveProtocols());
      liveSocket.onopen=()=>active&&setStream('live');
      liveSocket.onmessage=m=>{try{measured(JSON.parse(m.data) as Live);}catch(e){if(active)setError(errorMessage(e));}};
      liveSocket.onclose=()=>{if(active&&!terminal){setStream('reconnecting');reconnect=setTimeout(connect,2000);}};
      eventSocket?.close();eventSocket=new WebSocket(websocketURL(id,eventCursor),liveProtocols());
      eventSocket.onmessage=m=>{try{const event=JSON.parse(m.data) as Event;if(!active||event.seq<=eventCursor)return;eventCursor=event.seq;append([event]);if(['completed','failed','cancelled'].includes(event.kind))refresh();}catch(e){if(active)setError(errorMessage(e));}};
    };
    refresh();if(isBusy(experiment))connect();
    const poll=setInterval(refresh,1000);
    return()=>{active=false;clearInterval(poll);if(reconnect)clearTimeout(reconnect);liveSocket?.close();eventSocket?.close();};
  },[experiment?.id,recoverExpired,enabled]);

  const perform=useCallback(async(operation:()=>Promise<void>)=>{
    if(lock.current)return false;lock.current=true;setMutating(true);setError(null);setRecoveryNotice(null);
    try{await operation();return true;}catch(e){
      if(expiredRuntimeReference(e))recoverExpired();else setError(errorMessage(e));
      return false;
    }finally{lock.current=false;setMutating(false);}
  },[recoverExpired]);
  const stop=useCallback(async()=>{
    const s=currentSession.current;if(!s||!['active','stopping'].includes(s.status))return;
    let result=await api.stopSession(s.id);setSession(result);currentSession.current=result;
    while(['active','stopping'].includes(result.status)){
      await new Promise(resolve=>setTimeout(resolve,150));result=await api.session(s.id);
      setSession(result);currentSession.current=result;
    }
  },[]);
  const start=()=>perform(async()=>{
    await stop();inspecting.current=false;const s=await ensureSession(backend,storageKey,stagedConfig.current??currentWorld.current?.config,true,configurationId);await adopt(s,generation.current);
  });
  const togglePause=()=>perform(async()=>{
    const s=currentSession.current;if(!s||s.status!=='active')return;
    const next=await(s.pause_requested?api.resumeSession(s.id):api.pauseSession(s.id));
    currentSession.current=next;setSession(next);
  });
  const apply=(config:Dict)=>perform(async()=>{
    await stop();inspecting.current=false;const w=currentWorld.current;
    if(!w)return;
    const changed=await api.environment(w.id,config),state=await api.state(w.id);
    // Retain user-selected physical conditions,
    // so waiting or reloading between Apply and Start does not change the request.
    stagedConfig.current=config;put(`${storageKey}:settings`,JSON.stringify(config));
    currentWorld.current=changed;setWorld(changed);setObservation(state.observation as Dict);
    setPerception(simulatedPerception((state.observation as Dict).perception));setLiveState(null);
    currentSession.current=null;setSession(null);
    if(currentExperiment.current){const e=await api.experiment(currentExperiment.current.id);currentExperiment.current=e;setExperiment(e);}
  });
  const reset=()=>perform(async()=>{
    await stop();const w=currentWorld.current;if(!w)return;
    const resetWorld=await api.reset(w.id),state=await api.state(w.id);
    currentWorld.current=resetWorld;setWorld(resetWorld);setObservation(state.observation as Dict);
    setPerception(simulatedPerception((state.observation as Dict).perception));setLiveState(null);
    if(currentExperiment.current)setExperiment(await api.experiment(currentExperiment.current.id));
  });
  const history=(id:string)=>perform(async()=>{
    await stop();inspecting.current=true;const e=await api.experiment(id),b=await api.branches(id);
    currentExperiment.current=e;setExperiment(e);setBranches(b);
    const batch=await api.events(id);setEvents(batch.slice(-160));
    // Evidence inspection never substitutes a recorded trajectory into the main scene.
  });
  return {world,observation,perception,experiment,branches,events,session,liveState,hostPhysicsLimit,online,loaded,mutating,error,recoveryNotice,stream,
    busy:mutating||isBusy(experiment),active:session?.status==='active'||session?.status==='stopping',
    run:start,stop,togglePause,apply,reset,history,reconnect:()=>setEpoch(e=>e+1),clearError:()=>setError(null)};
}
