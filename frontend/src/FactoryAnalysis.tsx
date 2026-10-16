import {useEffect,useMemo,useState} from 'react';
import {factoryApi,type FactoryFrame,type FactoryRun} from './factoryApi';
import {nearestSample,sampleValue,samplesCSV,units,type Quantity} from './factoryAnalysisData';
import type {Vec3} from './domain';
import {errorMessage} from './api';
import FactoryDiscovery from './FactoryDiscovery';

const groups:{title:string;options:[Quantity,string][]}[]=[
 {title:'01 / Carton position',options:[['z','Height'],['x','X'],['y','Y']]},
 {title:'02 / Carton motion',options:[['speed','Speed'],['acceleration','Acceleration magnitude']]},
 {title:'03 / Joint torque',options:[['torque','Selected robot joint']]},
 {title:'04 / Gripper contact',options:[['force','Sum of finger normal forces']]},
 {title:'05 / Actuator mechanics',options:[['power','Mechanical power'],['work','Net mechanical work'],['positive_work','Positive actuator work'],['kinetic','Carton kinetic energy'],['potential','Carton potential energy']]},
 {title:'06 / Transport',options:[['conveyor','Infeed surface speed'],['completed','Delivered cartons'],['throughput','Cumulative throughput']]},
];
function save(data:string,type:string,name:string){const url=URL.createObjectURL(new Blob([data],{type})),link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

function Plot({frames,quantity,object,joint,events,range,cursor,onSelect}:{frames:FactoryFrame[];quantity:Quantity;object:string;joint:number;events:FactoryRun['events'];range:[number,number];cursor:number;onSelect:(time:number)=>void}){
 const points=useMemo(()=>frames.filter(f=>f.time>=range[0]&&f.time<=range[1]).map(f=>({time:f.time,value:sampleValue(f,quantity,object,joint,events)})),[frames,quantity,object,joint,events,range]);
 const values=points.flatMap(p=>p.value===null?[]:[p.value]);let low=values.length?Math.min(...values):0,high=values.length?Math.max(...values):1;const margin=Math.max((high-low)*.12,.0001);low-=margin;high+=margin;
 const x=(t:number)=>48+(t-range[0])/Math.max(.05,range[1]-range[0])*472,y=(v:number)=>154-(v-low)/(high-low)*120;
 const path=points.map((p,i)=>p.value===null?'':`${i===0||points[i-1].value===null?'M':'L'}${x(p.time).toFixed(2)},${y(p.value).toFixed(2)}`).join(' ');
 const selected=frames[nearestSample(frames,cursor)],value=selected?sampleValue(selected,quantity,object,joint,events):null;
 return <><div className="factory-plot-value"><strong>{value===null?'Unavailable':value.toFixed(3)}</strong><span>{units[quantity]} · {selected?.time.toFixed(3)??'—'} s</span></div>
  <svg viewBox="0 0 540 190" role="img" aria-label={`${quantity} in ${units[quantity]}, simulation time ${range[0].toFixed(2)} to ${range[1].toFixed(2)} seconds. Use the sample slider below to inspect.`} onPointerDown={e=>{const bounds=e.currentTarget.getBoundingClientRect();onSelect(range[0]+Math.max(0,Math.min(1,((e.clientX-bounds.left)/bounds.width*540-48)/472))*(range[1]-range[0]));}}>
   {[0,.5,1].map(f=>{const v=low+(high-low)*f;return <g key={f}><line x1={48} x2={520} y1={y(v)} y2={y(v)} stroke="#465149" strokeWidth={.6}/><text x={41} y={y(v)+4} textAnchor="end">{v.toFixed(Math.abs(v)>10?1:3)}</text></g>;})}
   <path d={path} fill="none" stroke="#ddba79" strokeWidth={1.6}/>
   {cursor>=range[0]&&cursor<=range[1]&&<line x1={x(cursor)} x2={x(cursor)} y1={29} y2={155} stroke="#a8d2c6" strokeDasharray="3 3"/>}
   <text x={48} y={179}>{range[0].toFixed(2)} s</text><text x={520} y={179} textAnchor="end">{range[1].toFixed(2)} s</text>
  </svg>
 </>;
}

export default function FactoryAnalysis({run,onInspect,onTrajectory}:{run:FactoryRun;onInspect:(frame:FactoryFrame|null)=>void;onTrajectory:(points:Vec3[])=>void}){
 const [frames,setFrames]=useState<FactoryFrame[]>([]),[error,setError]=useState<string|null>(null),[object,setObject]=useState('target'),[joint,setJoint]=useState(0),[index,setIndex]=useState<number|null>(null),[range,setRange]=useState<[number,number]|null>(null),[playing,setPlaying]=useState(false),[eventTime,setEventTime]=useState(''),[quantities,setQuantities]=useState<Quantity[]>(groups.map(g=>g.options[0][0]));
 useEffect(()=>{let active=true,timer:ReturnType<typeof setTimeout>;let after=-1;setFrames([]);setIndex(null);setRange(null);onInspect(null);
  async function poll(){try{const page=await factoryApi.samples(run.id,after);if(!active)return;if(page.frames.length){setFrames(old=>[...old,...page.frames]);after=page.next_index;}setError(null);if(['running','queued','paused'].includes(page.status)||after<page.total_samples-1)timer=setTimeout(poll,after<page.total_samples-1?30:600);}catch(e){if(active){setError(errorMessage(e));timer=setTimeout(poll,2000);}}}
  poll();return()=>{active=false;clearTimeout(timer);onInspect(null);};
 },[run.id]);
 useEffect(()=>{if(index!==null&&frames[index])onInspect(frames[index]);},[index,frames,onInspect]);
 useEffect(()=>{if(!playing||index===null)return;if(index>=frames.length-1){setPlaying(false);return;}const timer=setTimeout(()=>setIndex(i=>i===null?0:i+1),Math.max(16,(frames[index+1].time-frames[index].time)*1000));return()=>clearTimeout(timer);},[playing,index,frames]);
 useEffect(()=>{onTrajectory(frames.flatMap(f=>{const value=f.cartons.find(c=>c.id===object);return value?[value.position_m as Vec3]:[];}));return()=>onTrajectory([]);},[frames,object,onTrajectory]);
 const last=frames.at(-1)?.time??0,selected=index===null?frames.length-1:index,cursor=frames[selected]?.time??0,visibleRange=range??[0,Math.max(.05,last)] as [number,number];
 const select=(time:number)=>{setEventTime('');setPlaying(false);setIndex(nearestSample(frames,time));};
 function zoom(factor:number){const width=Math.min(Math.max(.1,(visibleRange[1]-visibleRange[0])*factor),Math.max(last,.1));const left=Math.max(0,Math.min(last-width,cursor-width/2));setRange([left,Math.min(last,left+width)]);}
 return <section className="factory-analysis" aria-label="Measured analysis"><header><div><span className="factory-eyebrow">Recorded instrument data</span><h2>Physics over time</h2><p>{frames.length.toLocaleString()} backend samples · {index===null?'Following latest':'Inspecting recorded state'} · {cursor.toFixed(3)} s</p></div><div className="factory-analysis-select"><label>Carton<select value={object} onChange={e=>setObject(e.target.value)}>{run.frame.cartons.map(c=><option key={c.id}>{c.id}</option>)}</select></label><label>Robot joint<select value={joint} onChange={e=>setJoint(Number(e.target.value))}>{Array.from({length:7},(_,i)=><option key={i} value={i}>Joint {i+1}</option>)}</select></label></div></header>
  {error&&<p role="alert">{error}</p>}
  {!frames.length?<p>Waiting for recorded physics samples…</p>:<>
   <div className="factory-timeline"><label>Recorded sample<input aria-label="Recorded sample" type="range" min={0} max={frames.length-1} step={1} value={Math.max(0,selected)} onChange={e=>{setEventTime('');setPlaying(false);setIndex(Number(e.target.value));}}/></label><output data-testid="factory-sample-time">{cursor.toFixed(3)} s · sample {selected+1}</output><div className="factory-analysis-tools"><button onClick={()=>{setEventTime('');if(playing)setPlaying(false);else{setIndex(selected>=frames.length-1?0:Math.max(0,selected));setPlaying(true);}}}>{playing?'Pause inspection':'Advance through samples'}</button><button onClick={()=>{setEventTime('');setIndex(null);setPlaying(false);onInspect(null);}}>Return to latest</button><label>Recorded event<select value={eventTime} onChange={e=>{if(e.target.value){select(Number(e.target.value));setEventTime(e.target.value);}}}><option value="">Choose an event</option>{run.events.map((e,i)=><option key={i} value={e.time_s}>{e.time_s.toFixed(3)} s · {e.carton_id??''} {e.kind.replaceAll('_',' ')}</option>)}</select></label></div></div>
   <div className="factory-analysis-tools"><button onClick={()=>zoom(.5)}>Zoom in</button><button onClick={()=>zoom(2)}>Zoom out</button><button onClick={()=>setRange(null)}>Full time range</button><label>From (s)<input type="number" step="0.05" min={0} max={visibleRange[1]-.05} value={Number(visibleRange[0].toFixed(3))} onChange={e=>{const v=e.target.valueAsNumber;if(Number.isFinite(v))setRange([Math.max(0,Math.min(v,visibleRange[1]-.05)),visibleRange[1]]);}}/></label><label>To (s)<input type="number" step="0.05" min={visibleRange[0]+.05} max={last} value={Number(visibleRange[1].toFixed(3))} onChange={e=>{const v=e.target.valueAsNumber;if(Number.isFinite(v))setRange([visibleRange[0],Math.max(visibleRange[0]+.05,Math.min(last,v))]);}}/></label><button onClick={()=>save(samplesCSV(frames,object,joint,run.events),'text/csv',`vivacity-${run.id}-${object}-joint${joint+1}.csv`)}>Export CSV</button><button onClick={()=>save(JSON.stringify({schema_version:'vivacity.factory-samples/1.0',run_id:run.id,units,frames,events:run.events}),'application/json',`vivacity-${run.id}-samples.json`)}>Export sampled JSON</button></div>
   <div className="factory-plots">{groups.map((g,i)=><section key={g.title}><div className="factory-plot-heading"><h3>{g.title}</h3><select aria-label={g.title.slice(5)+' quantity'} value={quantities[i]} onChange={e=>setQuantities(q=>q.map((v,j)=>j===i?e.target.value as Quantity:v))}>{g.options.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></div><Plot frames={frames} quantity={quantities[i]} object={object} joint={joint} events={run.events} range={visibleRange} cursor={cursor} onSelect={select}/></section>)}</div>
   <FactoryDiscovery run={run} frames={frames}/>
   <p className="factory-stage-note">Charts use saved backend samples, typically 0.05 s apart. Missing quantities stay unavailable. Forces and accelerations refer to the preceding physics solve; pose time is shown on the axis. Cumulative throughput is delivered cartons divided by elapsed simulation minutes. Work is integrated every 0.002 s. Selecting a sample changes inspection only. Older records select the nearest sample to an event; new runs also retain event-time samples.</p>
  </>}
 </section>;
}
