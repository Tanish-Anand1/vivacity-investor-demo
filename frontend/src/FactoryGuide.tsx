import {useEffect,useState,type Dispatch,type SetStateAction} from 'react';
import {errorMessage} from './api';
import {factoryApi,type FactoryBenchmarkRecord,type FactoryCell,type FactoryFrame,type FactoryRun} from './factoryApi';

type BenchmarkView={frame:FactoryFrame;status:string}|null;
type Props={
 cell:FactoryCell;
 run:FactoryRun|null;
 blocked:boolean;
 onStart:()=>void;
 onLoadChallenge:()=>void;
 onResearch:()=>void;
 setBenchmarkBusy:Dispatch<SetStateAction<boolean>>;
 setBenchmarkView:Dispatch<SetStateAction<BenchmarkView>>;
 setBenchmarkId:Dispatch<SetStateAction<string|undefined>>;
};

const running=(status:string)=>['queued','running','paused'].includes(status);
export function isGripChallenge(cell:FactoryCell){
 const c=cell.config;
 return c.carton_count===1&&Math.abs(c.carton_start_y_m+.4)<.0001&&Math.abs(c.carton_mass_kg-.06)<.0001&&
  Math.abs(c.carton_friction-.8)<.0001&&Math.abs(c.gripper_force_scale-.008)<.0001;
}

