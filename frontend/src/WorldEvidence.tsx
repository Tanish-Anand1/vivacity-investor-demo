import {useState} from 'react';
import {API,errorMessage} from './api';
import {workspaceToken,type LibraryWorld} from './workspaceApi';

export default function WorldEvidence({world}:{world:LibraryWorld}){
 const [error,setError]=useState<string|null>(null),[busy,setBusy]=useState(false);
 if(!world.representations)return null;
 const download=async()=>{setBusy(true);setError(null);try{
  const response=await fetch(`${API}/v1/workspace/worlds/${encodeURIComponent(world.id)}/geometry`,{headers:{'X-Workspace-Token':workspaceToken()},signal:AbortSignal.timeout(60000)});
  if(!response.ok)throw new Error('Original collider bytes could not be retrieved.');
  const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download=`vivacity-${world.id}-source.glb`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 }catch(e){setError(errorMessage(e));}finally{setBusy(false);}};
 return <details className="world-technical"><summary>Representation evidence & capture provenance</summary><p className="small">Appearance, geometric evidence and physical collisions are separate. The solid box proxy is configured; generated interiors and physical properties are uncalibrated.</p><pre className="generation-spec">{JSON.stringify({representations:world.representations,generation:world.generation},null,2)}</pre><button className="secondary" disabled={busy} onClick={download}>{busy?'Retrieving…':'Download preserved collider GLB'}</button>{error&&<p role="alert" className="negative">{error}</p>}</details>;
}
