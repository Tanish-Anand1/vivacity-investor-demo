import {useEffect,useRef,useState,type FormEvent} from 'react';
import {Canvas} from '@react-three/fiber';
import {API,errorMessage} from './api';
import {fetchRuntime} from './apiTransport';
import {readAPIResponse} from './apiResponse';
import {workspaceToken} from './workspaceApi';
import {buildAssets,type Assets,type Manifest} from './RobotAssets';
import {ModelScene,type Frame} from './HumanoidLab';
import SceneBoundary from './SceneBoundary';
import './humanoidLab.css';
import './contactLab.css';

const root='/v1/robotics/contact';
const terminal=new Set(['completed','failed','cancelled','interrupted']);
type Result={task_success:boolean;failure_reason:string|null;controller:string;model_sha256:string;measurements:Measurements};
type Measurements={minimum_hold_share?:number;hold_samples?:number;maximum_actuator_torque_fraction?:number;last_measurement?:{
  destination_error_m?:number;parcel_position_m?:number[];parcel_speed_m_s?:number;
  support?:{left_vertical_n:number;right_vertical_n:number;other_vertical_n:number}}};
type Job={id:string;task:string;status:string;steps_completed:number;current_phase:string|null;world_version:string|null;
  config:Record<string,unknown>;result:Result|null;error:string|null;partial_measurements:NonNullable<Measurements['last_measurement']>};
type Entries={seq:number;frame:Frame}[];
type Delta={status:string;frames:Entries;next_cursor:number;steps_completed:number;current_phase:string|null;partial_measurements:Job['partial_measurements']};
type Scene=Manifest&{mesh_buffer_sha256:string;initial_frame?:Frame;mesh_buffer_url?:string;world_version?:string};
type Comparison={same_world_version:boolean;trials:Job[]};
type Config={source_xy_m:[number,number];destination_xy_m:[number,number];parcel:{mass_kg:number;sliding_friction:number;dimensions_m:[number,number,number]};seed:number};
const initialConfig:Config={source_xy_m:[.32,0],destination_xy_m:[.4,0],parcel:{mass_kg:.5,sliding_friction:.8,dimensions_m:[.18,.18,.16]},seed:7};
const storageKey='vivacity-contact-last-trial-v1';
const wait=(ms:number)=>new Promise(resolve=>setTimeout(resolve,ms));
const number=(value:number|undefined,digits=3)=>value===undefined||!Number.isFinite(value)?'—':value.toFixed(digits);
const inputValue=(value:number)=>Number.isFinite(value)?value:'';

async function request<T>(path:string,method='GET',body?:unknown,signal?:AbortSignal):Promise<T>{
  const response=await fetchRuntime(API+root+path,{method,signal,headers:{'X-Workspace-Token':workspaceToken(),...(body===undefined?{}:{'Content-Type':'application/json'})},
    ...(body===undefined?{}:{body:JSON.stringify(body)})},{timeoutMs:60000});
  return readAPIResponse(response) as Promise<T>;
}
async function checkedAssets(scene:Scene,buffer:ArrayBuffer){
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),v=>v.toString(16).padStart(2,'0')).join('');
  if(hash!==scene.mesh_buffer_sha256)throw new Error('The render geometry checksum does not match this physical world.');
  return buildAssets(scene,buffer);
}

