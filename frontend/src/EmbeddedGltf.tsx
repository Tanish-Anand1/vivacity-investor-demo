import {useEffect} from 'react';
import {useThree} from '@react-three/fiber';
import {Box3,Mesh,Material,Texture,Object3D} from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {API} from './api';
import {workspaceToken,type LibraryWorld} from './workspaceApi';

function dispose(root:Object3D){const textures=new Set<Texture>();root.traverse(o=>{if(o instanceof Mesh){o.geometry.dispose();const materials=Array.isArray(o.material)?o.material:[o.material];materials.forEach((m:Material)=>{Object.values(m).forEach(v=>{if(v instanceof Texture)textures.add(v);});m.dispose();});}});textures.forEach(t=>t.dispose());}
export default function EmbeddedGltf({world,onStatus,onBounds}:{world:LibraryWorld;onStatus:(message:string,error?:boolean)=>void;onBounds?:(bounds:Box3)=>void}){
 const {scene,invalidate}=useThree();
 useEffect(()=>{let active=true,root:Object3D|undefined;const abort=new AbortController();onStatus('Loading geometry and materials…');
  const load=async()=>{const r=await fetch(`${API}/v1/workspace/worlds/${encodeURIComponent(world.id)}/appearance`,{headers:{'X-Workspace-Token':workspaceToken()},signal:abort.signal});if(!r.ok)throw new Error(`Embedded environment could not load (${r.status}).`);const gltf=await new GLTFLoader().parseAsync(await r.arrayBuffer(),'');if(!active){dispose(gltf.scene);return;}root=gltf.scene;const mapping=world.mapping??{},scale=Number(mapping.scale??1),center=mapping.original_center_m as number[]??[0,0,0],position=mapping.position_m as number[]??[0,0,0];root.scale.setScalar(scale);if(mapping.up_axis!=='z')root.rotation.x=Math.PI/2;root.position.set(...position.map((v,i)=>v-center[i]) as [number,number,number]);root.traverse(o=>{if(o instanceof Mesh){o.castShadow=true;o.receiveShadow=true;}});scene.add(root);root.updateMatrixWorld(true);onBounds?.(new Box3().setFromObject(root));onStatus('');invalidate();};
  load().catch(e=>{if(active&&e.name!=='AbortError')onStatus(e.message,true);});return()=>{active=false;abort.abort();if(root){scene.remove(root);dispose(root);}};
 },[world.id,world.version,scene,invalidate]);return null;
}
