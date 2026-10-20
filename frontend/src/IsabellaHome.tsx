import {lazy, Suspense, useEffect, useState} from 'react';
import type {FactoryVisualState} from './FactoryView';
import evidence from './generated/labOpening.json';
import './isabella.css';

const FactoryView=lazy(()=>import('./FactoryView'));
type RecordedTrial={condition:string;status:string;failure_kind:string|null;detail:string|null;gripper_force_scale:number;metrics:{cartons_sorted:number;simulation_steps:number;simulation_time_s?:number};frames:FactoryVisualState[]};
const trials=evidence.trials as unknown as RecordedTrial[];
const target=(frame:FactoryVisualState)=>frame.body_transforms.find(body=>body.name==='target')?.position;
const positions=trials.flatMap(trial=>trial.frames.flatMap(frame=>{const point=target(frame);return point?[[point[0],point[1]]]:[];}));
const minY=Math.min(...positions.map(point=>point[1])),maxY=Math.max(...positions.map(point=>point[1]));
const minX=Math.min(...positions.map(point=>point[0])),maxX=Math.max(...positions.map(point=>point[0]));
const plot=(point:number[])=>[36+(point[1]-minY)/Math.max(.1,maxY-minY)*568,172-(point[0]-minX)/Math.max(.1,maxX-minX)*96];

function RecordedPath({trial,index}:{trial:RecordedTrial;index:number}){
 const route=trial.frames.flatMap(frame=>{const point=target(frame);return point?[point]:[]});
 const current=target(trial.frames[index]);
 const marker=current?plot(current):null;
 const line=route.map((point,i)=>`${i?'L':'M'}${plot(point).map(value=>value.toFixed(1)).join(' ')}`).join(' ');
 return <figure className="isabella-path"><svg viewBox="0 0 640 220" role="img" aria-label={`Recorded carton centre path. Current X ${current?.[0].toFixed(3)??'unknown'} metres, Y ${current?.[1].toFixed(3)??'unknown'} metres.`}>
  <line x1="36" y1="172" x2="604" y2="172" stroke="#829289" strokeWidth="1"/>
  <path d={line} fill="none" stroke="#c9d8c5" strokeWidth="3"/>
  {marker&&<circle cx={marker[0]} cy={marker[1]} r="8" fill="#edf3e8"/>}
  <text x="36" y="200">START</text><text x="604" y="200" textAnchor="end">+Y / CONVEYOR DIRECTION</text>
 </svg><figcaption>Carton centre · recorded plan view {current&&<span>X {current[0].toFixed(3)} m · Y {current[1].toFixed(3)} m</span>}</figcaption></figure>;
}

function useRecordedFrame(trial:RecordedTrial){
 const [index,setIndex]=useState(0),[playing,setPlaying]=useState(false);
 useEffect(()=>{setIndex(0);setPlaying(false);},[trial]);
 useEffect(()=>{
  if(!playing)return;
  const timer=window.setInterval(()=>{if(document.visibilityState==='visible')setIndex(current=>(current+1)%trial.frames.length);},120);
  return()=>window.clearInterval(timer);
 },[playing,trial]);
 return {frame:trial.frames[index],index,playing,setIndex,setPlaying};
}

