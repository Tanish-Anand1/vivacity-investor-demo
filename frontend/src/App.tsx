import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, ArrowsClockwise, SlidersHorizontal, Warning, X } from '@phosphor-icons/react';
import { useRuntime, isBusy } from './useRuntime';
import { API, BACKEND, api, errorMessage } from './api';
import { format, robotFrame, clothFrame, type Backend, type Branch, type RobotFrame, type ClothFrame, type Vec3 } from './domain';
import { objectHalfSizes, placementAwayFrom } from './pickupWorkspace';
import Settings from './Settings';
import ClothSettings from './ClothSettings';
import TechnicalInspector from './TechnicalInspector';
import ResultCard from './ResultCard';
import IsabellaHome from './IsabellaHome';
import LabOpening from './LabOpening';
import { DEFAULT_SELECTION, selectionKey, type Selection } from './TemplatePicker';
import ExperimentSetup from './ExperimentSetup';
import {workspaceApi,defaultConfiguration,type Configuration,type SavedConfiguration,type LibraryWorld} from './workspaceApi';
import './studio.css';
import defaultWorkcell from './generated/defaultWorkcell.json';
import EngineeringPanel from './EngineeringPanel';
import type {OverlayOptions} from './EngineeringOverlay';
const defaultOverlays:OverlayOptions={forces:true,velocity:true,center:true,trajectory:false,collision:false};
import './engineering.css';
import './labOpening.css';

const FactoryWorkspace=lazy(()=>import('./FactoryWorkspace'));
const RobotView=lazy(()=>import('./RobotView'));
const ClothView=lazy(()=>import('./ClothView'));
const ImportWorld=lazy(()=>import('./ImportWorld'));
const WorldLibrary=lazy(()=>import('./WorldLibrary'));
const ExperimentLibrary=lazy(()=>import('./ExperimentLibrary'));

