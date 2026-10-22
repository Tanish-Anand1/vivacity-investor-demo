import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Canvas,useFrame,useThree} from '@react-three/fiber';
import {OrbitControls} from '@react-three/drei';
import {Group,PCFShadowMap,Quaternion,Vector3} from 'three';
import {API,errorMessage} from './api';
import {fetchRuntime} from './apiTransport';
import {workspaceToken,type RoboticsProgram} from './workspaceApi';
import {GeomMesh,loadAssets,type Assets} from './RobotAssets';
import SceneBoundary from './SceneBoundary';
import './humanoidLab.css';

type Pose={name:string;position:number[];quaternion_wxyz:number[]};
type Frame={time_s:number;base_position_m:number[];qpos:number[];body_transforms:Pose[];contacts:number;phase?:string;parcel_position_m?:number[];grasp_active?:boolean};
type Model={robot_id:string;name:string;environment_id:string;dof:number;actuators:number;mesh_count:number;model_hash:string;initial_frame:Frame;task_scope:string};
type Measurements={simulation_steps:number;simulation_duration_s:number;compute_wall_s:number;minimum_base_height_m:number;maximum_base_tilt_rad:number;peak_joint_delta_rad:number;minimum_hand_goal_distance_m:number|null;task_contact_samples:number;maximum_parcel_height_m:number|null;maximum_switch_angle_rad:number|null;maximum_switch_angle_after_hand_contact_rad:number|null;switch_activation_time_s:number|null;maximum_foot_slip_m_s:number|null;final_base_position_m:number[];fallen:boolean;final_parcel_position_m?:number[];destination_error_m?:number;maximum_joint_limit_violation_rad?:number;final_support_contact?:boolean;grasp_constraint_active_final?:boolean;grasp_constraint_pose_jump_m?:number|null;contact_force_peak_n?:{left:number;right:number};prohibited_contacts?:string[]};
type Result={robot_id:string;action:string;frames:Frame[];task_success:boolean;failure_reason:string|null;model_hash:string;scene_geometry_hash?:string;measurements:Measurements;parameters:Settings;environment_id:string;simulator_version:string;scope:string;events?:{phase:string;time_s:number;evidence:Record<string,unknown>}[];planning:{method:string;target_position_m?:number[];hand_position_error_m?:number;hand_position_errors_m?:{left:number;right:number};feasible:boolean}|null};
type Trial={id:string;status:'queued'|'running'|'completed'|'failed';created_unix_s:number;request:Settings;result:Result|null;error:string|null};
type Settings={robot_id:string;action:'attempt_task'|'hold_stance'|'pickup_place';duration_s:number;movement_scale:number;floor_friction:number;parcel_mass_kg:number;parcel_xy_m:[number,number];destination_xy_m:[number,number];task_timeout_s:number;perturbation_n:number;seed:number};
const defaults=(robot_id:string):Settings=>({robot_id,action:robot_id==='unitree_g1'?'pickup_place':'attempt_task',duration_s:2,movement_scale:robot_id==='unitree_h1'?.6:1,floor_friction:.8,parcel_mass_kg:.5,parcel_xy_m:[.35,0],destination_xy_m:[.66,-.47],task_timeout_s:8,perturbation_n:0,seed:7});
const labels:Record<string,string>={unitree_g1:'Warehouse logistics',apptronik_apollo:'Industrial maintenance',unitree_h1:'Terrain mobility'};
const modelNames:Record<string,string>={unitree_g1:'Unitree G1',apptronik_apollo:'Apptronik Apollo',unitree_h1:'Unitree H1'};

async function read<T>(path:string,init:RequestInit={}):Promise<T>{
  const response=await fetchRuntime(API+path,{...init,headers:{'X-Workspace-Token':workspaceToken(),...init.headers},signal:init.signal??AbortSignal.timeout(90000)},{timeoutMs:60000});
  const value=await response.json().catch(()=>null);
  if(!response.ok)throw new Error(typeof value?.detail==='string'?value.detail:`Request failed (${response.status})`);
  if(!value)throw new Error('The runtime returned an unreadable response.');
  return value as T;
}

