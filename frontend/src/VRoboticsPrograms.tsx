import {useCallback,useEffect,useState} from 'react';
import {errorMessage} from './api';
import {roboticsPrograms,type RoboticsProgram,type Configuration} from './workspaceApi';
import './vRoboticsPrograms.css';

export default function VRoboticsPrograms({busy,onOpen,onInspect,onArms,category,setCategory}:{busy:boolean;onOpen:(configuration:Configuration)=>Promise<boolean>;onInspect:(program:RoboticsProgram)=>void;onArms:()=>void;category:RoboticsProgram['category'];setCategory:(category:RoboticsProgram['category'])=>void}){
  const [programs,setPrograms]=useState<RoboticsProgram[]>([]);
  const [expanded,setExpanded]=useState(false);
  const [loading,setLoading]=useState(true);
  const [opening,setOpening]=useState<string|null>(null);
  const [error,setError]=useState<string|null>(null);
  const refresh=useCallback(async()=>{
    setLoading(true);setError(null);
    try{setPrograms(await roboticsPrograms());}catch(e){setError(errorMessage(e));}finally{setLoading(false);}
  },[]);
  useEffect(()=>{void refresh();},[refresh]);
  useEffect(()=>{if(category==='humanoids'){const first=programs.find(program=>program.id==='humanoid_logistics');if(first)onInspect(first);}},[category,programs,onInspect]);
  const visible=programs.filter(program=>program.category===category);
  const open=async(program:RoboticsProgram)=>{
    if(!program.default_configuration||busy||opening)return;
    setOpening(program.id);setError(null);
    try{if(await onOpen(program.default_configuration))setExpanded(false);}catch(e){setError(errorMessage(e));}
    finally{setOpening(null);}
  };
  return <section className="v-programs" aria-labelledby="v-programs-heading">
    <div className="v-programs-top"><div><span className="eyebrow">V-Robotics / physical workflows</span><h2 id="v-programs-heading">Choose a physical program.</h2><p>Run bounded robot tasks in the physics lab and inspect their measured outcomes. Each controller's limits are stated beside its task.</p></div><button type="button" className="secondary" aria-expanded={expanded} aria-controls="v-program-list" onClick={()=>setExpanded(value=>!value)}>{expanded?'Hide programs':'Browse programs'}</button></div>
    <div id="v-program-list" hidden={!expanded}>
      <div className="v-program-categories" role="group" aria-label="Robot category"><button type="button" disabled={busy} aria-pressed={category==='robotic_arms'} onClick={()=>{setCategory('robotic_arms');onArms();}}>Robotic arms</button><button type="button" disabled={busy} aria-pressed={category==='humanoids'} onClick={()=>{setCategory('humanoids');setExpanded(false);const first=programs.find(program=>program.id==='humanoid_logistics');if(first)onInspect(first);}}>Humanoids</button></div>
      {loading?<p role="status">Loading robotics programs…</p>:<div className="v-program-list">{visible.map(program=><article key={program.id} className="v-program-row"><div><span className="v-program-kicker">{program.robot_type} / {program.environment_id.replaceAll('_',' ')}</span><h3>{program.name}</h3><p>{program.scope}</p>{program.missing_capability&&<p className="v-program-gap">Needed: {program.missing_capability}</p>}</div><div className="v-program-action"><span>{program.status==='executable'?'Bounded task tested':'Not implemented'}</span>{program.category==='humanoids'?<button type="button" className="primary" disabled={busy} onClick={()=>{onInspect(program);setExpanded(false);}}>Open physical task</button>:program.status==='executable'&&program.default_configuration&&<button type="button" className="primary" disabled={busy||!!opening} onClick={()=>void open(program)}>{opening===program.id?'Opening…':'Open experiment'}</button>}</div></article>)}</div>}
    </div>
    {error&&<p className="v-program-error" role="alert">{error} <button type="button" onClick={()=>void refresh()}>Retry</button></p>}
  </section>;
}
