import {lazy,Suspense,useEffect,useRef,useState} from 'react';
import {api,API,errorMessage,liveWebsocketURL,websocketURL} from './api';
import {robotFrame,type World,type Experiment,type Branch,type Event,type RobotFrame} from './domain';
import ResultCard from './ResultCard';
import TechnicalInspector from './TechnicalInspector';
import Settings from './Settings';
const RobotView=lazy(()=>import('./RobotView'));

// Explicit manual execution of the shared runtime, with bounded jobs and real
// WebSocket states. Opening an import does not start a physics experiment.
export default function OrbitalTask({worldId}:{worldId:string}){
 const [world,setWorld]=useState<World|null>(null),[frame,setFrame]=useState<RobotFrame|null>(null),[experiment,setExperiment]=useState<Experiment|null>(null),[branches,setBranches]=useState<Branch[]>([]),[events,setEvents]=useState<Event[]>([]),[error,setError]=useState<string|null>(null),[editing,setEditing]=useState(false),[pending,setPending]=useState(false);
 const cursor=useRef(0),activeExperiment=useRef<string|null>(null);
 const [selected,setSelected]=useState<string|null>(null);
 const busy=pending||experiment?.status==='queued'||experiment?.status==='running';
 useEffect(()=>{let active=true;Promise.all([api.world(worldId),api.state(worldId)]).then(([w,s])=>{if(active){setWorld(w);setFrame(robotFrame(s.observation));}}).catch(e=>active&&setError(errorMessage(e)));return()=>{active=false;const id=activeExperiment.current;if(id)fetch(`${API}/v1/experiments/${id}/cancel`,{method:'POST'}).catch(()=>{});};},[worldId]);
 useEffect(()=>{
  if(!experiment)return;
  let active=true,updating=false,terminal=false;let eventCursor=0,sequence=-1;
  const receive=(live:unknown)=>{const v=live as {sequence:number;frame:unknown}|null;if(active&&v&&v.sequence>sequence){sequence=v.sequence;setFrame(robotFrame(v.frame));}};
  const receiveEvent=(event:Event)=>{if(active&&event.seq>eventCursor){eventCursor=event.seq;setEvents(e=>[...e,event].slice(-160));}};
  const live=new WebSocket(liveWebsocketURL(experiment.id));live.onmessage=e=>{try{receive(JSON.parse(e.data));}catch{/* HTTP fallback */}};
  const log=new WebSocket(websocketURL(experiment.id,0));log.onmessage=e=>{try{receiveEvent(JSON.parse(e.data));}catch{/* HTTP fallback */}};
  const refresh=async()=>{if(!active||updating||terminal)return;updating=true;try{
   const [e,l,ev]=await Promise.all([api.experiment(experiment.id),api.live(experiment.id),api.events(experiment.id,eventCursor)]);
   if(!active)return;receive(l);ev.forEach(receiveEvent);setExperiment(e);setError(null);
   if(e.status!=='queued'&&e.status!=='running'){activeExperiment.current=null;const b=await api.branches(e.id);if(active){setBranches(b);terminal=true;live.close();log.close();}}
  }catch(e){if(active)setError(errorMessage(e));}finally{updating=false;}};
  const timer=setInterval(refresh,1500);void refresh();return()=>{active=false;clearInterval(timer);live.close();log.close();};
 },[experiment?.id]);
 const run=async()=>{if(!world||busy)return;setPending(true);setError(null);try{setBranches([]);setEvents([]);const e=await api.submit(world.id,crypto.randomUUID(),{candidates:3,physics_trials:3,search_candidates:3,physics_budget:3,execute_selected:true,realtime_execution:true,max_simulation_seconds:40});activeExperiment.current=e.id;setExperiment(e);}catch(e){setError(errorMessage(e));}finally{setPending(false);}};
 const stop=async()=>{if(!experiment)return;try{const r=await fetch(`${API}/v1/experiments/${experiment.id}/cancel`,{method:'POST'});if(!r.ok)throw new Error('Cancellation failed');}catch(e){setError(errorMessage(e));}};
 const apply=async(config:Record<string,unknown>)=>{if(!world||busy)return;const w=await api.environment(world.id,config);setWorld(w);setFrame(robotFrame((await api.state(w.id)).observation));if(experiment)setExperiment(await api.experiment(experiment.id));};
 const feasible=branches.filter(b=>b.evaluation.success&&b.action.execution_role!=='authoritative_execution').sort((a,b)=>(a.evaluation.execution_duration_s??Infinity)-(b.evaluation.execution_duration_s??Infinity)).slice(0,3);
 return <>
  <div className="workspace-intro"><div><h1>Orbital Salvage Lab</h1><p>Deliver cargo to the docking region while avoiding the reactor. Adapted Panda; terrestrial gravity.</p></div></div>
  {error&&<p role="alert" className="error-notice">{error}</p>}
  <div className="workbench"><section className="visual-area"><Suspense fallback={<p>Loading geometry…</p>}><RobotView frames={frame?[frame]:[]} cursor={cursor} config={world?.config??{}} playing={false} replaying={false} renderTime={frame?.time??0}/></Suspense>
   <div className="experiment-actions"><button className="primary" disabled={!world||busy} onClick={run}>Start salvage experiment</button>{busy&&<button className="secondary" onClick={stop}>Stop experiment</button>}<button className="secondary" disabled={!world||busy} onClick={()=>setEditing(e=>!e)}>Change conditions</button><button className="secondary" disabled={!world||busy} onClick={async()=>{try{const w=await api.reset(worldId);setWorld(w);setFrame(robotFrame((await api.state(worldId)).observation));if(experiment)setExperiment(await api.experiment(experiment.id));}catch(e){setError(errorMessage(e));}}}>Reset world</button></div>
  </section><aside className="results"><div className="section-heading"><h2>Verified deliveries</h2><span role="status">{busy?'Computing real physics':experiment?.result.execution_evaluation?(experiment.result.execution_evaluation as {success:boolean}).success?'Delivery verified':'Execution failed':experiment?'Evaluated':'Ready to start'}</span></div>
   {editing&&world?<Settings config={world.config} disabled={busy} apply={async c=>{try{await apply(c);}catch(e){setError(errorMessage(e));throw e;}}} close={()=>setEditing(false)}/>:feasible.length?feasible.map((b,i)=><ResultCard key={b.id} branch={b} rank={i} selected={selected?selected===b.id:i===0} choose={()=>setSelected(b.id)} download={()=>api.download(b.experiment_id,b.id).catch(e=>setError(errorMessage(e)))}/>):<p className="results-empty">{busy?'Generating, simulating and evaluating independent alternatives.':'Choose Start salvage experiment. A configured task has not yet proved delivery.'}</p>}
   <p className="decision">{String(experiment?.error??experiment?.result.conclusion??'')}</p>{experiment?.stale&&<p className="stale-warning">Conditions changed. Previous results are stale; start a new experiment.</p>}
  </aside></div>
  <TechnicalInspector events={events} initialized={!!world} playing={false} branches={branches} select={()=>{}} history={{ids:[],open:()=>{},disabled:true}}/>
 </>;
}
