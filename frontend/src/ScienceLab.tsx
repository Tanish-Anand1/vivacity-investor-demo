import {useEffect,useMemo,useState} from 'react';
import {api,APIError,errorMessage} from './api';
import type {Experiment,World} from './domain';
import SciencePlot from './SciencePlot';
import recorded from './generated/isabellaSciencePreview.json';
import './scienceLab.css';

type Scenario='signal'|'control';
type Draft={scenario:Scenario;seed:number;noise:number;samples:number;horizon:number;speed:number;trainFraction:number};
type ScienceFrame={time:number;observed_position:number[];predicted_position:number[];predicted_velocity:number[];split:'train'|'heldout'};
type ScienceEvaluation={success:boolean;status:string;hypothesis:string;fit_message?:string;parameters?:Record<string,number>;uncertainty?:{method:string;standard_errors:Record<string,number>;jacobian_rank:number;full_rank:boolean;active_bounds:number[];caveat:string};train_rmse?:number;heldout_rmse?:number;training_bic?:number;train_count?:number;heldout_count?:number;integration_calls?:number;optimizer_evaluations?:number};
type ScienceBranch={id:string;experiment_id:string;initial_state:{times:number[];observations:number[][];config:{train_fraction:number;perturbing_position:number[]}};action:{hypothesis:string;definition:string};trace:ScienceFrame[];evaluation:ScienceEvaluation;performance:{integration_calls?:number;wall_seconds?:number;physics_wall_seconds?:number}};
type Persisted={worldId:string;draft:Draft;history:string[]};
const STORAGE='vivacity:science-lab/1';
const initial:Draft={scenario:'signal',seed:7,noise:.001,samples:70,horizon:5,speed:1,trainFraction:.7};
const short=(id:string)=>id.slice(0,8);
const format=(n:number|undefined,digits=5)=>typeof n==='number'&&Number.isFinite(n)?n.toFixed(digits):'—';
const hypothesisName=(id:string)=>id==='central_only'?'Central gravity':'Additional influence';
function config(draft:Draft){return {central_mu:1,hidden_mass:draft.scenario==='signal'?.12:0,initial_state:[1,0,0,draft.speed],perturbing_position:[2.5,.4],noise_std:draft.noise,samples:draft.samples,horizon:draft.horizon,train_fraction:draft.trainFraction};}
function valid(d:Draft){return Number.isInteger(d.seed)&&d.seed>=0&&d.seed<=4294967295&&Number.isInteger(d.samples)&&d.samples>=30&&d.samples<=200&&d.noise>=.00001&&d.noise<=.05&&d.horizon>=2&&d.horizon<=8&&d.speed>=.85&&d.speed<=1.15&&d.trainFraction>=.5&&d.trainFraction<=.85;}
function save(value:Persisted){try{localStorage.setItem(STORAGE,JSON.stringify(value));}catch{/* Storage can be disabled. */}}