export default function FactoryGuide({cell,run,blocked,onStart,onLoadChallenge,onResearch,setBenchmarkBusy,setBenchmarkView,setBenchmarkId}:Props){
 const [force,setForce]=useState(1),[job,setJob]=useState<FactoryBenchmarkRecord|null>(null),[pending,setPending]=useState(false),[error,setError]=useState<string|null>(null);
 const challenge=isGripChallenge(cell);
 const baseline=run?.cell_id===cell.id&&run.mode!=='conveyor'?run:null;
 const baselineFinished=!!baseline&&!running(baseline.status);
 const benchmarking=!!job&&running(job.status);
 const canCompare=challenge&&baselineFinished&&!blocked&&!benchmarking&&Math.abs(force-cell.config.gripper_force_scale)>.0001;

 useEffect(()=>{let live=true;setJob(null);setError(null);
  factoryApi.benchmarks().then(records=>{if(live){const saved=records.find(record=>record.cell_id===cell.id)??null;setJob(saved);if(saved?.request?.changes.gripper_force_scale!==undefined)setForce(saved.request.changes.gripper_force_scale);}}).catch(e=>{if(live)setError(errorMessage(e));});
  return()=>{live=false;};
 },[cell.id]);
 useEffect(()=>{setBenchmarkBusy(benchmarking);setBenchmarkView(benchmarking&&job?.active_frame?{frame:job.active_frame,status:job.status}:null);setBenchmarkId(job?.id);
 },[benchmarking,job?.active_frame,job?.status,job?.id,setBenchmarkBusy,setBenchmarkView,setBenchmarkId]);
 useEffect(()=>()=>{setBenchmarkBusy(false);setBenchmarkView(null);},[setBenchmarkBusy,setBenchmarkView]);
 useEffect(()=>{if(!benchmarking||!job)return;let live=true;let timer:ReturnType<typeof setTimeout>;
  async function poll(){try{const value=await factoryApi.benchmark(job!.id);if(live){setJob(value);setError(null);}}catch(e){if(live)setError(errorMessage(e));}finally{if(live)timer=setTimeout(poll,900);}}
  timer=setTimeout(poll,900);return()=>{live=false;clearTimeout(timer);};
 },[job?.id,benchmarking]);
 async function startComparison(){if(!canCompare)return;setPending(true);setError(null);try{
  const value=await factoryApi.startBenchmark(cell.id,{name:'Grip force intervention',repeats:2,held_out_repeats:1,changes:{gripper_force_scale:force}});
  setJob(value);
 }catch(e){setError(errorMessage(e));}finally{setPending(false);}}
 async function command(action:'pause'|'resume'|'stop'){if(!job)return;setPending(true);setError(null);try{setJob(await factoryApi.benchmarkControl(job.id,action));}catch(e){setError(errorMessage(e));}finally{setPending(false);}}
 const partitions=job?.comparison.partitions;
 const training=partitions?.training,heldOut=partitions?.held_out;
 return <section className="lab-guide" aria-label="Guided factory experiment">
  <div className="lab-guide-intro"><span className="factory-eyebrow">Case 01 / Contact handling</span><h2>A package loses its grip.</h2><p>Can one physical change help the robot deliver it? Test the same MuJoCo world under two conditions.</p></div>
  {!challenge&&<div className="lab-guide-recovery"><p>This saved cell has different conditions. Load the guided challenge to test a measured drop, or open Research to inspect the saved experiment.</p><button disabled={blocked} onClick={onLoadChallenge}>Load challenge world</button><button onClick={onResearch}>Inspect saved evidence</button></div>}
  {challenge&&<ol className="lab-steps">
   <li><span className="lab-step-number">01</span><div><h3>Observe the failure</h3><p>Run a one-carton baseline from a saved initial world state.</p><button className="primary" disabled={!challenge||blocked||benchmarking} onClick={()=>{setJob(null);onStart();}}>{running(baseline?.status??'')?'Baseline running…':baselineFinished?'Run baseline again':'Run baseline'}</button>
    {baseline&&<p className="lab-outcome" role="status">{running(baseline.status)?`${baseline.phase.replaceAll('_',' ')} · ${(baseline.frame?.time??0).toFixed(1)} simulated seconds`:`${baseline.status} · ${Number(baseline.metrics.cartons_sorted??0)} of ${cell.config.carton_count} delivered${baseline.status==='failed'?` · ${baseline.phase.replaceAll('_',' ')}`:''}`}</p>}
   </div></li>
   <li><span className="lab-step-number">02</span><div><h3>Explore an alternative</h3><p>Change only the gripper force. The backend will run matched training and held-out trials for both conditions.</p><label className="lab-force">Gripper force scale <output>{force.toFixed(3)}</output><input type="range" min="0.005" max="1" step="0.005" value={force} disabled={!challenge||benchmarking||blocked} onChange={event=>setForce(Number(event.target.value))}/></label>
    <button disabled={!canCompare||pending} onClick={startComparison}>{benchmarking?'Testing physical trials…':'Test both conditions · 6 trials'}</button>
    {!baselineFinished&&<p className="lab-hint">First observe the baseline to unlock the comparison.</p>}
   </div></li>
   <li><span className="lab-step-number">03</span><div><h3>Compare the evidence</h3>{!job?<p>The result will show actual delivery counts and failure reasons. No outcome is chosen in advance.</p>:<>
    <p className="lab-outcome" role="status">{job.status} · {job.trials.length} / {job.total_trials} physical trials{job.active_phase?` · ${job.active_phase.replaceAll('_',' ')}`:''}</p>
    {benchmarking&&<div className="lab-benchmark-actions"><button disabled={pending} onClick={()=>command(job.status==='paused'?'resume':'pause')}>{job.status==='paused'?'Resume trials':'Pause trials'}</button><button disabled={pending} onClick={()=>command('stop')}>Stop trials</button>{job.trials.length>0&&<button onClick={onResearch}>Inspect completed trials while testing continues</button>}</div>}
    {job.error&&<p role="alert">{job.error}</p>}
    {training&&<table className="lab-comparison" aria-label="Measured comparison"><thead><tr><th scope="col">Condition</th><th scope="col">Training</th><th scope="col">Held-out</th></tr></thead><tbody>{(['baseline','candidate'] as const).map(condition=><tr key={condition}><th scope="row">{condition==='baseline'?'Weak grip':`Force ${force.toFixed(3)}`}</th><td>{training[condition]?.successes??0}/{training[condition]?.trials??0} delivered</td><td>{heldOut?.[condition]?.successes??0}/{heldOut?.[condition]?.trials??0} delivered</td></tr>)}</tbody></table>}
    {!benchmarking&&job.trials.length>0&&<><p className="lab-result">{job.comparison.selected_condition==='candidate'?'The intervention performed better in these simulated training trials.':job.comparison.selected_condition==='baseline'?'The baseline performed better in these simulated training trials.':job.comparison.selected_condition==='tie'?'The training conditions tied.':'No condition met the selection criterion.'}</p><p className="lab-hint">{job.comparison.selection_reason} Held-out runs are reported separately. This does not validate performance on hardware.</p><button onClick={onResearch}>Inspect trials and replay</button></>}
   </>}</div></li>
  </ol>}
  {error&&<p role="alert" className="notice">{error}</p>}
  <p className="lab-guide-foot">Simulation evidence · MuJoCo dynamics · one carton · seeded starts</p>
 </section>;
}