function ModelScene({assets,frames,cursor,playing,robotId,time}:{assets:Assets;frames:Frame[];cursor:React.RefObject<number>;playing:boolean;robotId:string;time:number}){
  const groups=useRef(new Map<string,Group>());
  const {invalidate}=useThree();
  const vecA=useMemo(()=>new Vector3(),[]),vecB=useMemo(()=>new Vector3(),[]);
  const qa=useMemo(()=>new Quaternion(),[]),qb=useMemo(()=>new Quaternion(),[]);
  const renderConfig=useMemo(()=>({humanoid_visual:robotId}),[robotId]);
  useEffect(()=>{invalidate();},[frames,cursor,playing,time,invalidate]);
  useFrame(()=>{
    if(!frames.length)return;
    const t=cursor.current;
    let index=frames.findIndex(frame=>frame.time_s>=t);
    if(index<0)index=frames.length-1;
    const a=frames[Math.max(0,index-1)],b=frames[index];
    const alpha=b.time_s>a.time_s?Math.max(0,Math.min(1,(t-a.time_s)/(b.time_s-a.time_s))):0;
    for(let i=0;i<a.body_transforms.length;i++){
      const from=a.body_transforms[i],to=b.body_transforms[i],group=groups.current.get(from.name);
      if(!group||!to)continue;
      group.position.copy(vecA.fromArray(from.position).lerp(vecB.fromArray(to.position),alpha));
      qa.set(from.quaternion_wxyz[1],from.quaternion_wxyz[2],from.quaternion_wxyz[3],from.quaternion_wxyz[0]);
      qb.set(to.quaternion_wxyz[1],to.quaternion_wxyz[2],to.quaternion_wxyz[3],to.quaternion_wxyz[0]);
      group.quaternion.copy(qa.slerp(qb,alpha));
    }
    if(playing)invalidate();
  });
  const target=robotId==='unitree_h1'?[.35,0,.85]:robotId==='unitree_g1'?[.22,0,.72]:[.25,0,1.0];
  const darkShell=robotId==='unitree_h1';
  return <>
    <ambientLight intensity={darkShell?.48:.22}/><hemisphereLight args={['#e4e8e1','#4e554f',darkShell?1.4:.56]}/>
    <directionalLight position={[-2,-3,5]} intensity={darkShell?2.15:1.1} castShadow shadow-mapSize={[2048,2048]} shadow-bias={-.00008} shadow-normalBias={.012} shadow-camera-left={-5} shadow-camera-right={5} shadow-camera-top={5} shadow-camera-bottom={-5}/>
    <directionalLight position={[3,2,3]} intensity={darkShell?.95:.3}/>
    {assets.manifest.bodies.map(body=><group key={body.id} ref={node=>{if(node)groups.current.set(body.name,node);else groups.current.delete(body.name);}}>
      {assets.manifest.geoms.filter(geom=>geom.body_id===body.id&&[0,1,2].includes(geom.group)).map(geom=>geom.name==='floor'
        ?<mesh key={geom.id} receiveShadow><planeGeometry args={[16,16]}/><meshStandardMaterial color="#59605c" roughness={.94}/></mesh>
        :<GeomMesh key={geom.id} geom={geom} assets={assets} config={renderConfig}/>)}
    </group>)}
    <OrbitControls makeDefault target={target as [number,number,number]} minDistance={1.1} maxDistance={13} maxPolarAngle={Math.PI*.49} enableDamping={false}/>
  </>;
}

