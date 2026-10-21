import {lazy,Suspense,useEffect,useState} from 'react';
import type {FactoryVisualState} from './FactoryView';
import SciencePlot from './SciencePlot';
import recordedScience from './generated/isabellaSciencePreview.json';
import recordedRobotics from './generated/labOpening.json';
import './isabella.css';

const FactoryView=lazy(()=>import('./FactoryView'));
type Model={id:string;definition:string;train_rmse:number;heldout_rmse:number;training_bic:number;predicted_positions:number[][]};
type ScienceRecording={schema_version:string;status:string;seed:number;simulator_version:string;times:number[];observations:number[][];train_count:number;hypotheses:Model[]};
type RobotTrial={condition:string;status:string;failure_kind:string|null;gripper_force_scale:number;metrics:{cartons_sorted:number;simulation_steps:number};frames:FactoryVisualState[]};
const science=recordedScience as ScienceRecording;
const robotics=recordedRobotics.trials as unknown as RobotTrial[];
const fmt=(value:number)=>Number.isFinite(value)?value.toFixed(5):'Unavailable';

export default function IsabellaHome({enterLab,openScience,openRobotics,openWorlds}:{enterLab:()=>void;openScience:()=>void;openRobotics:()=>void;openWorlds:()=>void}){
 const [modelId,setModelId]=useState(science.hypotheses[1].id);
 const [sample,setSample]=useState(science.observations.length-1);
 const [playing,setPlaying]=useState(false);
 const [robotCondition,setRobotCondition]=useState(1);
 const [sceneReady,setSceneReady]=useState(false);
 const [sceneError,setSceneError]=useState<string|null>(null);
 const model=science.hypotheses.find(item=>item.id===modelId)??science.hypotheses[0];
 const robot=robotics[robotCondition];
 useEffect(()=>{
  if(!playing)return;
  const timer=window.setInterval(()=>{if(document.visibilityState==='visible')setSample(index=>index>=science.times.length-1?0:index+1);},110);
  return()=>window.clearInterval(timer);
 },[playing]);
 return <div className="isabella-home" id="top">
  <a className="skip-link" href="#isabella-main">Skip to content</a>
  <header className="isabella-header">
   <a href="#top" className="isabella-wordmark" aria-label="Isabella Labs by Vivacity, home"><strong>ISABELLA<span>LABS</span></strong><small>BY VIVACITY</small></a>
   <nav aria-label="Isabella navigation"><a href="#method">Method</a><a href="#fields">Experiments</a><button onClick={openWorlds}>Worlds</button><button className="isabella-nav-enter" onClick={enterLab}>Enter lab <span aria-hidden="true">↗</span></button></nav>
  </header>
  <main id="isabella-main" className="isabella-main" tabIndex={-1}>
   <section className="isabella-hero" aria-labelledby="isabella-headline">
    <div className="isabella-hero-copy">
     <p className="isabella-eyebrow">THE EXPERIMENTAL SCIENCE LAB / BY VIVACITY</p>
     <h1 id="isabella-headline">Make the<br/><em>unknown</em><br/>testable<span>.</span></h1>
     <p className="isabella-lede">Create a world. Change a variable. Discover what happens through simulation you can inspect, replay, and question.</p>
     <div className="isabella-hero-actions"><button className="isabella-primary" onClick={enterLab}>ENTER THE LAB <span aria-hidden="true">↗</span></button><button className="isabella-secondary" onClick={openScience}>RUN AN EXPERIMENT <span aria-hidden="true">↗</span></button></div>
    </div>
    <div className="isabella-hero-instrument" aria-label="Recorded orbital inference result">
     <div className="isabella-instrument-heading"><div><span>THE INVISIBLE PLANET</span><strong>What is moving this orbit?</strong></div><span className="isabella-recorded-tag">RECORDED SCIPY RESULT</span></div>
     <SciencePlot observations={science.observations} series={science.hypotheses.map(item=>({id:item.id,label:item.id==='central_only'?'Central gravity':'Additional influence',predicted_positions:item.predicted_positions}))} selectedId={modelId} sampleIndex={sample} trainCount={science.train_count}/>
     <div className="isabella-instrument-footer"><span><i className="isabella-legend-observed"/>OBSERVATIONS</span><span><i className="isabella-legend-predicted"/>MODEL PREDICTION</span><span>{science.train_count} FIT / {science.times.length-science.train_count} HELD OUT</span></div>
    </div>
   </section>
   <section className="isabella-method" id="method" aria-labelledby="method-heading">
    <div className="isabella-method-intro"><p className="isabella-eyebrow">AN EXPERIMENT YOU CAN INTERROGATE</p><h2 id="method-heading">A curve can be beautiful.<br/><em>Evidence is better.</em></h2><p>These are saved outputs of a bounded, two-dimensional gravity experiment. Two hypotheses were fitted to the same noisy observations; the final samples were kept out of training. Choose a model and inspect its prediction.</p><button className="isabella-text-link" onClick={openScience}>Run a fresh numerical experiment <span aria-hidden="true">↗</span></button></div>
    <div className="isabella-method-console">
     <div className="isabella-model-switch" role="group" aria-label="Recorded hypothesis">{science.hypotheses.map((item,i)=><button key={item.id} aria-pressed={modelId===item.id} onClick={()=>setModelId(item.id)}><span>0{i+1}</span>{i===0?'Central gravity':'Additional influence'}</button>)}</div>
     <div className="isabella-model-detail"><strong>{model.definition}</strong><dl><div><dt>Training RMSE</dt><dd>{fmt(model.train_rmse)}</dd></div><div><dt>Held-out RMSE</dt><dd>{fmt(model.heldout_rmse)}</dd></div><div><dt>Training BIC</dt><dd>{model.training_bic.toFixed(2)}</dd></div></dl><p>Normalized model units. Lower RMSE and BIC are better for this comparison.</p></div>
     <div className="isabella-timeline"><button aria-label={playing?'Pause recorded orbital samples':'Play recorded orbital samples'} onClick={()=>setPlaying(value=>!value)}>{playing?'Pause':'Play'}</button><label htmlFor="isabella-sample">Recorded sample <span>{sample+1} / {science.times.length}</span></label><input id="isabella-sample" type="range" min="0" max={science.times.length-1} value={sample} onChange={event=>{setPlaying(false);setSample(Number(event.target.value));}}/></div>
     <p className="isabella-method-source">Recorded SciPy {science.simulator_version} computation · seed {science.seed}. The live lab makes new observations and fits new models on the backend.</p>
    </div>
   </section>
   <section className="isabella-fields" id="fields" aria-labelledby="fields-heading">
    <div className="isabella-fields-heading"><p className="isabella-eyebrow">TWO WORKING LABS. ONE EXECUTION CONTRACT.</p><h2 id="fields-heading">The method moves<br/><em>between worlds.</em></h2></div>
    <article className="isabella-field isabella-field-science"><div><span className="isabella-field-index">01 / NUMERICAL INFERENCE</span><h3>The Invisible Planet</h3><p>Test whether an unseen fixed gravitational influence better explains an observed orbit. Fit competing models with SciPy, measure held-out predictions, and inspect uncertainty.</p><button onClick={openScience}>Open discovery lab <span aria-hidden="true">↗</span></button></div><div className="isabella-field-measure" aria-label="Recorded held-out comparison"><span>RECORDED HELD-OUT ERROR</span><div><small>Central</small><strong>{fmt(science.hypotheses[0].heldout_rmse)}</strong></div><div><small>Additional influence</small><strong>{fmt(science.hypotheses[1].heldout_rmse)}</strong></div><p>Normalized model units · measured on unseen samples</p></div></article>
    <article className="isabella-field isabella-field-robotics"><div className="isabella-robot-preview" aria-label="Recorded MuJoCo robotic handling result"><Suspense fallback={<div className="isabella-scene-fallback" role="status">Loading recorded robot geometry…</div>}><FactoryView frame={robot.frames.at(-1)??robot.frames[0]} mode="performance" status="recorded" onVisualReady={()=>setSceneReady(true)} onVisualError={setSceneError}/></Suspense><img className={`isabella-scene-poster${sceneReady?' isabella-scene-poster-ready':''}`} src="/vivacity/isabella-scene-poster.webp" alt="" aria-hidden="true"/></div><div><span className="isabella-field-index">02 / PHYSICAL SIMULATION</span><h3>A package loses its grip.</h3><p>Change the gripper force in the same MuJoCo workcell. Watch the robot execute independent trials, then compare measured deliveries and failure reasons.</p><div className="isabella-robot-conditions" role="group" aria-label="Recorded robotic condition">{robotics.map((item,i)=><button key={item.condition} aria-pressed={robotCondition===i} onClick={()=>{setRobotCondition(i);setSceneReady(false);}}>{i===0?'Weak grip':'Full grip'}</button>)}</div><p className="isabella-robot-result" role="status">{robot.metrics.cartons_sorted} / 1 delivered · {robot.status==='completed'?'completed in simulation':`measured ${robot.failure_kind?.replaceAll('_',' ')??'failure'}`} · {robot.metrics.simulation_steps.toLocaleString()} physics steps</p>{sceneError&&<p className="isabella-preview-error" role="alert">The 3D preview could not load. The recorded measurements remain available.</p>}<button onClick={openRobotics}>Open robotics lab <span aria-hidden="true">↗</span></button></div></article>
   </section>
   <section className="isabella-invitation" aria-labelledby="invitation-heading"><p className="isabella-eyebrow">ISABELLA LABS / BY VIVACITY</p><h2 id="invitation-heading">Ask a better question.<br/><em>Run the experiment.</em></h2><div><button onClick={enterLab}>Enter the laboratory <span aria-hidden="true">↗</span></button><button onClick={openWorlds}>Explore robotic worlds <span aria-hidden="true">↗</span></button></div></section>
  </main>
  <footer className="isabella-footer"><span>ISABELLA LABS <span>BY VIVACITY</span></span><a href="https://www.tryvivacity.com/" target="_blank" rel="noreferrer">Vivacity ↗</a></footer>
 </div>;
}
