import {useSyncExternalStore,useState,useEffect} from 'react';
import {defaultQuality,qualityProfiles,type RenderQuality} from './renderQuality';
const event='vivacity:render-quality';
function read():RenderQuality{
 const saved=localStorage.getItem(event);
 return saved==='performance'||saved==='balanced'||saved==='high'?saved:defaultQuality((navigator as Navigator&{deviceMemory?:number}).deviceMemory,navigator.hardwareConcurrency);
}
const subscribe=(fn:()=>void)=>{window.addEventListener(event,fn);return()=>window.removeEventListener(event,fn);};
export function useRenderQuality(){return useSyncExternalStore(subscribe,read,()=> 'balanced' as RenderQuality);}
export default function RenderQualityControl({worldId}:{worldId?:string}){
 const quality=useRenderQuality();
 const [diagnostics,setDiagnostics]=useState<Record<string,unknown>|null>(null);
 useEffect(()=>{setDiagnostics(null);const loaded=(e:Event)=>{const detail=(e as CustomEvent).detail;if(!worldId||detail.world===worldId)setDiagnostics(detail);};window.addEventListener('vivacity:world-loaded',loaded);return()=>window.removeEventListener('vivacity:world-loaded',loaded);},[worldId]);
 return <div><label className="render-quality">View quality <select value={quality} onChange={e=>{localStorage.setItem(event,e.target.value);window.dispatchEvent(new Event(event));}}>{Object.entries(qualityProfiles).map(([id,p])=><option key={id} value={id}>{p.label}</option>)}</select></label>{diagnostics&&<details className="render-diagnostics"><summary>Rendering diagnostics</summary><pre className="generation-spec">{JSON.stringify(diagnostics,null,2)}</pre><p className="small">Measured load/decode/LOD time and Three.js resource counts, not total GPU memory. View-dependent LOD budget is a target. Physics runs on the backend.</p></details>}</div>;
}