export default function App(){
  const [showOpening,setShowOpening]=useState(()=>{try{return window.location.pathname==='/'&&localStorage.getItem('vivacity:isabella-intro-complete')!=='1'&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches;}catch{return false;}});
  const finishOpening=useCallback(()=>{try{localStorage.setItem('vivacity:isabella-intro-complete','1');}catch{ /* Storage may be disabled. */ }setShowOpening(false);requestAnimationFrame(()=>document.getElementById('isabella-main')?.focus());},[]);
  const [guidedAutostart,setGuidedAutostart]=useState(()=>new URLSearchParams(window.location.search).get('guided')==='1');
  const [activeTemplate,setActiveTemplate]=useState<{selection:Selection;backend:Backend;config:Record<string,unknown>;key?:string;name?:string;configurationId?:string}>({selection:DEFAULT_SELECTION,backend:'mujoco',config:defaultWorkcell,key:'curated-warehouse-v1',name:'Franka Panda / Industrial warehouse / Pick and place'});
  const [draft,setDraft]=useState<Configuration>(defaultConfiguration('warehouse'));
  type Page='home'|'factory'|'workspace'|'worlds'|'experiments'|'results'|'settings'|'import';
  const routePage=(path:string):Page=>path==='/lab'?'factory':path==='/workspace'?'workspace':path==='/worlds'?'worlds':path==='/experiments'?'experiments':path==='/settings'?'settings':path==='/import'?'import':'home';
  const [page,setPage]=useState<Page>(()=>routePage(window.location.pathname));
  const navigate=useCallback((next:Page,path:string,guided=false)=>{window.history.pushState({},'',path);setGuidedAutostart(guided);setPage(next);window.scrollTo(0,0);},[]);
  useEffect(()=>{const back=()=>{setPage(routePage(window.location.pathname));setGuidedAutostart(new URLSearchParams(window.location.search).get('guided')==='1');};window.addEventListener('popstate',back);return()=>window.removeEventListener('popstate',back);},[]);
  const [inspecting,setInspecting]=useState(false),[inspectSelection,setInspectSelection]=useState<'object'|'robot'|'experiment'>('object');
  const [overlays,setOverlays]=useState<OverlayOptions>(defaultOverlays);
  const setupSummary=useRef<HTMLElement>(null);
  const [setupOpen,setSetupOpen]=useState(false);
  const [setupStep,setSetupStep]=useState(0);
  const [preparing,setPreparing]=useState(false);
  const [visualWorld,setVisualWorld]=useState<LibraryWorld|undefined>();
  useEffect(()=>{
    if(page!=='workspace'||visualWorld)return;
    let active=true;
    workspaceApi.world(draft.environment_id).then(world=>{if(active)setVisualWorld(world);}).catch(()=>{});
    return()=>{active=false;};
  },[page,draft.environment_id,visualWorld]);
  const backend=activeTemplate.backend,cloth=backend==='cloth';
  const rt=useRuntime(backend,activeTemplate.key??selectionKey(activeTemplate.selection),activeTemplate.config,activeTemplate.configurationId,page!=='factory'&&page!=='home');
  const [branchId,setBranchId]=useState<string|null>(null),[editing,setEditing]=useState(false),[downloadError,setDownloadError]=useState<string|null>(null);
  const compatible=rt.world?.backend===backend&&(rt.world.config.robot_model??'panda')===(activeTemplate.config.robot_model??'panda'),branches=compatible?rt.branches:[];
  const ranked=useMemo(()=>{
    const ids=rt.experiment?.result.top_feasible_branch_ids as string[]|undefined;
    if(ids)return ids.map(id=>branches.find(b=>b.id===id)).filter((b):b is Branch=>!!b&&b.evaluation.success).slice(0,3);
    return branches.filter(b=>b.evaluation.success&&b.action.execution_role!=='authoritative_execution')
      .sort((a,b)=>Number(b.id===rt.experiment?.selected_branch_id)-Number(a.id===rt.experiment?.selected_branch_id)).slice(0,3);
  },[branches,rt.experiment]);
  const selected=branches.find(b=>b.id===branchId)??ranked[0];
  const currentFrame=compatible?(cloth?clothFrame(rt.observation):robotFrame(rt.observation)):null;
  const frames=useMemo(()=>currentFrame?[currentFrame]:[],[currentFrame]);
  const cursor=useRef(0);cursor.current=0;
  const config=compatible?rt.world?.config??{}:{};
  const terminal=compatible&&rt.experiment&&!isBusy(rt.experiment);
  const status=!rt.loaded?'Initializing':!rt.online?'Connection lost':rt.mutating?'Applying change':
    rt.session?.status==='stopping'?'Stopping safely':rt.session?.paused?'Simulation paused':
    rt.session?.pause_requested?'Pausing safely':isBusy(rt.experiment)&&rt.liveState?.stage==='testing_candidates'?'Testing real physics':
    isBusy(rt.experiment)&&rt.liveState?.stage==='executing'?'Live physics execution':
    isBusy(rt.experiment)?rt.experiment?.status==='queued'?'Queued':'Evaluating alternatives':
    rt.experiment?.stale?'World changed · run again':
    rt.experiment?.status==='cancelled'?'Cancelled':rt.experiment?.status==='failed'?'Experiment failed':
    rt.experiment?.result.execution_evaluation&&!(rt.experiment.result.execution_evaluation as {success:boolean}).success?'Execution failed':
    terminal&&rt.experiment?.selected_branch_id?'Task verified':terminal?'No feasible result':'Ready to start';
  const counters=Object.assign({},...rt.events.filter(e=>e.kind==='progress').map(e=>e.details),rt.experiment?.result.search??{}) as Record<string,unknown>;
  const disabled=preparing||rt.mutating||!compatible||!rt.online;
  const canMoveCube=backend==='mujoco'&&!disabled&&!rt.active&&!isBusy(rt.experiment)&&config.scene_profile!=='orbital_salvage';
  const moveCube=async(point:Vec3)=>{
    const sizes=objectHalfSizes(config),destination=placementAwayFrom(point,config.placement_position as Vec3,sizes);
    if(config.physical_operation==='stacking')destination[2]=3*sizes[2]+.001;
    return rt.apply({...config,cube_position:point,placement_position:destination});
  };
  useEffect(()=>{setBranchId(null);setEditing(false);},[backend,rt.experiment?.id]);
  const loadConfiguration=async(saved:SavedConfiguration,world:LibraryWorld)=>{
    await rt.stop();const resolved=await workspaceApi.resolve(saved.configuration);
    setVisualWorld(world);
    setDraft(saved.configuration);setActiveTemplate({selection:DEFAULT_SELECTION,backend:resolved.world.backend,
      config:resolved.world.config as Record<string,unknown>,key:'configuration:'+saved.id,configurationId:saved.id,
      name:`${saved.configuration.robot_id} / ${world.name} / ${saved.configuration.operation_id.replaceAll('_',' ')}`});
    setInspecting(false);setSetupOpen(false);if(window.location.pathname!=='/workspace')navigate('workspace','/workspace');else setPage('workspace');setupSummary.current?.focus();
  };
  const prepare=async(configuration:Configuration,step:number)=>{
    if(preparing)return;setPreparing(true);setDownloadError(null);setInspecting(false);if(window.location.pathname!=='/workspace')navigate('workspace','/workspace');else setPage('workspace');setDraft(configuration);
    try{const [saved,world]=await Promise.all([workspaceApi.save(configuration),workspaceApi.world(configuration.environment_id)]);await loadConfiguration(saved,world);setSetupStep(step);setSetupOpen(true);}
    catch(e){setDownloadError(errorMessage(e));}finally{setPreparing(false);}
  };
  const chooseWorld=(world:LibraryWorld)=>prepare({...draft,environment_id:world.id,...(world.id==='textile_fixture'?{operation_id:'cloth_fold' as const,gripper_id:'fold_fixture' as const,robot_id:'panda' as const}:draft.operation_id==='cloth_fold'?{operation_id:'pick_place' as const,gripper_id:'panda_parallel' as const}:{})},0);


  return <>{page==='home'?<IsabellaHome enterLab={()=>navigate('factory','/lab')} watchExperiment={()=>navigate('factory','/lab?guided=1',true)} openWorlds={()=>navigate('worlds','/worlds')}/>:<>
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="site-header platform-nav"><a className="isabella-lab-brand" href="/" aria-label="Isabella Labs home">ISABELLA LABS <small>BY VIVACITY</small></a><nav className="main-nav" aria-label="Workspace navigation">
      {(['factory','workspace','worlds','experiments'] as const).map(id=><button key={id} aria-pressed={page===id} disabled={rt.mutating} onClick={()=>navigate(id,id==='factory'?'/lab':`/${id}`)}>{id==='factory'?'Laboratory':id[0].toUpperCase()+id.slice(1)}</button>)}
      <button className="nav-settings" aria-label="Runtime settings" onClick={()=>navigate('settings','/settings')}><SlidersHorizontal size={18}/></button>
    </nav></header>
    <main className="platform-main" id="workspace" tabIndex={-1}>
      {page==='factory'?<Suspense fallback={<p role="status" className="lab-entry-status">Preparing the physical world…</p>}><FactoryWorkspace startGuided={guidedAutostart}/></Suspense>:
       page==='worlds'?<Suspense fallback={<p>Loading world library…</p>}><WorldLibrary choose={chooseWorld} nativeImport={async()=>{await rt.stop();navigate('import','/import');}}/></Suspense>:
       page==='experiments'||page==='results'?<Suspense fallback={<p>Loading measured experiment history…</p>}><ExperimentLibrary load={loadConfiguration} current={compatible?rt.experiment:null} currentConfig={(branches[0]?.initial_state.config as Record<string,unknown>|undefined)??config} currentFriction={robotFrame(branches[0]?.trace.at(-1))?.inspection?.object.friction[0]}/></Suspense>:
       page==='settings'?<section className="library-area"><h1>Runtime settings</h1><p>API: {API}</p><p className="small">Provider keys stay in backend environment variables. World generation availability is shown in Worlds. This demo uses bounded shared compute and browser capabilities; it does not provide production user accounts or guaranteed uptime.</p><a href={`${BACKEND}/docs`} target="_blank" rel="noreferrer">API and schema reference</a></section>:
       page==='import'?<><button className="secondary" onClick={()=>navigate('worlds','/worlds')}>Back to world library</button><Suspense fallback={<div className="viewport-loading">Loading import tools…</div>}><ImportWorld/></Suspense></>:<>
        <div className="workspace-heading"><div><h1>Physical experiments</h1><p>Configure a task. Test alternatives. Inspect measured results.</p></div><span className="connection" role="status">{rt.online?'Physics connected':'Connecting to runtime…'}</span></div>
        {preparing&&<p role="status" className="small">Loading the selected physical configuration…</p>}
        {rt.recoveryNotice&&<p role="status" className="small">{rt.recoveryNotice}</p>}
        <nav className="journey" aria-label="Experiment stages">{['Environment','Robot','Operation','Experiment'].map((label,i)=><button key={label} aria-pressed={setupOpen&&setupStep===i} disabled={rt.active} onClick={()=>{setInspecting(false);setSetupStep(i);setSetupOpen(true);setEditing(false);}}><span>0{i+1}</span>{label}</button>)}</nav>
        {!rt.online&&rt.loaded&&<div className="offline-notice" role="status"><Warning size={18}/><span>Simulation runtime unavailable.</span><button onClick={rt.reconnect}>Reconnect</button></div>}
        {downloadError&&<p className="negative" role="alert">{downloadError}</p>}
        {rt.error&&<div className="error-notice" role="alert"><Warning size={18}/><span>{rt.error}</span>{!rt.online&&<button onClick={rt.reconnect}>Reconnect</button>}<button className="icon-button" aria-label="Dismiss error" onClick={rt.clearError}><X size={17}/></button></div>}
        <div className="workbench">
          <section className="visual-area" aria-label="Live simulation">
            {cloth?<Suspense fallback={<div className="viewport-loading">Loading cloth…</div>}><ClothView frames={frames as ClothFrame[]} cursor={cursor} time={currentFrame?.time??0} playing={false} config={config}/></Suspense>:
              <Suspense fallback={<div className="viewport-loading">Loading workcell…</div>}><RobotView frames={frames as RobotFrame[]} cursor={cursor} config={config} replaying={false} playing={false} renderTime={currentFrame?.time??0} canMoveCube={canMoveCube} onMoveCube={moveCube} visualWorld={visualWorld} overlays={inspecting?overlays:undefined} trace={rt.experiment?.stale?[]:(selected?.trace??[]).filter((f):f is RobotFrame=>!!robotFrame(f))} onSelect={s=>{setInspectSelection(s);setInspecting(true);setSetupOpen(false);}}/></Suspense>}
            <div className="simulation-strip"><div><span>Simulation time</span><strong>{format(currentFrame?.time??0)} s</strong><small>{status}</small></div>{!cloth&&<button className="secondary" aria-pressed={inspecting} onClick={()=>{setInspecting(v=>!v);setSetupOpen(false);}}>Engineering inspection</button>}</div>
            {inspecting&&!cloth&&<details className="overlay-controls"><summary>Inspection overlays & legend</summary><div>{Object.entries(overlays).map(([id,on])=><label key={id}><input type="checkbox" checked={on} onChange={e=>setOverlays(o=>({...o,[id]:e.target.checked}))}/>{({forces:'Contact / applied forces',velocity:'Linear / angular velocity',center:'Center of mass',trajectory:'Recorded object trajectory',collision:'Robot collision geometry'} as Record<string,string>)[id]}</label>)}</div><p className="small">Amber: contact forces. Coral: applied force. Purple: torque. Teal: velocity / path. Blue: angular velocity. Vector lengths are scaled and capped for visibility. Trajectories use recorded samples from this experiment; this is not a video.</p></details>}
            <div className="experiment-actions">
              <button className="primary run-button" disabled={disabled||rt.active} onClick={rt.run}>Start experiments<ArrowRight size={18}/></button>
              {rt.active&&<button className="secondary" disabled={disabled||rt.session?.status==='stopping'} onClick={rt.togglePause}>{rt.session?.pause_requested?'Resume simulation':'Pause simulation'}</button>}
              {rt.active&&<button className="secondary" disabled={disabled||rt.session?.status==='stopping'} onClick={async()=>{try{await rt.stop();}catch(e){setDownloadError(errorMessage(e));}}}>Stop experiments</button>}
              <button className="secondary" disabled={disabled} onClick={()=>{setInspecting(false);setSetupOpen(false);setEditing(e=>!e);}}><SlidersHorizontal size={18}/>{cloth?'Cloth settings':'Change conditions'}</button>
              <button className="secondary" disabled={disabled} onClick={rt.reset}><ArrowsClockwise size={18}/>Reset world</button>
            </div>
            {backend==='mujoco'&&<p className="small" role="status">The search tests physical alternatives until measured improvement levels off or this host reaches its compute budget. Progress below counts completed backend simulations.</p>}
          </section>
          <aside className="results" aria-label="Verified results">
            {inspecting&&!cloth?<EngineeringPanel frame={robotFrame(currentFrame)} selection={inspectSelection} select={setInspectSelection}/>:setupOpen?<><div className="context-heading"><h2>Configure experiment</h2><button aria-label="Close configuration" className="icon-button" onClick={()=>setSetupOpen(false)}><X size={16}/></button></div><ExperimentSetup initial={draft} load={loadConfiguration} worldsPage={()=>navigate('worlds','/worlds')} step={setupStep} setStep={setSetupStep}/></>:<>
            <div className="section-heading"><h2>{cloth?'Best verified folds':'Best verified placements'}</h2><span className="status-label" data-testid="experiment-status" aria-live="polite">{status}</span></div>
            {backend==='mujoco'&&config.task==='pick_place'&&config.scene_profile!=='orbital_salvage'&&<details className="sensor-details"><summary>Simulator object localization</summary><p className="sensor-summary" data-testid="object-perception" role="status">{rt.active?'Object localization pauses during physical execution.':rt.perception?.detected&&rt.perception.estimated_xy_m?`Simulated depth sensing: object at X ${format(rt.perception.estimated_xy_m[0])} m, Y ${format(rt.perception.estimated_xy_m[1])} m from ${rt.perception.visible_cube_rays} MuJoCo rays.`:rt.perception?'Object is not visible to the simulated overhead sensor.':'Locating the object…'} <span>Simulator labels, not a real camera.</span></p></details>}
            {editing&&rt.world?cloth?<ClothSettings key={rt.world.id} config={rt.world.config} disabled={disabled} apply={rt.apply} close={()=>setEditing(false)}/>:
              <Settings key={rt.world.id} config={rt.world.config} disabled={disabled} apply={rt.apply} close={()=>setEditing(false)}/>:<>
              {!ranked.length?<p className="results-empty">{rt.busy?'Computing and validating independent alternatives…':terminal&&rt.experiment?.selected_branch_id?'Loading measured results…':terminal?'No feasible candidate. Measured failures are retained below.':rt.loaded?'Choose Start experiments when you’re ready. You can change the settings first.':'Initializing an actual physical world…'}</p>:
                ranked.map((b,i)=><ResultCard key={b.id} branch={b} rank={i} selected={b.id===selected?.id} choose={()=>setBranchId(b.id)} download={()=>{setDownloadError(null);api.download(b.experiment_id,b.id).catch(e=>setDownloadError(errorMessage(e)));}}/>)}
              {downloadError&&<p role="alert" className="negative">{downloadError}</p>}
              <p className="decision" data-testid="decision">{compatible?String(rt.experiment?.error??rt.experiment?.result.conclusion??''):''}</p>
              {rt.experiment?.stale&&<p className="stale-warning" data-testid="stale-warning">The world changed. These results describe its previous configuration.</p>}
            </>}
            </>}
          </aside>
        </div>
        {counters.generated!==undefined&&<dl className="search-counts" aria-label="Actual search work">{[['Generated','generated'],['Screened','screened'],['Passed screening','screening_passed'],[cloth?'Validation rollouts':'Physics trials','fully_simulated'],['Verified feasible','verified_feasible']].map(([name,key])=><div key={key}><dt>{name}</dt><dd data-testid={`count-${key}`}>{Number(counters[key]??0).toLocaleString()}{!cloth&&!counters.adaptive_stopping&&key==='fully_simulated'&&Number(counters.physics_target)>0?` / ${Number(counters.physics_target).toLocaleString()}`:''}</dd></div>)}</dl>}
        <TechnicalInspector events={rt.events} initialized={compatible} playing={false} branches={branches} select={setBranchId} history={{ids:rt.session?.experiments??[],open:rt.history,disabled:rt.mutating}}/>
        
      </>}
    </main>
    <footer className="platform-footer"><span>Viva Physics</span><a href={`${BACKEND}/docs`} target="_blank" rel="noreferrer">API reference <ArrowRight size={14}/></a></footer>
    </>}
    {showOpening&&page==='home'&&<LabOpening finish={finishOpening}/>}
  </>;
}