export default function ScienceLab(){
 const [draft,setDraft]=useState<Draft>(initial),[applied,setApplied]=useState<Draft|null>(null);
 const [world,setWorld]=useState<World|null>(null),[experiment,setExperiment]=useState<Experiment|null>(null);
 const [branches,setBranches]=useState<ScienceBranch[]>([]),[selectedId,setSelectedId]=useState<string|null>(null);
 const [history,setHistory]=useState<string[]>([]),[sample,setSample]=useState(0),[playing,setPlaying]=useState(false);
 const [busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState<string|null>(null),[notice,setNotice]=useState<string|null>(null);
 const active=experiment?.status==='queued'||experiment?.status==='running';
 const dirty=applied!==null&&JSON.stringify(draft)!==JSON.stringify(applied);
 const selected=branches.find(branch=>branch.id===selectedId)??null;
 const source=selected?.initial_state??(world?.state as ScienceBranch['initial_state']|undefined);
 const observations=source?.observations??recorded.observations;
 const times=source?.times??recorded.times;
 const trainCount=selected?.evaluation.train_count??Math.floor(observations.length*(source?.config.train_fraction??.7));
 const series=useMemo(()=>branches.filter(branch=>branch.trace.length).map(branch=>({id:branch.id,label:hypothesisName(branch.evaluation.hypothesis),predicted_positions:branch.trace.map(frame=>frame.predicted_position)})),[branches]);
 const index=Math.max(0,Math.min(sample,Math.max(0,observations.length-1)));
 const frame=selected?.trace[index];
 const stale=!!experiment?.stale;

 useEffect(()=>{let live=true;(async()=>{try{
  const raw=localStorage.getItem(STORAGE);if(!raw)return;
  const saved=JSON.parse(raw) as Persisted;
  if(typeof saved.worldId!=='string'||!saved.draft||!Array.isArray(saved.history))return;
  const loaded=await api.world(saved.worldId);
  if(!live)return;
  setWorld(loaded);setDraft(saved.draft);setApplied(saved.draft);setHistory(saved.history);
  if(saved.history[0]){
   try{
    const result=await api.experiment(saved.history[0]);
    const fits=await api.branches(result.id) as unknown as ScienceBranch[];
    if(live){setExperiment(result);setBranches(fits);setSelectedId(result.selected_branch_id??fits[0]?.id??null);}
   }catch(e){
    if(!(e instanceof APIError&&e.status===404))throw e;
    if(live){setHistory([]);save({worldId:saved.worldId,draft:saved.draft,history:[]});setNotice('Saved experiment records expired on this host. Run a new comparison.');}
   }
  }
 }catch(e){if(live){
  if(e instanceof APIError&&e.status===404){try{localStorage.removeItem(STORAGE);}catch{/* Storage can be disabled. */}setNotice('The saved observation world expired on this host. Create a new world to continue.');}
  else setError(errorMessage(e));
 }}finally{if(live)setLoading(false);}})();return()=>{live=false;};},[]);
 useEffect(()=>{if(!active||!experiment)return;let live=true,timer:ReturnType<typeof setTimeout>;
  async function poll(){try{
   const result=await api.experiment(experiment!.id);
   if(!live)return;
   if(result.status==='completed'||result.status==='failed'||result.status==='cancelled'){
    const fits=await api.branches(result.id) as unknown as ScienceBranch[];
    if(live){setBranches(fits);setSelectedId(result.selected_branch_id??fits[0]?.id??null);setSample(0);setExperiment(result);}
   }else setExperiment(result);
  }catch(e){if(live)setError(errorMessage(e));}finally{if(live)timer=setTimeout(poll,700);}}
  timer=setTimeout(poll,700);return()=>{live=false;clearTimeout(timer);};
 },[experiment?.id,active]);
 useEffect(()=>{if(!playing||!selected?.trace.length)return;const timer=window.setInterval(()=>setSample(i=>i>=selected.trace.length-1?0:i+1),100);return()=>clearInterval(timer);},[playing,selected?.id,selected?.trace.length]);

 async function act(work:()=>Promise<void>){setBusy(true);setError(null);setNotice(null);try{await work();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}
 async function apply(){
  if(!valid(draft)||active)return;
  await act(async()=>{
   if(!world)await api.health();
   const value=world?await api.environment(world.id,config(draft)):await api.create('scipy',config(draft));
   setWorld(value);setApplied({...draft});setPlaying(false);setSample(0);
   if(world&&experiment){setExperiment({...experiment,stale:true});setNotice('The observations changed. Previous fits are preserved in history and are stale for this world version.');}
   else{setExperiment(null);setBranches([]);setSelectedId(null);setHistory([]);setNotice('Observation world created. Run the two competing models when ready.');}
   save({worldId:value.id,draft:{...draft},history:world?history:[]});
  });
 }
 async function run(){
  if(!world||dirty||active)return;
  await act(async()=>{
   const result=await api.submit(world.id,`science-${crypto.randomUUID()}`,{candidates:2,planner_iterations:100,max_simulation_seconds:8});
   const next=[result.id,...history.filter(id=>id!==result.id)].slice(0,24);
   setExperiment(result);setBranches([]);setSelectedId(null);setSample(0);setPlaying(false);setHistory(next);
   save({worldId:world.id,draft:applied??draft,history:next});
  });
 }
 async function openRecord(id:string){if(active)return;await act(async()=>{const [result,fits]=await Promise.all([api.experiment(id),api.branches(id)]);setExperiment(result);setBranches(fits as unknown as ScienceBranch[]);setSelectedId(result.selected_branch_id??fits[0]?.id??null);setSample(0);setPlaying(false);});}
 async function reset(){if(!world||active)return;await act(async()=>{const value=await api.reset(world.id);setWorld(value);setPlaying(false);setExperiment(previous=>previous?{...previous,stale:true}:null);setNotice('World reset to its initial observation state. Prior fits remain in history.');});}
 async function commit(){if(!world||!experiment||!selected||stale||!selected.evaluation.success)return;await act(async()=>{const value=await api.commit(world.id,experiment.id,selected.id);setWorld(value);setExperiment({...experiment,stale:true});setNotice('The selected fitted model was committed to this world version. The prior comparison is now historical.');});}
 const selectedHypothesis=selected?.evaluation.hypothesis;
 return <section className="discovery-lab" aria-labelledby="discovery-title">
  <header className="discovery-heading"><div><p className="discovery-kicker">ISABELLA LABS / SCIENTIFIC DISCOVERY</p><h1 id="discovery-title">The Invisible Planet<span>.</span></h1><p>Can an unseen gravitational influence explain an observed orbit? Fit two simplified physical models, reserve observations for a blind prediction check, and follow the numerical evidence.</p></div><div className="discovery-status" role="status"><span className={world?'online':'offline'}/>{loading?'Recovering saved world…':world?`World ${short(world.id)} · revision ${world.revision}`:'No world created'}</div></header>
  {error&&<div className="discovery-error" role="alert"><strong>Something interrupted the experiment.</strong><span>{error}</span><button onClick={()=>setError(null)}>Dismiss</button></div>}
  {notice&&<p className="discovery-notice" role="status">{notice}</p>}
  <div className="discovery-stage">
   <div className="discovery-chart"><div className="discovery-chart-head"><div><span>COMPUTED ORBIT / XY PLANE</span><strong>{world?experiment?stale?'Historical comparison':active?'Fitting models…':'Measured comparison':'Observation world ready':'Recorded reference preview'}</strong></div><span>{world?'SCIPY NUMERICAL MODEL':'REFERENCE RESULT'}</span></div>
    <SciencePlot observations={observations} series={series.length?series:!world?recorded.hypotheses.map(item=>({id:item.id,label:hypothesisName(item.id),predicted_positions:item.predicted_positions})):[]} selectedId={selected?.id??recorded.hypotheses[1].id} sampleIndex={index} trainCount={trainCount} perturbingPosition={source?.config.perturbing_position}/>
    <div className="discovery-chart-foot"><span><i/>Observed positions</span><span><i/>Predicted trajectory</span><span>{trainCount} training · {Math.max(0,observations.length-trainCount)} held out</span></div>
    {!world&&<p className="discovery-reference">This plot is a recorded SciPy example. Create a world to generate new observations; results will replace it after you run the models.</p>}
    {stale&&<p className="discovery-stale" data-testid="science-stale-warning" role="status">Historical result: the world conditions have changed. Run a new comparison for the current observations.</p>}
   </div>
   <aside className="discovery-controls" aria-label="Scientific experiment controls">
    <div className="discovery-controls-heading"><span>01 / DESIGN THE WORLD</span><h2>Change a condition.</h2><p>The generator integrates a 2D orbit with seeded measurement noise. The hidden source strength is withheld from the fitted models and public observation state.</p></div>
    <fieldset disabled={active||busy||loading}><legend>Observation settings</legend>
     <label>Observation scenario<select value={draft.scenario} onChange={event=>setDraft({...draft,scenario:event.target.value as Scenario})}><option value="signal">Unexplained motion</option><option value="control">Control observation</option></select></label>
     <div className="discovery-control-pair"><label>Noise standard deviation<input type="number" min="0.00001" max="0.05" step="0.001" value={draft.noise} onChange={event=>setDraft({...draft,noise:event.target.valueAsNumber})}/></label><label>Samples<input type="number" min="30" max="200" step="1" value={draft.samples} onChange={event=>setDraft({...draft,samples:event.target.valueAsNumber})}/></label></div>
     <div className="discovery-control-pair"><label>Initial speed<input type="number" min="0.85" max="1.15" step="0.01" value={draft.speed} onChange={event=>setDraft({...draft,speed:event.target.valueAsNumber})}/></label><label>Observation horizon<input type="number" min="2" max="8" step="0.5" value={draft.horizon} onChange={event=>setDraft({...draft,horizon:event.target.valueAsNumber})}/></label></div>
     <div className="discovery-control-pair"><label>Training fraction<input type="number" min="0.5" max="0.85" step="0.05" value={draft.trainFraction} onChange={event=>setDraft({...draft,trainFraction:event.target.valueAsNumber})}/></label><label>Reproducibility seed<input type="number" min="0" max="4294967295" step="1" value={draft.seed} disabled={!!world} onChange={event=>setDraft({...draft,seed:event.target.valueAsNumber})}/></label></div>
    </fieldset>
    {!valid(draft)&&<p className="discovery-validation" role="status">Enter values within the displayed input bounds to create a valid world.</p>}
    <div className="discovery-commands"><button className="discovery-primary" disabled={!valid(draft)||busy||active||loading||!!world&&!dirty} onClick={apply}>{busy?'Working…':!world?'Create observation world':'Apply changed conditions'} <span aria-hidden="true">↗</span></button><button disabled={!world||dirty||busy||active} onClick={run}>Run model comparison</button>{active&&<button onClick={()=>act(async()=>{if(experiment)await api.cancel(experiment.id);})}>Cancel numerical fit</button>}{world&&<button disabled={busy||active} onClick={reset}>Reset world</button>}</div>
    {dirty&&world&&<p className="discovery-prompt">Apply the changed conditions before running the next comparison.</p>}
    <div className="discovery-process"><span>02 / TEST HYPOTHESES</span><p>{active?`Backend status: ${experiment?.status}. Each model is fitted in its own branch.`:experiment?`Last job: ${experiment.status}. ${branches.length} branch${branches.length===1?'':'es'} recorded.`:'The backend will fit both hypotheses with SciPy and rank them using held-out prediction error and a complexity penalty.'}</p></div>
   </aside>
  </div>
  <div className="discovery-evidence" id="discovery-evidence"><div className="discovery-evidence-title"><span>03 / INSPECT THE EVIDENCE</span><h2>What survived the prediction?</h2><p>{experiment?.result?.conclusion?String(experiment.result.conclusion):'Run both hypotheses to compare actual numerical predictions. Failed fits remain visible.'}</p></div>
   {branches.length?<><div className="discovery-model-list" role="group" aria-label="Fitted hypotheses">{branches.map(branch=><button key={branch.id} aria-pressed={selectedId===branch.id} onClick={()=>{setSelectedId(branch.id);setSample(0);setPlaying(false);}}><span>{hypothesisName(branch.evaluation.hypothesis)}</span><strong>{branch.evaluation.success?format(branch.evaluation.heldout_rmse):branch.evaluation.status}</strong><small>{branch.evaluation.success?'Held-out RMSE':'Numerical failure'}{experiment?.selected_branch_id===branch.id?' · selected':''}</small></button>)}</div>
    {selected&&<div className="discovery-inspection"><div className="discovery-readouts"><dl><div><dt>Training RMSE</dt><dd>{format(selected.evaluation.train_rmse)}</dd></div><div><dt>Held-out RMSE</dt><dd>{format(selected.evaluation.heldout_rmse)}</dd></div><div><dt>Training BIC</dt><dd>{format(selected.evaluation.training_bic,2)}</dd></div><div><dt>Integrations</dt><dd>{selected.evaluation.integration_calls??'—'}</dd></div></dl><p>{selected.action.definition} The extra parameter is selected only if both the held-out prediction and complexity criterion support it.</p></div>
     <div className="discovery-replay"><h3>Replay recorded predictions</h3><p>Every point comes from the fitted SciPy trajectory. Playback moves through stored numerical samples; it does not run new physics.</p><div><button disabled={!selected.trace.length} onClick={()=>setPlaying(value=>!value)}>{playing?'Pause replay':'Play replay'}</button><label htmlFor="science-replay">Sample {index+1} / {selected.trace.length}<input id="science-replay" aria-label="Replay numerical samples" type="range" min="0" max={Math.max(0,selected.trace.length-1)} value={index} onChange={event=>{setPlaying(false);setSample(Number(event.target.value));}}/></label></div><p role="status">{frame?`t = ${format(frame.time,3)} · ${frame.split} · observed (${frame.observed_position.map(v=>format(v,3)).join(', ')}) · predicted (${frame.predicted_position.map(v=>format(v,3)).join(', ')})`:'No trajectory recorded for this fit.'}</p><div className="discovery-replay-actions"><button disabled={busy} onClick={()=>act(async()=>{if(experiment)await api.download(experiment.id,selected.id);})}>Export branch JSON</button><button disabled={busy||stale||!selected.evaluation.success} onClick={commit}>Commit fitted model</button></div></div>
    </div>}
    <details className="discovery-technical"><summary>Fitted parameters & uncertainty</summary>{selected?.evaluation.parameters?<><dl>{Object.entries(selected.evaluation.parameters).map(([name,value])=><div key={name}><dt>{name.replaceAll('_',' ')}</dt><dd>{format(value,6)} ± {format(selected.evaluation.uncertainty?.standard_errors[name],6)}</dd></div>)}</dl><p>{selected.evaluation.uncertainty?.method} {selected.evaluation.uncertainty?.caveat}</p></>:<p>The selected hypothesis did not produce fitted parameters.</p>}</details>
   </>:<p className="discovery-empty">{active?'Computing the two independent fits…':'No fitted models yet. Create a world and run model comparison.'}</p>}
   {world&&<details className="discovery-history"><summary>Experiment history ({history.length})</summary><ol>{history.map((id,i)=><li key={id}><button aria-pressed={experiment?.id===id} disabled={busy||active} onClick={()=>openRecord(id)}>Experiment {history.length-i} · {short(id)}{experiment?.id===id&&stale?' · stale':''}</button></li>)}</ol><p>History is indexed in this browser. The runtime stores full observations, branch states, evaluations, and replay traces in SQLite while the host retains them.</p></details>}
   <p className="discovery-scope">Scope: restricted nondimensional 2D Newtonian model, stationary external perturber, synthetic noisy observations. This compares models; it does not discover a new physical law or validate a real astronomical system.</p>
  </div>
 </section>;
}
