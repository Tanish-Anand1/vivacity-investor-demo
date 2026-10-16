import {useEffect,useMemo,useRef,useState} from 'react';
import {factoryApi,type DiscoveryModel,type DiscoverySeries,type FactoryDiscoveryRecord,type FactoryFrame,type FactoryRun} from './factoryApi';
import {sampleValue,type Quantity} from './factoryAnalysisData';
import {errorMessage} from './api';
import {desmosNumber} from './desmosNumber';
import {parseDesmosSnapshot} from './desmosSnapshot';
import MathEquation from './MathEquation';

const choices:[Quantity,string][]=[['x','Carton X'],['y','Carton Y'],['z','Carton height'],['speed','Carton speed'],['torque','Joint 1 torque'],['force','Gripper contact force'],['power','Actuator power'],['work','Mechanical work']];
const key=import.meta.env.VITE_DESMOS_API_KEY as string|undefined;
type GraphExpression={id:string;type?:'expression'|'table'|'text';latex?:string;color?:string;columns?:{latex:string;values:string[];color?:string;points?:boolean;lines?:boolean}[];text?:string};
type Calculator={setExpression:(v:GraphExpression)=>void;setExpressions:(v:GraphExpression[])=>void;removeExpression:(v:{id:string})=>void;setMathBounds:(v:{left:number;right:number;bottom:number;top:number})=>void;updateSettings:(v:{xAxisLabel?:string;yAxisLabel?:string})=>void;getState:()=>unknown;setState:(state:unknown)=>void;observeEvent:(name:string,listener:(name:string,event:{isUserInitiated:boolean})=>void)=>void;unobserveEvent:(name:string)=>void;destroy:()=>void};
type DesmosGlobal={GraphingCalculator:(element:HTMLElement)=>Calculator;enabledFeatures?:{GraphingCalculator?:boolean}};
declare global{interface Window{Desmos?:DesmosGlobal}}