export default function ContactLab(){
  const [enabled,setEnabled]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState<string|null>(null);
  const [notice,setNotice]=useState<string|null>(null),[retry,setRetry]=useState(0),[mutating,setMutating]=useState(false);
  const [config,setConfig]=useState<Config>(initialConfig),[task,setTask]=useState('g1_constrained_carton');
  const [job,setJob]=useState<Job|null>(null),[history,setHistory]=useState<Job[]>([]),[selected,setSelected]=useState<string[]>([]);
  const [comparison,setComparison]=useState<Comparison|null>(null);
  const [assets,setAssets]=useState<Assets|null>(null),[sceneFor,setSceneFor]=useState(''),[frames,setFrames]=useState<Frame[]>([]);
  const [replaying,setReplaying]=useState(false),[time,setTime]=useState(0);
  const cursor=useRef(0),liveFrames=useRef<Frame[]>([]),currentJob=useRef<Job|null>(job);
  currentJob.current=job;
  const busy=!!job&&!terminal.has(job.status),paused=job?.status==='paused';
  const readyScene=!!assets&&sceneFor===(job?.id??'preview');
  const measured:Measurements|undefined=job?.result?.measurements??(job?{last_measurement:job.partial_measurements}:undefined);

  async function refreshHistory(){setHistory(await request<Job[]>('/experiments'));}
  function selectJob(value:Job){
    setReplaying(false);setFrames([]);liveFrames.current=[];cursor.current=0;setTime(0);setJob(value);
    try{localStorage.setItem(storageKey,value.id);}catch{/* Persistence remains server-side. */}
  }
  useEffect(()=>{const controller=new AbortController();let cancelled=false;
    async function load(){try{
      setLoading(true);
      const caps=await request<{enabled:boolean}>('/capabilities','GET',undefined,controller.signal);
      if(cancelled)return;setEnabled(caps.enabled);
      if(caps.enabled){
        const items=await request<Job[]>('/experiments','GET',undefined,controller.signal);
        if(cancelled)return;setHistory(items);
        let saved:string|null=null;try{saved=localStorage.getItem(storageKey);}catch{/* Optional browser convenience. */}
        const existing=items.find(item=>item.id===saved);
        if(existing&&!currentJob.current)selectJob(existing);
      }
      if(!currentJob.current){
        const sceneResponse=await fetch('/vivacity/contact-preview.json',{signal:controller.signal});
        if(!sceneResponse.ok)throw new Error('The native model preview is unavailable.');
        const scene=await sceneResponse.json() as Scene;
        const response=await fetch(scene.mesh_buffer_url!,{signal:controller.signal});
        if(!response.ok)throw new Error('The licensed robot geometry is unavailable.');
        const built=await checkedAssets(scene,await response.arrayBuffer());
        if(cancelled){built.geometry.forEach(g=>g.dispose());return;}
        if(!currentJob.current){setAssets(built);setSceneFor('preview');setFrames(scene.initial_frame?[scene.initial_frame]:[]);}
        else built.geometry.forEach(g=>g.dispose());
      }
      if(!cancelled)setError(null);
    }catch(e){if(!cancelled)setError(errorMessage(e));}finally{if(!cancelled)setLoading(false);}}
    void load();return()=>{cancelled=true;controller.abort();};
  },[retry]);
  useEffect(()=>()=>{assets?.geometry.forEach(g=>g.dispose());},[assets]);

  useEffect(()=>{if(!job?.id)return;const id=job.id,controller=new AbortController();let disposed=false,next=0,sceneLoaded=false;
    liveFrames.current=[];setFrames([]);setSceneFor('');
    async function follow(){while(!disposed){try{
      const delta=await request<Delta>(`/experiments/${id}/frames?cursor=${next}&limit=32`,'GET',undefined,controller.signal);
      if(disposed)return;
      for(const entry of delta.frames){
        if(entry.seq!==next)throw new Error('The runtime frame sequence has a gap. Reconnect to reload the persisted trace.');
        if(!liveFrames.current.length){cursor.current=entry.frame.time_s;setTime(cursor.current);}
        liveFrames.current.push(entry.frame);next++;
      }
      if(delta.next_cursor!==next)throw new Error('The runtime frame cursor is inconsistent.');
      if(delta.frames.length)setFrames([...liveFrames.current]);
      setJob(current=>current?.id===id?{...current,status:delta.status,steps_completed:delta.steps_completed,
        current_phase:delta.current_phase,partial_measurements:delta.partial_measurements}:current);
      if(!sceneLoaded&&liveFrames.current.length){
        const scene=await request<Scene>(`/experiments/${id}/scene`,'GET',undefined,controller.signal);
        const response=await fetchRuntime(API+root+`/experiments/${id}/meshes`,{signal:controller.signal,
          headers:{'X-Workspace-Token':workspaceToken()}},{timeoutMs:60000});
        if(!response.ok)throw new Error('The compiled scene meshes could not be loaded.');
        const built=await checkedAssets(scene,await response.arrayBuffer());
        if(disposed){built.geometry.forEach(g=>g.dispose());return;}
        setAssets(built);setSceneFor(id);sceneLoaded=true;
      }
      setError(null);
      if(delta.status==='paused'||terminal.has(delta.status)){
        cursor.current=liveFrames.current.at(-1)?.time_s??0;setTime(cursor.current);
      }
      if(terminal.has(delta.status)&&delta.frames.length<32){
        const final=await request<Job>(`/experiments/${id}`,'GET',undefined,controller.signal);
        if(disposed)return;setJob(final);await refreshHistory();return;
      }
      if(delta.frames.length<32)await wait(400);
    }catch(e){if(disposed)return;setError(errorMessage(e));await wait(2000);}}}
    void follow();return()=>{disposed=true;controller.abort();};
  },[job?.id,retry]);

  useEffect(()=>{if(!replaying&&(!busy||paused))return;let raf=0,previous=performance.now(),lastDisplay=0;
    const tick=(now:number)=>{
      const available=frames.at(-1)?.time_s??0;
      cursor.current=Math.min(available,cursor.current+Math.min(.1,(now-previous)/1000));previous=now;
      if(now-lastDisplay>80){setTime(cursor.current);lastDisplay=now;}
      if(replaying&&cursor.current>=available){setReplaying(false);setTime(cursor.current);return;}
      raf=requestAnimationFrame(tick);
    };raf=requestAnimationFrame(tick);return()=>cancelAnimationFrame(raf);
  },[busy,paused,replaying,frames]);

  async function action(operation:()=>Promise<void>){
    if(mutating)return;setMutating(true);setError(null);setNotice(null);
    try{await operation();}catch(e){setError(errorMessage(e));}finally{setMutating(false);}
  }
  function run(event:FormEvent){event.preventDefault();void action(async()=>{
    const created=await request<Job>('/experiments','POST',{task,config});selectJob(created);await refreshHistory();
  });}
  function control(command:string){void action(async()=>{setJob(await request<Job>(`/experiments/${job!.id}/${command}`,'POST'));});}
  function fork(){void action(async()=>{
    const branch=await request<Job>(`/experiments/${job!.id}/fork`,'POST',{});
    setNotice(`Fork ${branch.id.slice(0,8)} is queued from this checkpoint. Resume the original to release the shared worker.`);
    await refreshHistory();
  });}
  function replay(){void action(async()=>{
    const saved=await request<{frames:Entries}>(`/experiments/${job!.id}/replay`);
    if(!saved.frames.length)throw new Error('This trial has no recorded physics frames.');
    setFrames(saved.frames.map(item=>item.frame));cursor.current=saved.frames[0].frame.time_s;
    setTime(cursor.current);setReplaying(true);
  });}
  function download(){void action(async()=>{
    const report=await request<unknown>(`/experiments/${job!.id}/export`);
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download=`contact-${job!.id}.json`;link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  });}
  function location(kind:'source_xy_m'|'destination_xy_m',index:number,value:number){
    setConfig(previous=>({...previous,[kind]:previous[kind].map((v,i)=>i===index?value:v) as [number,number]}));
  }
  function dimension(index:number,value:number){setConfig(previous=>({...previous,parcel:{...previous.parcel,
    dimensions_m:previous.parcel.dimensions_m.map((v,i)=>i===index?value:v) as [number,number,number]}}));}
  const outcome=job?.result?(job.result.task_success?'Placement completed in simulation':`Trial failed: ${job.result.failure_reason??job.error??'See measured report'}`):
    job&&terminal.has(job.status)?`${job.status==='cancelled'?'Trial cancelled':'Trial failed'}: ${job.error??job.status}. The final received state is preserved.`:
    job?`${job.status.replaceAll('_',' ')} · ${job.current_phase??'preparing'} · ${job.steps_completed} measured steps`:'Model keyframe. No experiment has started.';

  return <section className="humanoid-lab contact-lab" aria-labelledby="contact-title">
    <div className="humanoid-heading"><div><span className="eyebrow">Physical Truth / contact research</span><h1 id="contact-title">Two hands. Measured support.</h1>
      <p>A bounded G1 carton experiment. Change a condition, run native physics, and inspect what actually happened. This release is experimental.</p></div><a className="secondary" href="/works">Existing humanoid lab</a></div>
    {error&&<div role="alert" className="humanoid-error"><span>{error}</span><button type="button" className="secondary" onClick={()=>setRetry(v=>v+1)}>Reconnect</button></div>}
    {notice&&<p role="status">{notice}</p>}
    {!loading&&!enabled&&<p role="status">Contact research is disabled on this runtime. No simulation will start.</p>}
    <div className="humanoid-layout"><div className="humanoid-primary">
      <div className="humanoid-viewport" role="region" aria-label="Native G1 and carton physical scene" data-model-hash={readyScene?assets?.manifest.model_hash:undefined}>
        {readyScene&&<SceneBoundary><Canvas frameloop="demand" shadows dpr={[1,1.5]} camera={{position:[2,-2,1.65],up:[0,0,1],fov:43}}>
          <ModelScene assets={assets!} frames={frames} cursor={cursor} playing={replaying||(busy&&!paused)} robotId="unitree_g1" time={time}/>
        </Canvas></SceneBoundary>}
      </div>
      {!readyScene&&<p role="status">Loading the matching compiled geometry…</p>}
      <div className="humanoid-playback"><div><strong data-testid="contact-time">{time.toFixed(2)} s</strong>
        <span>{replaying?'Replay of received physics frames':busy?(paused?'Physics paused at a committed checkpoint':'Live backend state; waiting when no newer frame is available'):job?'Measured final state. Replay starts only when selected.':'Native model keyframe'}</span></div>
        {job&&terminal.has(job.status)&&<><button type="button" className="secondary" disabled={mutating||!readyScene} onClick={replaying?()=>setReplaying(false):replay}>{replaying?'Pause replay':'Replay'}</button>
          <button type="button" className="secondary" disabled={mutating} onClick={download}>Export JSON</button></>}
      </div>
      <div className="humanoid-result" aria-live="polite"><strong data-testid="contact-result">{outcome}</strong>
        <dl><div><dt>Left hand support</dt><dd>{number(measured?.last_measurement?.support?.left_vertical_n)} N</dd></div>
          <div><dt>Right hand support</dt><dd>{number(measured?.last_measurement?.support?.right_vertical_n)} N</dd></div>
          <div><dt>Placement error</dt><dd>{number(measured?.last_measurement?.destination_error_m===undefined?undefined:measured.last_measurement.destination_error_m*1000,1)} mm</dd></div>
          <div><dt>Minimum steady hand share</dt><dd>{number((measured?.hold_samples??0)>0&&measured?.minimum_hold_share!==undefined?measured.minimum_hold_share*100:undefined,1)}%</dd></div></dl>
        {job?.world_version&&<details><summary>World and controller identity</summary><p>World version: {job.world_version}</p><p>Model: {assets?.manifest.model_hash}</p><p>Controller: {job.result?.controller??job.task}</p></details>}
      </div>
    </div><form className="humanoid-controls contact-controls" onSubmit={run}>
      <h2>Configure the next trial</h2><p className="humanoid-scope">Edits create a new world when you run. Existing results retain their original conditions. Wider settings can produce a measured failure.</p>
      <fieldset disabled={busy||mutating||!enabled}><legend>Controller and parcel</legend>
        <label>Controller<select value={task} onChange={e=>setTask(e.target.value)}><option value="g1_constrained_carton">Constrained contact control</option><option value="g1_stationary_bimanual">Native servo baseline</option></select></label>
        {(['source_xy_m','destination_xy_m'] as const).map(kind=>[0,1].map(index=><label key={kind+index}>{kind==='source_xy_m'?'Source':'Destination'} {index?'Y':'X'} (m)
          <input type="number" required step=".005" min={index?-.3:.18} max={index?.3:.7} value={inputValue(config[kind][index])} onChange={e=>location(kind,index,e.target.valueAsNumber)}/></label>))}
        <label>Parcel mass (kg)<input type="number" required min=".01" max="20" step=".01" value={inputValue(config.parcel.mass_kg)} onChange={e=>setConfig(v=>({...v,parcel:{...v.parcel,mass_kg:e.target.valueAsNumber}}))}/></label>
        <label>Sliding friction<input type="number" required min=".001" max="2" step=".001" value={inputValue(config.parcel.sliding_friction)} onChange={e=>setConfig(v=>({...v,parcel:{...v.parcel,sliding_friction:e.target.valueAsNumber}}))}/></label>
        <details><summary>Carton dimensions</summary><p>Full lengths. Mass stays fixed; geometry and inertia are rebuilt.</p>{['X','Y','Z'].map((axis,index)=><label key={axis}>Dimension {axis} (m)<input type="number" required min=".04" max=".5" step=".01" value={inputValue(config.parcel.dimensions_m[index])} onChange={e=>dimension(index,e.target.valueAsNumber)}/></label>)}</details>
      </fieldset>
      <div className="humanoid-actions"><button className="primary" type="submit" disabled={busy||mutating||loading||!enabled}>Run physical trial</button>
        {busy&&<><button className="secondary" type="button" disabled={mutating||['pausing','cancelling'].includes(job!.status)} onClick={()=>control(paused?'resume':'pause')}>{paused?'Resume physics':'Pause physics'}</button>
          <button className="secondary" type="button" disabled={mutating||job!.status==='cancelling'} onClick={()=>control('cancel')}>Cancel</button></>}
        <button className="secondary" type="button" disabled={!paused||mutating} onClick={fork}>Fork paused snapshot</button>
      </div>
      <p className="humanoid-limit">No attachment supports this carton. State comes from the simulator, not camera perception. This is stationary manipulation, not walking or hardware validation.</p>
    </form></div>
    <section className="humanoid-history" aria-labelledby="contact-history"><h2 id="contact-history">Saved trials</h2>
      <button type="button" className="secondary" disabled={!enabled||mutating} onClick={()=>void action(refreshHistory)}>Refresh history</button>
      {!history.length&&<p>No saved trials for this browser workspace.</p>}
      <ol>{history.map(item=><li key={item.id}><label><input type="checkbox" aria-label={`Compare ${item.id.slice(0,8)}`} checked={selected.includes(item.id)} onChange={e=>setSelected(v=>e.target.checked?[...v,item.id].slice(-4):v.filter(id=>id!==item.id))}/></label>
        <button type="button" onClick={()=>selectJob(item)} aria-current={job?.id===item.id?'true':undefined}>{item.id.slice(0,8)} · {item.status} · {item.task==='g1_constrained_carton'?'Constrained control':'Native servo'}</button></li>)}</ol>
      <button type="button" className="secondary" disabled={selected.length<2||mutating} onClick={()=>void action(async()=>setComparison(await request<Comparison>('/compare','POST',{ids:selected})))}>Compare selected trials</button>
      {comparison&&<div className="humanoid-comparison"><p>{comparison.same_world_version?'Same immutable world version.':'Different world versions; compare their recorded conditions.'}</p><table><caption>Measured outcomes, including failed trials</caption><thead><tr><th>Trial</th><th>Outcome</th><th>Steps</th><th>Placement error</th></tr></thead><tbody>{comparison.trials.map(item=><tr key={item.id}><th>{item.id.slice(0,8)}</th><td>{item.result?.task_success?'Completed':item.result?.failure_reason??item.status}</td><td>{item.steps_completed}</td><td>{number(item.result?.measurements.last_measurement?.destination_error_m,4)} m</td></tr>)}</tbody></table></div>}
    </section>
  </section>;
}
