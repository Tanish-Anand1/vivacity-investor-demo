import {useEffect,useRef,useState} from 'react';
import FactoryView,{type FactoryViewMode} from './FactoryView';
import {factoryApi,factoryDefaults,type FactoryCell,type FactoryRun,type FactorySettings,type FactoryFrame} from './factoryApi';
import {APIError,errorMessage} from './api';
import FactoryObservation from './FactoryObservation';
import FactoryAnalysis from './FactoryAnalysis';
import FactoryBenchmark from './FactoryBenchmark';
import FactoryExchange from './FactoryExchange';
import FactoryProjects from './FactoryProjects';
import type {FactoryImport} from './factoryApi';
import type {Vec3} from './domain';
import {editableFactorySettings,factorySettingsIssue} from './factorySettings';
import FactoryGuide,{isGripChallenge} from './FactoryGuide';
import './factory.css';
import './lab.css';

const flagshipSettings:FactorySettings={...factoryDefaults,name:'Grip-force laboratory',carton_count:1,carton_start_y_m:-.4,realtime_speed:8,gripper_force_scale:.008};

export default function FactoryWorkspace({startGuided=false}:{startGuided?:boolean}){
 const guidedStarted=useRef(false);
 const [mode,setMode]=useState<FactoryViewMode>('fidelity'),[cell,setCell]=useState<FactoryCell|null>(null),[run,setRun]=useState<FactoryRun|null>(null),[inspectionRun,setInspectionRun]=useState<FactoryRun|null>(null),[error,setError]=useState<string|null>(null),[busy,setBusy]=useState(false),[draft,setDraft]=useState<FactorySettings>(factoryDefaults),[inspected,setInspected]=useState<FactoryFrame|null>(null),[trajectory,setTrajectory]=useState<Vec3[]>([]),[benchmarkBusy,setBenchmarkBusy]=useState(false),[benchmarkView,setBenchmarkView]=useState<{frame:FactoryFrame;status:string}|null>(null);
 const [experience,setExperience]=useState<'explore'|'research'>('explore');
 const [creatorLabel,setCreatorLabel]=useState(''),[benchmarkId,setBenchmarkId]=useState<string|undefined>();
 const [imported,setImported]=useState<FactoryImport|null>(null);
 const active=!!run&&['queued','running','paused'].includes(run.status);
 async function load(){
  const id=localStorage.getItem('vivacity:factory-cell');let value:FactoryCell;
  try{value=id?await factoryApi.cell(id):await factoryApi.create(flagshipSettings);}catch(e){if(e instanceof APIError&&e.status===404)value=await factoryApi.create(flagshipSettings);else throw e;}
  let shouldStart=false;
  if(startGuided&&!guidedStarted.current){
   if(!isGripChallenge(value))value=await factoryApi.create(flagshipSettings);
   guidedStarted.current=true;shouldStart=true;
  }
  setCell(value);setDraft(editableFactorySettings(factoryDefaults,value.config));localStorage.setItem('vivacity:factory-cell',value.id);
  if(shouldStart){setBusy(true);try{setRun(await factoryApi.start(value.id,'production'));}finally{setBusy(false);}}
  else if(value.last_run_id)setRun(await factoryApi.run(value.last_run_id));
 }
 useEffect(()=>{load().catch(e=>setError(errorMessage(e)));},[]);
 useEffect(()=>{if(!active||!run)return;let alive=true,timer:ReturnType<typeof setTimeout>;
  async function poll(){try{const value=await factoryApi.run(run!.id);if(alive){setRun(value);setError(null);}}catch(e){if(alive)setError(errorMessage(e));}finally{if(alive)timer=setTimeout(poll,160);}}
  timer=setTimeout(poll,160);return()=>{alive=false;clearTimeout(timer);};
 },[run?.id,active]);
 async function action(fn:()=>Promise<void>){setBusy(true);setError(null);try{await fn();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}
 function showCell(value:FactoryCell,nextRun:FactoryRun|null=null){
  setCell(value);setDraft(editableFactorySettings(factoryDefaults,value.config));setRun(nextRun);setInspectionRun(null);setInspected(null);setTrajectory([]);setBenchmarkView(null);setBenchmarkId(undefined);
  localStorage.setItem('vivacity:factory-cell',value.id);
 }
 const settingsIssue=factorySettingsIssue(draft);
 const command=(value:'pause'|'resume'|'stop'|'emergency_stop')=>action(async()=>{if(run)setRun(await factoryApi.control(run.id,value));});
  const frame=inspected??inspectionRun?.frame??benchmarkView?.frame??run?.frame??cell?.frame??null;
 return <section className={`factory-workspace lab-workspace lab-${experience}`}>
  <header className="factory-heading lab-heading"><div><span className="factory-eyebrow">Isabella Labs / Robotic handling</span><h1>Build a world. Test what could happen.</h1><p>Observe a physical failure, change one condition, and compare the outcomes before touching a production line.</p></div><div className="lab-heading-controls"><div className="lab-mode-switch" role="group" aria-label="Laboratory depth"><button aria-pressed={experience==='explore'} onClick={()=>{setInspectionRun(null);setInspected(null);setExperience('explore');}}>Explore</button><button aria-pressed={experience==='research'} onClick={()=>setExperience('research')}>Research</button></div>{experience==='research'&&<label>View<select value={mode} onChange={e=>setMode(e.target.value as FactoryViewMode)}><option value="fidelity">High fidelity</option><option value="performance">Performance</option><option value="engineering">Engineering</option></select></label>}</div></header>
  {error&&<div role="alert" className="notice">{error} <button onClick={()=>action(load)}>Reconnect</button></div>}
  {inspectionRun&&<p className="factory-stage-note" role="status">Inspecting recorded trial {inspectionRun.id}. The original comparison and its cell remain selected. Return to latest to follow the ongoing simulation.</p>}
  {inspected&&!benchmarkBusy&&<p className="factory-stage-note" role="status">Viewport: recorded sample at {inspected.time.toFixed(3)} s. {active?'Production continues on the backend.':''}Use “Return to latest” in the analysis controls to leave inspection.</p>}
  <div className="lab-stage">
   {experience==='explore'&&cell&&<FactoryGuide key={cell.id} cell={cell} run={run} blocked={active||benchmarkBusy||busy} onStart={()=>action(async()=>setRun(await factoryApi.start(cell.id,'production',creatorLabel)))} onLoadChallenge={()=>action(async()=>showCell(await factoryApi.create(flagshipSettings)))} onResearch={()=>setExperience('research')} setBenchmarkBusy={setBenchmarkBusy} setBenchmarkView={setBenchmarkView} setBenchmarkId={setBenchmarkId}/>}
   <div className="lab-world"><FactoryView frame={frame} mode={mode} geometry={cell?.collision_geometry} trajectory={trajectory} status={benchmarkView?.status??run?.status??'idle'}/>
    <div className="lab-world-status"><strong role="status">{benchmarkView?'Comparing conditions · '+(benchmarkView.frame.phase??'initializing').replaceAll('_',' '):run?run.status.replaceAll('_',' ')+' · '+run.phase.replaceAll('_',' '):(cell?'World ready':'Connecting to simulator')}</strong><span data-testid="factory-clock">{(frame?.time??0).toFixed(3)} s · simulation time</span></div>
   </div>
  </div>
  {experience==='explore'&&active&&<div className="lab-run-controls"><button disabled={busy} onClick={()=>command(run?.status==='paused'?'resume':'pause')}>{run?.status==='paused'?'Resume simulation':'Pause simulation'}</button><button disabled={busy} onClick={()=>command('stop')}>Stop simulation</button></div>}
  {experience==='research'&&<div className="factory-control-bar"><div><strong role="status">{benchmarkView?'Benchmark '+benchmarkView.status+' · '+(benchmarkView.frame.phase??'initializing').replaceAll('_',' '):run?run.status.replaceAll('_',' ')+' · '+run.phase.replaceAll('_',' '):(cell?'Ready':'Connecting')}</strong><span>Backend state and controls</span></div><div className="factory-actions">
   <button className="primary" disabled={!cell||active||benchmarkBusy||busy} onClick={()=>action(async()=>{if(cell)setRun(await factoryApi.start(cell.id,'production',creatorLabel));})}>Start production</button>
   <button disabled={!active||busy} onClick={()=>command(run?.status==='paused'?'resume':'pause')}>{run?.status==='paused'?'Resume':'Pause'}</button>
   <button disabled={!active||busy} onClick={()=>command('stop')}>Stop</button>
   <button className="factory-estop" disabled={!active||busy} onClick={()=>command('emergency_stop')}>Emergency simulation stop</button>
   <button disabled={active||benchmarkBusy||busy||!cell} onClick={()=>action(async()=>{const value=await factoryApi.create(cell?.config??factoryDefaults);showCell(value);})}>Reset</button>
  </div></div>}
  {!benchmarkBusy&&run?.error&&<p role="alert" className="notice">{run.error}</p>}
  {experience==='research'&&<>{!benchmarkBusy&&<div className="factory-counts"><span><strong>{Number(run?.metrics.cartons_sorted??run?.events.filter(e=>e.kind==='destination_arrival').length??0)}</strong> / {cell?.config.carton_count??3} cartons sorted</span><span><strong>{run?.events.filter(e=>e.kind==='station_arrival').length??0}</strong> station arrivals</span><span>Lane A &lt; {(cell?.config.sort_threshold_kg??.07)*1000} g · Lane B ≥ {(cell?.config.sort_threshold_kg??.07)*1000} g</span></div>}
  <p className="factory-stage-note">Small-carton contact sorting. Control uses simulator mass and position. Camera observations are independently rendered on request. Emergency stop freezes this simulation, not physical hardware.</p>
  <details className="factory-readout"><summary>Production conditions</summary><fieldset disabled={active||benchmarkBusy||busy} className="factory-settings"><legend>New run configuration</legend>
   <label>Configuration name<input value={draft.name} maxLength={80} onChange={e=>setDraft({...draft,name:e.target.value})}/></label>
   {([['carton_count','Cartons',1,3,1],['carton_start_x_m','Initial carton X (m)',.465,.535,.005],['carton_start_y_m','Initial carton Y (m)',-1.28,-.35,.01],['carton_mass_kg','Reference mass (kg)',.02,.15,.01],['carton_half_size_m','Carton half-width (m)',.02,.03,.001],['carton_friction','Contact friction',.05,1.5,.05],['conveyor_speed_m_s','Conveyor speed (m/s)',.02,.18,.01],['arrival_interval_s','Minimum arrival spacing (s)',1,60,1],['sort_threshold_kg','Lane threshold (kg)',.02,.15,.01],['realtime_speed','Simulation speed',.25,8,.25],['gripper_force_scale','Gripper force scale',.005,1,.005]] as const).map(([key,label,min,max,step])=><label key={key}>{label}<input type="number" value={Number.isFinite(draft[key])?draft[key]:''} min={min} max={max} step={step} onChange={e=>setDraft({...draft,[key]:e.target.value===''?Number.NaN:e.target.valueAsNumber})}/></label>)}
   {settingsIssue&&<p className="factory-stage-note" role="status">{settingsIssue}</p>}
   <button disabled={busy||active||benchmarkBusy||!!settingsIssue} onClick={()=>action(async()=>{const value=await factoryApi.create(draft);showCell(value);})}>Apply conditions</button>
   <button disabled={!cell} onClick={()=>action(async()=>{if(cell)setRun(await factoryApi.start(cell.id,'conveyor',creatorLabel));})}>Test conveyor only</button>
  </fieldset><p className="factory-stage-note">Later cartons have seeded mass variation (0.7–1.6 × reference, limited to 20–150 g). A finite batch is integrated continuously; cartons are not teleported or respawned. Arrival spacing is a minimum because this cell handles one carton at a time.</p></details>
  <details className="factory-readout"><summary>Measured transport and event log</summary><dl>{Object.entries(frame?.conveyors??{}).map(([name,value])=><div key={name}><dt>{name.replaceAll('_',' ')}</dt><dd>{value.surface_speed_m_s.toFixed(3)} m/s</dd></div>)}</dl><ol>{run?.events.map((event,i)=><li key={i}>{event.time_s.toFixed(3)} s · {event.kind.replaceAll('_',' ')}</li>)}</ol></details>
  {cell&&<details className="factory-readout lab-provenance"><summary>World state and reproducibility</summary><p>The initial full physics state is saved with this cell. Production and benchmark trials restore independent copies; changing conditions creates a new cell and leaves prior evidence intact.</p><dl><div><dt>World ID</dt><dd>{cell.id}</dd></div><div><dt>Seed</dt><dd>{cell.config.seed}</dd></div><div><dt>Physics version</dt><dd>{cell.engine?.version??'Unavailable'}</dd></div><div><dt>World version</dt><dd>{cell.world_version??'Unavailable'}</dd></div><div><dt>Model SHA-256</dt><dd>{cell.initial_state?.model_hash??'Unavailable'}</dd></div><div><dt>Selected run</dt><dd>{run?.id??'No run selected'}</dd></div></dl><p>These are simulated outcomes. They have not been validated on a physical production line.</p></details>}
  {cell&&<FactoryProjects cellId={cell.id} runId={run?.id} benchmarkId={benchmarkId} disabled={active||benchmarkBusy||busy} onCreator={setCreatorLabel} onImport={value=>{setImported(value);showCell(value.cell);}} onRun={saved=>action(async()=>{const value=await factoryApi.cell(saved.cell_id);showCell(value,saved);})}/>}
  {cell&&<FactoryExchange cellId={cell.id} runId={run?.id} disabled={active||benchmarkBusy||busy} onImport={value=>{setImported(value);showCell(value.cell);}}/>}
  {cell&&<FactoryBenchmark key={`benchmark-${cell.id}`} onSelect={setBenchmarkId} baseline={cell.config} preset={imported?.benchmark_request??null} cellId={cell.id} disabled={active||busy} onBusy={setBenchmarkBusy} onFrame={setBenchmarkView} load={saved=>action(async()=>{const value=await factoryApi.cell(saved.cell_id);showCell(value,saved);})} inspectTrial={saved=>{setInspectionRun(saved);setInspected(null);setTrajectory([]);}}/>}
  {(inspectionRun||run)&&<FactoryAnalysis key={(inspectionRun??run)!.id} run={(inspectionRun??run)!} onInspect={value=>{setInspected(value);if(!value)setInspectionRun(null);}} onTrajectory={setTrajectory}/>}
  {cell&&!benchmarkBusy&&<FactoryObservation key={cell.id} cellId={cell.id} frame={inspected??frame} label={inspected?"Recorded":"Live"}/>}
  </>}
 </section>;
}