function download(data:string,name:string,type='application/json'){
 const url=URL.createObjectURL(new Blob([data],{type}));const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function fmt(value:number|null|undefined){return value===null||value===undefined?'—':Number.isFinite(value)?value.toPrecision(4):'—';}
function relationshipLatex(model:{equation_latex?:string;coefficients?:number[]}){
 if(model.equation_latex)return model.equation_latex;
 const c=model.coefficients;
 if(!c?.length)return String.raw`\text{Equation unavailable for this saved fit}`;
 let expression=String.raw`\tau=`+desmosNumber(c[0]);
 for(let i=1;i<c.length;i++)expression+=(c[i]<0?' - ':' + ')+desmosNumber(Math.abs(c[i]))+(i===1?String.raw`\alpha`:String.raw`\omega`);
 return expression;
}
function pointsFor(frames:FactoryFrame[],quantity:Quantity):[number,number][]{
 return frames.flatMap(frame=>{const value=sampleValue(frame,quantity,'target',0);return value===null?[]:[[frame.time,value] as [number,number]];});
}
function OutcomePlot({points,curve,comparison}:{points:[number,number][];curve:[number,number][];comparison?:[number,number][]}){
 const all=[...points,...curve,...(comparison??[])];if(!all.length)return <p>Waiting for measured samples.</p>;
 const xs=all.map(v=>v[0]),ys=all.map(v=>v[1]);const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
 const dx=Math.max(1e-9,maxX-minX),dy=Math.max(1e-9,maxY-minY),pad=dy*.1||.01;
 const sx=(x:number)=>40+(x-minX)/dx*480,sy=(y:number)=>150-(y-minY+pad)/(dy+2*pad)*130;
 const path=(data:[number,number][])=>data.map(([x,y],i)=>`${i?'L':'M'}${sx(x).toFixed(2)},${sy(y).toFixed(2)}`).join(' ');
 return <svg className="factory-discovery-plot" viewBox="0 0 540 185" role="img" aria-label="Original MuJoCo observations as points, selected fitted approximation as a line, and optional comparison curve"><line x1="40" x2="520" y1="150" y2="150" stroke="currentColor" opacity=".4"/><path d={path(curve)} fill="none" stroke="#78d1b3" strokeWidth="2"/>{comparison&&<path d={path(comparison)} fill="none" stroke="#d1a7e7" strokeWidth="1.7"/>}{points.filter((_,i)=>i%Math.max(1,Math.ceil(points.length/150))===0).map(([x,y],i)=><circle key={i} cx={sx(x)} cy={sy(y)} r="1.7" fill="#ddb879"/>)}<text x="40" y="173">{fmt(minX)} s</text><text x="520" y="173" textAnchor="end">{fmt(maxX)} s</text></svg>;
}
let loading:Promise<void>|null=null;
function loadDesmos(apiKey:string):Promise<void>{
 if(window.Desmos)return Promise.resolve();
 if(!loading)loading=new Promise<void>((resolve,reject)=>{const script=document.createElement('script');script.src=`https://www.desmos.com/api/v1.12/calculator.js?apiKey=${encodeURIComponent(apiKey)}`;script.async=true;script.onload=()=>window.Desmos?resolve():reject(new Error('Desmos calculator did not initialize.'));script.onerror=()=>reject(new Error('Desmos could not load.'));document.head.append(script);}).catch(error=>{loading=null;throw error;});
 return loading;
}

function DesmosGraph({runId,quantity,unit,points,model,comparison,edited,onEdited,onReady}:{runId:string;quantity:Quantity;unit:string;points:[number,number][];model:DiscoveryModel|null;comparison?:{id:string;points:[number,number][];model:DiscoveryModel|null};edited:boolean;onEdited:()=>void;onReady:(calc:Calculator|null)=>void}){
 const host=useRef<HTMLDivElement>(null),calc=useRef<Calculator|null>(null),[failure,setFailure]=useState<string|null>(null),[ready,setReady]=useState(false);
 useEffect(()=>{if(!key||!host.current)return;let active=true;loadDesmos(key).then(()=>{if(!active||!host.current||!window.Desmos)return;if(window.Desmos.enabledFeatures?.GraphingCalculator===false)throw new Error('This Desmos key does not enable Graphing Calculator.');const created=window.Desmos.GraphingCalculator(host.current);calc.current=created;setReady(true);onReady(created);created.observeEvent('change.vivacity',(_name,event)=>{if(event.isUserInitiated)onEdited();});}).catch(e=>{if(active)setFailure(errorMessage(e));});return()=>{active=false;onReady(null);calc.current?.unobserveEvent('change.vivacity');calc.current?.destroy();calc.current=null;};},[runId]);
 useEffect(()=>{const c=calc.current;if(!c||!key)return;
  // Programmatic updates only mirror canonical measurements. Desmos edits are a scratch view.
  const table=(id:string,data:[number,number][],color:string,subscript:number):GraphExpression=>({id,type:'table',columns:[{latex:`x_${subscript}`,values:data.map(v=>desmosNumber(v[0]))},{latex:`y_${subscript}`,values:data.map(v=>desmosNumber(v[1])),color,points:true,lines:false}]});
  c.setExpression(table('observations',points,'#ddb879',1));
  if(comparison)c.setExpression(table('comparison_observations',comparison.points,'#d1a7e7',2));else c.removeExpression({id:'comparison_observations'});
  if(!edited){
   for(let i=0;i<5;i++){if(model&&i<model.parameters.length)c.setExpression({id:`parameter_${i+1}`,latex:`a_{${i+1}}=${desmosNumber(model.parameters[i])}`});else c.removeExpression({id:`parameter_${i+1}`});}
   if(model)c.setExpression({id:'fitted_model',latex:model.editable_latex,color:'#78d1b3'});else c.removeExpression({id:'fitted_model'});
  }
  if(comparison?.model)c.setExpression({id:'comparison_model',latex:comparison.model.equation_latex,color:'#d1a7e7'});else c.removeExpression({id:'comparison_model'});
  c.updateSettings({xAxisLabel:'Simulation time (s)',yAxisLabel:`${quantity} (${unit})`});
  if(!edited&&points.length>1){const ys=points.map(p=>p[1]),span=Math.max(.01,Math.max(...ys)-Math.min(...ys));c.setMathBounds({left:points[0][0],right:points.at(-1)![0]+Math.max(.1,(points.at(-1)![0]-points[0][0])*.05),bottom:Math.min(...ys)-span*.2,top:Math.max(...ys)+span*.2});}
 },[points,model,comparison,quantity,unit,edited,runId,ready]);
 if(!key)return <p className="factory-stage-note">Interactive Desmos graph requires an authorized Desmos API key. The measured graph, validated equations and exports remain available here.</p>;
 return <>{failure&&<p role="alert">{failure}</p>}<div ref={host} className="factory-desmos" aria-label="Interactive Desmos graph of measured points and editable fitted functions"/></>;
}

export default function FactoryDiscovery({run,frames}:{run:FactoryRun;frames:FactoryFrame[]}){
 const [record,setRecord]=useState<FactoryDiscoveryRecord|null>(null),[failure,setFailure]=useState<string|null>(null),[quantity,setQuantity]=useState<Quantity>('z'),[modelName,setModelName]=useState<string|null>(null),[edited,setEdited]=useState(false),[history,setHistory]=useState<FactoryRun[]>([]),[compareId,setCompareId]=useState(''),[compare,setCompare]=useState<{record:FactoryDiscoveryRecord;frames:FactoryFrame[]}|null>(null),[calculator,setCalculator]=useState<Calculator|null>(null),[snapshotMessage,setSnapshotMessage]=useState<string|null>(null);
 const runStatus=useRef(run.status);runStatus.current=run.status;
 useEffect(()=>{let active=true,timer:ReturnType<typeof setTimeout>,retries=0;async function poll(){try{const value=await factoryApi.discovery(run.id);if(!active)return;setRecord(value);setFailure(null);const waitingForFinalFits=value.sample_count>=25&&Object.keys(value.series).length<choices.length;
   if(['queued','running','paused'].includes(runStatus.current)||value.processing||waitingForFinalFits&&retries++<20)timer=setTimeout(poll,1800);
   else if(waitingForFinalFits)setFailure('Equation worker has not completed. Reload to retry; recorded measurements remain saved.');
  }catch(error){if(active){setFailure(errorMessage(error));timer=setTimeout(poll,3000);}}}poll();return()=>{active=false;clearTimeout(timer);};},[run.id]);
 useEffect(()=>{factoryApi.history().then(rows=>setHistory(rows.filter(row=>row.id!==run.id))).catch(()=>{});},[run.id]);
 useEffect(()=>{let active=true;setCompare(null);if(!compareId)return;async function load(){try{const [r,page]=await Promise.all([factoryApi.discovery(compareId),factoryApi.samples(compareId,-1)]);let frames=[...page.frames],after=page.next_index;while(after<page.total_samples-1&&frames.length<3000){const next=await factoryApi.samples(compareId,after);frames=[...frames,...next.frames];after=next.next_index;}if(active)setCompare({record:r,frames});}catch(error){if(active)setFailure(errorMessage(error));}}load();return()=>{active=false;};},[compareId]);
 const series=record?.series[quantity],models=series?.models??[],selected=models.find(m=>m.model===modelName)??models.find(m=>m.model===series?.selected_model)??null;
 const selectedStatus=selected?.validation_status??(selected?'validation unavailable':'');
 const points=useMemo(()=>pointsFor(frames,quantity),[frames,quantity]);
 const comparisonSeries=compare?.record.series[quantity],comparisonModel=comparisonSeries?.models.find(m=>m.model===comparisonSeries.selected_model)??null;
 const comparisonPoints=useMemo(()=>compare?pointsFor(compare.frames,quantity):undefined,[compare,quantity]);
 function switchModel(value:string){setModelName(value);setEdited(false);}
 const saveSnapshot=()=>download(JSON.stringify({schema_version:'vivacity.desmos-ready/1.0',run_id:run.id,comparison_run_id:compareId||null,quantity,unit:series?.unit??'',observations:points,model:selected,comparison_observations:comparisonPoints??null,comparison_model:comparisonModel,desmos_state:calculator?.getState()??null,source:'MuJoCo observations; fitted approximations; Desmos edits are exploratory and do not alter measurements'}),`vivacity-${run.id}-${quantity}-desmos.json`);
 async function reopenSnapshot(file:File){
  try{
   if(!calculator)throw new Error('The Desmos calculator is not ready.');
   if(file.size>1_048_576)throw new Error('Snapshot exceeds the 1 MiB import limit.');
   const state=parseDesmosSnapshot(await file.text(),run.id,quantity);
   calculator.setState(state);
   setEdited(true);setFailure(null);setSnapshotMessage('Saved Desmos analysis reopened. Original MuJoCo measurements remain unchanged.');
  }catch(error){setFailure(errorMessage(error));setSnapshotMessage(null);}
 }
 return <section className="factory-discovery" aria-label="Mathematical discovery"><header><div><span className="factory-eyebrow">Mathematical discovery</span><h2>From measurements to equations</h2><p>Automatic, time-ordered model fitting from recorded MuJoCo frames. Equations describe this run; they do not establish physical laws or causation.</p></div></header>
  <div className="factory-discovery-controls"><label>Measured relationship<select value={quantity} onChange={e=>{setQuantity(e.target.value as Quantity);setModelName(null);setEdited(false);}}>{choices.map(([value,label])=><option key={value} value={value}>{label} vs simulation time</option>)}</select></label><label>Model family<select value={selected?.model??''} onChange={e=>switchModel(e.target.value)} disabled={!models.length}><option value="">Waiting for fit</option>{models.map(m=><option key={m.model} value={m.model}>{m.model.replaceAll('_',' ')}</option>)}</select></label><label>Compare saved run<select value={compareId} onChange={e=>setCompareId(e.target.value)}><option value="">None</option>{history.map(row=><option key={row.id} value={row.id}>{new Date(row.created_at*1000).toLocaleString()} · {row.status}</option>)}</select></label></div>
  {failure&&<p role="alert">{failure}</p>}
  <p role="status">{record?.processing?'Updating equation in background · ':''}{series?`${series.sample_count} measured points · ${series.fit_stage??'saved'} fit · ${selectedStatus.replaceAll('_',' ')}`:`${record?.sample_count??0} saved points · collecting at least 25 for model fitting`}</p>
  <div className="factory-discovery-legend"><span><i className="observed"/>Original MuJoCo measurements</span><span><i className="fitted"/>Fitted approximation</span>{comparisonPoints&&<span><i className="compared"/>Comparison run</span>}</div>
  <OutcomePlot points={points} curve={selected?.predicted_curve??[]} comparison={comparisonModel?.predicted_curve}/>
  {selected&&<div className="factory-discovery-evidence">
   <div className="factory-discovery-equation-card"><strong>{selected.model.replaceAll('_',' ')} · {selectedStatus.replaceAll('_',' ')}</strong><MathEquation latex={selected.display_latex??selected.equation_latex}/><p className="factory-discovery-equation-hint">Swipe the equation to see all terms.</p><p className="factory-discovery-equation-units">y: {series?.label} ({series?.unit}) · {selected.display_latex?'t':'x'}: simulation time (s)</p></div>
   <dl><div><dt>Training RMSE</dt><dd>{fmt(selected.training.rmse)} {series?.unit}</dd></div><div><dt>Held-out RMSE</dt><dd>{fmt(selected.validation.rmse)} {series?.unit}</dd></div><div><dt>Training MAE</dt><dd>{fmt(selected.training.mae)} {series?.unit}</dd></div><div><dt>Held-out MAE</dt><dd>{fmt(selected.validation.mae)} {series?.unit}</dd></div><div><dt>Training R²</dt><dd>{fmt(selected.training.r2)}</dd></div><div><dt>Held-out R²</dt><dd>{fmt(selected.validation.r2)}</dd></div></dl><p>{series?.train_count} train / {series?.held_out_count} future holdout · updated {series?.updated_at?new Date(series.updated_at*1000).toLocaleTimeString():'—'} · valid domain {fmt(selected.domain_s[0])}–{fmt(selected.domain_s[1])} s.</p><p>{selected.validation_status?(selected.validation_status==='poor_fit'?'This model does not predict the held-out interval well enough.': 'Time-ordered 20% holdout; descriptive approximation only.'):'This saved fit predates per-model validation. Run a new experiment for a graded result.'}</p></div>}
  {record?.relationships?.map(relation=><details key={relation.name} className="factory-discovery-relationship"><summary>Joint torque and motion · {relation.status.replaceAll('_',' ')}</summary><p>{relation.sample_count} complete MuJoCo joint measurements. {relation.reason}</p>{relation.models.map(model=><div key={model.model} className="factory-discovery-relationship-model"><strong>{model.model.replaceAll('_',' ')}</strong><MathEquation latex={relationshipLatex(model)}/><p>Held-out RMSE {fmt(model.validation.rmse)} N m · R² {fmt(model.validation.r2)} · {model.validation_status.replaceAll('_',' ')}</p></div>)}<p>{relation.scope}</p></details>)}
  <div className="factory-analysis-tools"><button disabled={!selected} onClick={()=>{if(selected)navigator.clipboard.writeText(selected.display_latex??selected.equation_latex).catch(e=>setFailure(errorMessage(e)));}}>Copy LaTeX</button><button onClick={()=>download(['time_s,'+quantity+' ['+(series?.unit??'')+']',...points.map(p=>p.join(','))].join('\r\n'),`vivacity-${run.id}-${quantity}.csv`,'text/csv')}>Export measured CSV</button><button onClick={saveSnapshot}>Save Desmos-ready snapshot</button>{key&&<label>Reopen Desmos snapshot<input type="file" accept="application/json,.json" disabled={!calculator} onChange={event=>{const file=event.target.files?.[0];if(file)void reopenSnapshot(file);event.target.value='';}}/></label>}</div>
  {snapshotMessage&&<p role="status" className="factory-stage-note">{snapshotMessage}</p>}
  <DesmosGraph runId={run.id} quantity={quantity} unit={series?.unit??''} points={points} model={selected} comparison={compareId&&comparisonPoints?{id:compareId,points:comparisonPoints,model:comparisonModel}:undefined} edited={edited} onEdited={()=>setEdited(true)} onReady={setCalculator}/>
  {edited&&<p className="factory-stage-note">The Desmos view contains user edits. New fitted parameters will resume when you choose a model again. Original saved measurements and fitted results are unchanged.</p>}
 </section>;
}