export default function HumanoidLab({program,back}:{program:RoboticsProgram;back:()=>void}){
  const [robotId,setRobotId]=useState(()=>program.id==='humanoid_logistics'?'unitree_g1':program.id==='humanoid_maintenance'?'apptronik_apollo':'unitree_h1');
  const [model,setModel]=useState<Model|null>(null),[assets,setAssets]=useState<Assets|null>(null);
  const [settings,setSettings]=useState<Settings>(()=>defaults(robotId));
  const [trial,setTrial]=useState<Trial|null>(null),[history,setHistory]=useState<Trial[]>([]);
  const [error,setError]=useState<string|null>(null),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
  const [playing,setPlaying]=useState(false),[time,setTime]=useState(0);
  const cursor=useRef(0);
  const loadSequence=useRef(0);
  const reload=useCallback(async()=>{
    const sequence=++loadSequence.current;
    setLoading(true);setError(null);setModel(null);setAssets(null);setTrial(null);setPlaying(false);cursor.current=0;setTime(0);
    try{
      const [info,prior]=await Promise.all([
        read<Model>(`/v1/robotics/humanoids/models/${robotId}`),
        read<Trial[]>(`/v1/robotics/humanoids/experiments?robot_id=${robotId}`),
      ]);
      const geometry=await loadAssets(robotId,`${info.model_hash}-${retry}`);
      if(sequence===loadSequence.current){setModel(info);setAssets(geometry);setHistory(prior);}
    }catch(cause){if(sequence===loadSequence.current)setError(errorMessage(cause));}
    finally{if(sequence===loadSequence.current)setLoading(false);}
  },[robotId,retry]);
  useEffect(()=>{setSettings(defaults(robotId));void reload();},[robotId,retry,reload]);
  useEffect(()=>{
    if(!trial||!['queued','running'].includes(trial.status))return;
    let alive=true,timer:ReturnType<typeof setTimeout>|undefined;
    const poll=async()=>{
      try{const current=await read<Trial>(`/v1/robotics/humanoids/experiments/${trial.id}`);
        if(!alive)return;setTrial(current);
        if(current.status==='completed'){setError(null);setHistory(items=>[current,...items.filter(item=>item.id!==current.id)].slice(0,10));cursor.current=0;setTime(0);setPlaying(true);return;}
        if(current.status==='failed'){setError(current.error??'The physical trial failed.');return;}
        timer=setTimeout(()=>void poll(),900);
      }catch(cause){if(alive){setError(errorMessage(cause));timer=setTimeout(()=>void poll(),1600);}}
    };
    void poll();return()=>{alive=false;if(timer)clearTimeout(timer);};
  },[trial?.id,trial?.status]);
  const visibleTrial=trial?.request.robot_id===robotId?trial:null;
  const result=visibleTrial?.result?.robot_id===robotId?visibleTrial.result:null;
  const replayCompatible=Boolean(result&&model&&(result.scene_geometry_hash??result.model_hash)===model.model_hash);
  const duration=replayCompatible?(result?.frames.at(-1)?.time_s??0):0;
  useEffect(()=>{
    if(!playing||!result||!replayCompatible)return;
    let handle=0;const origin=performance.now(),offset=cursor.current;
    const tick=(now:number)=>{const next=Math.min(duration,offset+(now-origin)/1000);cursor.current=next;setTime(next);
      if(next>=duration){setPlaying(false);return;}handle=requestAnimationFrame(tick);};
    handle=requestAnimationFrame(tick);return()=>cancelAnimationFrame(handle);
  },[playing,result,duration,replayCompatible]);
  const run=async()=>{
    setError(null);setPlaying(false);setTrial(null);cursor.current=0;setTime(0);
    try{setTrial(await read<Trial>('/v1/robotics/humanoids/experiments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)}));}
    catch(cause){setError(errorMessage(cause));}
  };
  const download=()=>{
    if(!result)return;const blob=new Blob([JSON.stringify({trial_id:trial?.id,...result},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`vivacity-${robotId}-${trial?.id}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  const frames=useMemo(()=>replayCompatible&&result?result.frames:(model?[model.initial_frame]:[]),[replayCompatible,result,model]);
  const busy=visibleTrial?.status==='queued'||visibleTrial?.status==='running';
  const sceneReady=Boolean(model&&model.robot_id===robotId&&assets&&assets.manifest.model_hash===model.model_hash);
  const visibleHistory=history.filter(item=>item.request.robot_id===robotId);
  const outcomeSummary=!result?null:result.task_success
    ?result.action==='pickup_place'?`The G1 lifted the parcel and released it onto the destination stand, ${result.measurements.destination_error_m?.toFixed(3)} m from the requested center.`:robotId==='apptronik_apollo'?`Hand contact deflected the hinged switch beyond its threshold at ${result.measurements.switch_activation_time_s?.toFixed(2)} s.`:'Required physical checks passed.'
    :result.action==='pickup_place'?`The pickup did not pass: ${(result.failure_reason??'unknown failure').replaceAll('_',' ')}.`
    :robotId==='unitree_g1'&&result.measurements.task_contact_samples>0?'Hand contact with the parcel was measured, but pickup and transport were not completed.'
    :`${(result.failure_reason??'Measured goal conditions were not met').replaceAll('_',' ')}.`;
  return <section className="humanoid-lab" aria-labelledby="humanoid-title">
    <div className="humanoid-heading"><div><span className="eyebrow">Physical embodiment / {labels[robotId]}</span><h2 id="humanoid-title">{model?.name??modelNames[robotId]}</h2><p>{robotId==='unitree_g1'?'Stationary pickup uses articulated MuJoCo control, bilateral contact checks, a documented rigid-grasp constraint and measured placement. Walking and fulfillment remain under validation.':'Full-body model, collision world and measured joint-state probes. Complete task controllers remain under validation.'}</p></div><button className="secondary" type="button" onClick={back}>Back to arm workcell</button></div>
    <div className="humanoid-model-tabs" role="group" aria-label="Humanoid model">{Object.keys(modelNames).map(id=><button type="button" key={id} aria-pressed={id===robotId} disabled={busy} onClick={()=>setRobotId(id)}>{modelNames[id]}<small>{labels[id]}</small></button>)}</div>
    {error&&<div className="humanoid-error" role="alert">{error}<button type="button" className="secondary" onClick={()=>setRetry(value=>value+1)}>Retry model and scene</button></div>}
    <div className="humanoid-layout"><div className="humanoid-primary"><div className="humanoid-viewport" role="region" aria-label={`${model?.name??'Humanoid'} three-dimensional physical model and task environment`}>
      {sceneReady&&assets&&frames.length>0&&<SceneBoundary onError={()=>setError('The 3D view could not render. Try reloading in a WebGL2-capable browser.')}><Canvas key={robotId} frameloop="demand" dpr={[1,1.75]} shadows={{type:PCFShadowMap}} camera={{position:robotId==='unitree_h1'?[2.6,-3.4,2.25]:robotId==='unitree_g1'?[1.45,-2.1,1.55]:[-2.8,-1.25,1.95],fov:42,near:.02,far:80}} gl={{antialias:true}} onCreated={({camera,gl})=>{camera.up.set(0,0,1);gl.setClearColor('#2d3434');}}><ModelScene assets={assets} frames={frames} cursor={cursor} playing={playing} time={time} robotId={robotId}/></Canvas></SceneBoundary>}
      {(loading||(model&&model.robot_id!==robotId))&&<p role="status" className="humanoid-loading">Loading the licensed full-body model and physical scene…</p>}
      {!loading&&!sceneReady&&model?.robot_id===robotId&&<div className="humanoid-loading" role="alert">The model and scene geometry differ. <button className="secondary" type="button" onClick={()=>setRetry(value=>value+1)}>Retry matching assets</button></div>}
      {!loading&&!model&&<p className="humanoid-loading">The physical model is unavailable. No unrelated robot was loaded.</p>}
    </div>
    <div className="humanoid-playback"><div><strong>{replayCompatible?`${time.toFixed(2)} / ${duration.toFixed(2)} s`:'Standing state'}</strong><span>{result&&!replayCompatible?'Replay unavailable: this trial used another scene version.':result?'Recorded body transforms from this physics trial':'Model keyframe; no experiment has run'}</span></div>{result&&replayCompatible&&<><button type="button" className="secondary" onClick={()=>{if(cursor.current>=duration){cursor.current=0;setTime(0);}setPlaying(value=>!value);}}>{playing?'Pause replay':'Play replay'}</button><label>Recorded time<input aria-label="Recorded simulation time" type="range" min="0" max={duration} step="any" value={time} onChange={event=>{const next=Number(event.target.value);cursor.current=next;setTime(next);setPlaying(false);}}/></label></>}</div>
    <div className="humanoid-disclosure"><details><summary>Model and scene provenance</summary><p>Robot source: a licensed full-body description for {model?.name??robotId}; geometry and physical properties come from that model. The virtual facility is a bounded collision scene assembled for this test, not a calibrated facility twin. <a href={`https://github.com/google-deepmind/mujoco_menagerie/tree/main/${robotId}`} target="_blank" rel="noreferrer">View model source and license ↗</a></p>{model&&<dl><div><dt>Actuated joints</dt><dd>{model.actuators}</dd></div><div><dt>Degrees of freedom</dt><dd>{model.dof}</dd></div><div><dt>Visual meshes</dt><dd>{model.mesh_count}</dd></div><div><dt>Model hash</dt><dd>{model.model_hash.slice(0,16)}…</dd></div></dl>}</details></div>
    </div><aside className="humanoid-controls" aria-label="Humanoid physics controls"><h3>{robotId==='unitree_g1'?'Run stationary pickup':'Run a physical probe'}</h3><p className="humanoid-scope">{robotId==='unitree_g1'?'The G1 reads privileged simulator object pose, reaches with both arms, verifies contact force, lifts and places the parcel. The grasp uses an explicit contact-gated rigid constraint; this is not vision or dexterous grasping.':robotId==='apptronik_apollo'?'The arm approaches a hinged switch. Actuation counts only if hand contact and switch movement are measured.':'A joint-controlled gait attempt begins on the terrain course. Traversal counts only if the body progresses without falling or slipping.'}</p>
      <label>Test mode<select value={settings.action} disabled={busy} onChange={event=>setSettings(value=>({...value,action:event.target.value as Settings['action']}))}>{robotId==='unitree_g1'&&<option value="pickup_place">Pick up and place</option>}<option value="attempt_task">Reach probe</option><option value="hold_stance">Hold stance</option></select></label>
      <label>Motion scale <output>{settings.movement_scale.toFixed(2)}</output><input type="range" min="0" max="1" step="0.05" value={settings.movement_scale} disabled={busy} onChange={event=>setSettings(value=>({...value,movement_scale:Number(event.target.value)}))}/></label>
      <label>Floor friction <output>{settings.floor_friction.toFixed(2)}</output><input type="range" min="0.2" max="1.5" step="0.05" value={settings.floor_friction} disabled={busy} onChange={event=>setSettings(value=>({...value,floor_friction:Number(event.target.value)}))}/></label>
      {robotId==='unitree_g1'&&<label>Parcel mass <output>{settings.parcel_mass_kg.toFixed(2)} kg</output><input type="range" min="0.1" max="2" step="0.1" value={settings.parcel_mass_kg} disabled={busy} onChange={event=>setSettings(value=>({...value,parcel_mass_kg:Number(event.target.value)}))}/></label>}
      {robotId==='unitree_g1'&&settings.action==='pickup_place'&&<><label>Parcel X <output>{settings.parcel_xy_m[0].toFixed(2)} m</output><input type="range" min="0.30" max="0.39" step="0.01" value={settings.parcel_xy_m[0]} disabled={busy} onChange={event=>setSettings(value=>({...value,parcel_xy_m:[Number(event.target.value),value.parcel_xy_m[1]]}))}/></label><label>Parcel Y <output>{settings.parcel_xy_m[1].toFixed(2)} m</output><input type="range" min="-0.03" max="0.03" step="0.01" value={settings.parcel_xy_m[1]} disabled={busy} onChange={event=>setSettings(value=>({...value,parcel_xy_m:[value.parcel_xy_m[0],Number(event.target.value)]}))}/></label><label>Destination X <output>{settings.destination_xy_m[0].toFixed(2)} m</output><input type="range" min="0.55" max="0.72" step="0.01" value={settings.destination_xy_m[0]} disabled={busy} onChange={event=>setSettings(value=>({...value,destination_xy_m:[Number(event.target.value),value.destination_xy_m[1]]}))}/></label><label>Destination Y <output>{settings.destination_xy_m[1].toFixed(2)} m</output><input type="range" min="-0.58" max="-0.36" step="0.01" value={settings.destination_xy_m[1]} disabled={busy} onChange={event=>setSettings(value=>({...value,destination_xy_m:[value.destination_xy_m[0],Number(event.target.value)]}))}/></label></>}
      <label>Horizontal disturbance <output>{settings.perturbation_n.toFixed(0)} N</output><input type="range" min="0" max="80" step="5" value={settings.perturbation_n} disabled={busy} onChange={event=>setSettings(value=>({...value,perturbation_n:Number(event.target.value)}))}/></label>
      <div className="humanoid-actions"><button className="primary" type="button" disabled={!sceneReady||busy||loading} onClick={()=>void run()}>{busy?'Running physical steps…':settings.action==='pickup_place'?'Run pickup experiment':'Run physics probe'}</button><button className="secondary" type="button" onClick={()=>{setPlaying(false);setTrial(null);cursor.current=0;setTime(0);}}>Reset view</button></div>
      {visibleTrial&&<div className="humanoid-result" aria-live="polite"><strong>{busy?'Computing measured motion…':visibleTrial.status==='failed'?'Trial failed':result?.task_success?(robotId==='apptronik_apollo'?'Momentary switch actuated in simulation':'Task completed in simulation'):'Task not completed'}</strong>{result&&<><p>{outcomeSummary} This is a recorded simulation, not hardware validation.</p><dl><div><dt>Physics steps</dt><dd>{result.measurements.simulation_steps.toLocaleString()}</dd></div><div><dt>Lowest base height</dt><dd>{result.measurements.minimum_base_height_m.toFixed(3)} m</dd></div><div><dt>Peak body tilt</dt><dd>{result.measurements.maximum_base_tilt_rad.toFixed(3)} rad</dd></div><div><dt>Joint movement</dt><dd>{result.measurements.peak_joint_delta_rad.toFixed(3)} rad</dd></div><div><dt>{robotId==='unitree_h1'?'Foot-ground contact points':'Task contacts'}</dt><dd>{result.measurements.task_contact_samples}</dd></div>{result.measurements.minimum_hand_goal_distance_m!==null&&<div><dt>Closest hand to target</dt><dd>{result.measurements.minimum_hand_goal_distance_m.toFixed(3)} m</dd></div>}{result.planning?.hand_position_error_m!==undefined&&<div><dt>Planned hand IK error</dt><dd>{result.planning.hand_position_error_m.toFixed(4)} m</dd></div>}{result.planning?.hand_position_errors_m&&<div><dt>Planned bilateral IK error</dt><dd>{Math.max(...Object.values(result.planning.hand_position_errors_m)).toFixed(4)} m</dd></div>}{result.measurements.maximum_switch_angle_rad!==null&&<div><dt>Peak switch angle</dt><dd>{result.measurements.maximum_switch_angle_rad.toFixed(3)} rad</dd></div>}{result.measurements.maximum_foot_slip_m_s!==null&&<div><dt>Peak contact slip speed</dt><dd>{result.measurements.maximum_foot_slip_m_s.toFixed(3)} m/s</dd></div>}</dl>{result.action==="pickup_place"&&<div className="pickup-evidence"><p><strong>Measured task:</strong> {result.events?.map(event=>`${event.phase.replaceAll("_"," ")} ${event.time_s.toFixed(2)} s`).join(" → ")??"No transition reached"}</p><p>Peak hand contact: {result.measurements.contact_force_peak_n?.left.toFixed(1)??"0.0"} N left · {result.measurements.contact_force_peak_n?.right.toFixed(1)??"0.0"} N right. Final parcel: {result.measurements.final_parcel_position_m?.map(value=>value.toFixed(3)).join(", ")} m. Destination support: {result.measurements.final_support_contact?"yes":"no"}. Grasp released: {result.measurements.grasp_constraint_active_final?"no":"yes"}.</p></div>}<button className="secondary" type="button" onClick={download}>Export measured trial JSON</button></>}</div>}
      {visibleHistory.length>0&&<details className="humanoid-history"><summary>Saved trials ({visibleHistory.length})</summary><ol>{visibleHistory.map(item=><li key={item.id}><button type="button" disabled={busy} onClick={()=>{setTrial(item);setPlaying(false);cursor.current=0;setTime(0);}}>{new Date(item.created_unix_s*1000).toLocaleString()} · {item.result?.task_success?'completed':item.status==='completed'?'measured failure':item.status}</button></li>)}</ol></details>}
      <p className="humanoid-limit">Task status reflects measured contacts, pose and destination checks. Apollo's momentary switch actuation works at the tested setting. Reliable actuation across conditions, walking parcel transport and terrain completion remain unvalidated.</p>
    </aside></div>
  </section>;
}
