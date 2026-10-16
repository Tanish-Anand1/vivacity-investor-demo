import type {LibraryWorld} from './workspaceApi';
import {useEffect,useState} from 'react';
import {API} from './api';
import {workspaceToken} from './workspaceApi';

/** Orthographic projection of the real typed box collision geometry.
 * It is a geometry preview, never an experiment result or a facility photo.
 */
export default function WorldThumbnail({world}:{world:LibraryWorld}){
 const [thumbnail,setThumbnail]=useState<string|null>(null);
 useEffect(()=>{let active=true,url:string|undefined;const controller=new AbortController();setThumbnail(null);
  if(world.thumbnail_available)fetch(`${API}/v1/workspace/worlds/${encodeURIComponent(world.id)}/thumbnail`,{headers:{'X-Workspace-Token':workspaceToken()},signal:controller.signal})
   .then(r=>{if(!r.ok)throw new Error('Thumbnail unavailable');return r.blob();}).then(blob=>{if(active){url=URL.createObjectURL(blob);setThumbnail(url);}}).catch(()=>{});
  return()=>{active=false;controller.abort();if(url)URL.revokeObjectURL(url);};},[world.id,world.thumbnail_available]);
 if(thumbnail)return <img className="world-thumbnail" src={thumbnail} alt={`${world.name}: actual provider preview of this generated environment`} loading="lazy"/>;
 if(['warehouse','robotics_lab'].includes(world.id))return <img className="world-thumbnail" src={`/vivacity/world-previews/${world.id}.jpg?v=2`} alt={`${world.name}, captured from its actual colored 3D environment`} loading="lazy"/>;
 const shapes=world.spec.geometries.filter(g=>g.type==='box');
 const project=(x:number,y:number,z:number)=>[(x-y)*.866,(x+y)*.5-z];
 const faces=shapes.flatMap(g=>{
  const corners=Array.from({length:8},(_,i)=>g.position.map((v,j)=>v+g.size[j]*(i&(1<<j)?1:-1)));
  return [[4,5,7,6],[0,1,5,4],[1,3,7,5]].map((indices,i)=>({points:indices.map(k=>project(...corners[k] as [number,number,number])),color:`rgb(${g.rgba.slice(0,3).map(v=>Math.round(v*(i===0?255:210))).join(',')})`,depth:g.position[0]+g.position[1]+g.position[2]*.01}));
 }).sort((a,b)=>a.depth-b.depth);
 const points=faces.flatMap(f=>f.points),xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
 const lo=[Math.min(...xs,0),Math.min(...ys,0)],hi=[Math.max(...xs,1),Math.max(...ys,1)],scale=Math.min(320/(hi[0]-lo[0]),145/(hi[1]-lo[1]));
 return <svg className="world-thumbnail" viewBox="0 0 360 190" role="img" aria-label={`${world.name}: actual box collision configuration, simplified geometry preview`}><rect width="360" height="190" fill="#252b2f"/><g transform={`translate(${180-(hi[0]+lo[0])*.5*scale} ${88-(hi[1]+lo[1])*.5*scale}) scale(${scale})`}>{faces.map((f,i)=><polygon key={i} points={f.points.map(p=>p.join(',')).join(' ')} fill={f.color} stroke="#78878c" strokeWidth={.008}/>)}</g><text x="12" y="178" fill="#d4dfe0" fontSize="9">Collision geometry preview</text></svg>;
}