export default function IsabellaHome({enterLab,watchExperiment,openWorlds}:{enterLab:()=>void;watchExperiment:()=>void;openWorlds:()=>void}){
 const [condition,setCondition]=useState(1);
 const [sceneReady,setSceneReady]=useState(false);
 const [sceneError,setSceneError]=useState<string|null>(null);
 const trial=trials[condition];
 const {frame,index,playing,setIndex,setPlaying}=useRecordedFrame(trial);
 return <div className="isabella-home" id="top">
  <a className="skip-link" href="#isabella-main">Skip to content</a>
  <header className="isabella-header">
   <a href="#top" className="isabella-wordmark" aria-label="Isabella Labs by Vivacity, home"><strong>ISABELLA<span>LABS</span></strong><small>BY VIVACITY</small></a>
   <nav aria-label="Isabella navigation"><a href="#experiment">The experiment</a><button onClick={openWorlds}>Worlds</button><button onClick={enterLab}>Enter lab <span aria-hidden="true">↗</span></button></nav>
  </header>
  <main id="isabella-main" className="isabella-main" tabIndex={-1}>
   <section className="isabella-hero" aria-labelledby="isabella-headline">
    <div className="isabella-hero-text">
     <h1 id="isabella-headline">Explore<br/><em>possible</em><br/>worlds<span className="isabella-period">.</span></h1>
     <p>Build environments, test outcomes, and discover better solutions.</p>
     <div className="isabella-hero-actions"><button className="isabella-primary" onClick={enterLab}>ENTER THE LAB <span aria-hidden="true">↗</span></button><button className="isabella-secondary" onClick={watchExperiment}>WATCH AN EXPERIMENT <span aria-hidden="true">↗</span></button></div>
     {sceneError&&<p className="isabella-preview-error" role="alert">The 3D preview could not load. Recorded measurements below remain available.</p>}
    </div>
    <div className={`isabella-hero-scene${sceneReady?' isabella-hero-scene-ready':''}`} aria-label="Recorded MuJoCo robotic handling trial; use the experiment controls below to inspect it">
     <Suspense fallback={<div className="isabella-scene-fallback" role="status"><span className="sr-only">Preparing the recorded physical world…</span></div>}><FactoryView frame={frame} mode="performance" status="recorded" onVisualReady={()=>setSceneReady(true)} onVisualError={setSceneError}/></Suspense>
     <img className={`isabella-scene-poster${sceneReady?' isabella-scene-poster-ready':''}`} src="/vivacity/isabella-scene-poster.webp" alt="" aria-hidden="true"/>
    </div>
   </section>
   <section id="experiment" className="isabella-experiment" aria-labelledby="experiment-heading">
    <div className="isabella-experiment-heading"><h2 id="experiment-heading">One world.<br/><em>Two conditions.</em></h2><p>The same saved initial state, two gripper forces. These frames were recorded from MuJoCo physics; the lab runs new trials on the backend.</p></div>
    <div className="isabella-experiment-controls">
     <div className="isabella-condition-group" role="group" aria-label="Recorded condition">{trials.map((item,i)=><button key={item.condition} aria-pressed={condition===i} onClick={()=>setCondition(i)}>{i===0?'Weak grip':'Full grip'} <span>{item.gripper_force_scale.toFixed(3)} force scale</span></button>)}</div>
     <RecordedPath trial={trial} index={index}/>
     <div className="isabella-recorded-result" role="status"><strong>{trial.metrics.cartons_sorted} / 1 delivered</strong><span>{trial.status==='completed'?'Completed in simulation':`Measured failure: ${trial.failure_kind?.replaceAll('_',' ')??trial.status}`}</span><span>{trial.metrics.simulation_steps.toLocaleString()} physics steps</span></div>
     <div className="isabella-timeline"><button aria-label={playing?'Pause recorded trial':'Play recorded trial'} onClick={()=>setPlaying(!playing)}>{playing?'Pause':'Play'}</button><label htmlFor="isabella-sample">Recorded sample <span>{index+1} / {trial.frames.length}</span></label><input id="isabella-sample" type="range" min="0" max={trial.frames.length-1} value={index} onChange={event=>{setPlaying(false);setIndex(Number(event.target.value));}}/></div>
    </div>
   </section>
   <section className="isabella-invitation" aria-labelledby="invitation-heading"><p>CREATE A WORLD · CHANGE A VARIABLE · DISCOVER WHAT HAPPENS</p><h2 id="invitation-heading">Change one thing.<br/><em>See what follows.</em></h2><div><button onClick={watchExperiment}>Run the robotic handling experiment <span aria-hidden="true">↗</span></button><button onClick={openWorlds}>Explore available worlds <span aria-hidden="true">↗</span></button></div></section>
  </main>
  <footer className="isabella-footer"><span>ISABELLA LABS <span>BY VIVACITY</span></span><a href="https://www.tryvivacity.com/" target="_blank" rel="noreferrer">Vivacity ↗</a></footer>
 </div>;
}
