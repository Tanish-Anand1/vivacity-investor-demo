import {lazy,Suspense,useState} from 'react';
import type {FactoryVisualState} from './FactoryView';
import recordedRobotics from './generated/labOpening.json';
import './isabella.css';

const FactoryView=lazy(()=>import('./FactoryView'));
type RobotTrial={condition:string;status:string;failure_kind:string|null;gripper_force_scale:number;metrics:{cartons_sorted:number;simulation_steps:number};frames:FactoryVisualState[]};
const robotics=recordedRobotics.trials as unknown as RobotTrial[];

export default function IsabellaHome({enterLab,openScience,openRobotics,openWorlds}:{enterLab:()=>void;openScience:()=>void;openRobotics:()=>void;openWorlds:()=>void}){
 const [condition,setCondition]=useState(1);
 const [sceneReady,setSceneReady]=useState(false);
 const [sceneError,setSceneError]=useState<string|null>(null);
 const trial=robotics[condition];
 const delivered=trial.status==='completed'&&trial.metrics.cartons_sorted>0;
 return <div className="isabella-home" id="top">
  <a className="skip-link" href="#isabella-main">Skip to content</a>
  <header className="isabella-header">
   <a href="#top" className="isabella-wordmark" aria-label="Isabella Labs by Vivacity, home"><strong>ISABELLA<span>LABS</span></strong><small>BY VIVACITY</small></a>
   <nav aria-label="Isabella navigation"><a href="#experiment">The experiment</a><button onClick={openWorlds}>Worlds</button><button className="isabella-nav-enter" onClick={enterLab}>Enter lab <span aria-hidden="true">↗</span></button></nav>
  </header>
  <main id="isabella-main" className="isabella-main" tabIndex={-1}>
   <section className="isabella-hero" aria-labelledby="isabella-headline">
    <div className="isabella-hero-copy">
     <p className="isabella-eyebrow">ISABELLA LABS / BY VIVACITY</p>
     <h1 id="isabella-headline">Let robots<br/>fail here<br/><span>first.</span></h1>
     <p className="isabella-lede">Give a machine a world. Change the conditions. See what actually happens before it moves in yours.</p>
     <div className="isabella-hero-actions"><button className="isabella-primary" onClick={enterLab}>ENTER THE LAB <span aria-hidden="true">↗</span></button><button className="isabella-secondary" onClick={openRobotics}>OPEN ROBOTICS EXPERIMENT <span aria-hidden="true">↗</span></button></div>
    </div>
    <div className="isabella-hero-scene" aria-label="Recorded robotic handling scene">
     <Suspense fallback={<div className="isabella-scene-fallback" role="status">Loading recorded workcell…</div>}><FactoryView frame={trial.frames.at(-1)??trial.frames[0]} mode="fidelity" status="recorded" onVisualReady={()=>setSceneReady(true)} onVisualError={setSceneError}/></Suspense>
     <img className={`isabella-scene-poster${sceneReady?' isabella-scene-poster-ready':''}`} src="/vivacity/isabella-scene-poster.webp" alt="" aria-hidden="true" fetchPriority="high"/>
     <div className="isabella-scene-caption"><span>RECORDED SIMULATION</span><span>ROBOTIC HANDLING / WORLD 01</span></div>
    </div>
   </section>
   <section className="isabella-experiment" id="experiment" aria-labelledby="experiment-heading">
    <div className="isabella-experiment-intro"><p className="isabella-eyebrow">A WORLD, UNDER TEST</p><h2 id="experiment-heading">One change.<br/>Another outcome.</h2><p>In this saved physical experiment, the robot meets the same carton under two grip settings. Change the condition to inspect what each recorded run actually did.</p><button className="isabella-text-link" onClick={openRobotics}>Open the experiment lab <span aria-hidden="true">↗</span></button></div>
    <div className="isabella-experiment-evidence"><div className="isabella-condition-switch" role="group" aria-label="Recorded robotic condition">{robotics.map((item,i)=><button key={item.condition} aria-pressed={condition===i} onClick={()=>setCondition(i)}>{i===0?'Weak grip':'Full grip'} <span>{i===0?'01':'02'}</span></button>)}</div><div className="isabella-evidence-number" role="status"><strong>{trial.metrics.cartons_sorted}<span> / 1</span></strong><p>{delivered?'carton delivered':'carton not delivered'}</p></div><p className="isabella-evidence-detail">{delivered?'The recorded run reached the destination.':`The recorded run ended with ${trial.failure_kind?.replaceAll('_',' ')??'a measured failure'}.`} <span>{trial.metrics.simulation_steps.toLocaleString()} physics steps.</span></p><p className="isabella-evidence-provenance">Saved simulated result. A new test starts only after you choose to run one in the lab.</p>{sceneError&&<p role="alert" className="isabella-preview-error">The 3D preview could not load. Recorded measurements remain available.</p>}</div>
   </section>
   <section className="isabella-worlds" aria-labelledby="worlds-heading"><div className="isabella-worlds-image"><img src="/vivacity/isabella-scene-poster.webp" alt="Recorded view of a robot in an industrial sorting cell"/></div><div className="isabella-worlds-copy"><p className="isabella-eyebrow">POSSIBLE WORLDS</p><h2 id="worlds-heading">The world changes.<br/>The question changes.</h2><p>Move from one workcell to another, set the task and physical conditions, then compare the outcomes that follow.</p><button className="isabella-text-link" onClick={openWorlds}>Explore robotic worlds <span aria-hidden="true">↗</span></button></div></section>
   <section className="isabella-invitation" aria-label="Enter Isabella Labs"><h2>Enter a world.<br/><span>See what holds.</span></h2><div><button onClick={enterLab}>Enter Isabella Labs <span aria-hidden="true">↗</span></button><button onClick={openScience}>Explore scientific experiments <span aria-hidden="true">↗</span></button></div></section>
  </main>
  <footer className="isabella-footer"><span>ISABELLA LABS <span>BY VIVACITY</span></span><a href="https://www.tryvivacity.com/" target="_blank" rel="noreferrer">Vivacity ↗</a></footer>
 </div>;
}
