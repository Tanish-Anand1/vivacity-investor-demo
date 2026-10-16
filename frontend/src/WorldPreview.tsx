import {useEffect,useMemo,useState,useRef} from 'react';
import {Canvas} from '@react-three/fiber';
import {OrbitControls} from '@react-three/drei';
import {BufferAttribute,BufferGeometry,DoubleSide,Spherical,Vector3,Box3} from 'three';
import {useThree} from '@react-three/fiber';
import type {OrbitControls as OrbitControlsImpl} from 'three-stdlib';
import type {LibraryWorld} from './workspaceApi';
import {workspaceApi} from './workspaceApi';
import type {components} from './generated/api';
import SceneBoundary from './SceneBoundary';
import EnvironmentAppearance,{appearanceFor} from './EnvironmentAppearance';
import RenderQualityControl,{useRenderQuality} from './QualityControl';
import {qualityProfiles} from './renderQuality';

export function ImportedVisual({preview,mapping}:{preview:components['schemas']['ImportPreview'];mapping:Record<string,unknown>}){
  const geometry=useMemo(()=>{
    const scale=Number(mapping.scale??1),center=mapping.original_center_m as number[]??[0,0,0];
    const positions=preview.positions.flatMap(p=>{
      const converted=mapping.up_axis==='z'?p:[p[0],-p[2],p[1]];
      return converted.map((v,i)=>v*scale-center[i]);
    });
    const g=new BufferGeometry();g.setAttribute('position',new BufferAttribute(new Float32Array(positions),3));g.setIndex(preview.indices);g.computeVertexNormals();return g;
  },[preview,mapping]);
  useEffect(()=>()=>geometry.dispose(),[geometry]);
  const pos=mapping.position_m as [number,number,number]??[2.5,2.5,.5];
  return <mesh geometry={geometry} position={pos}><meshStandardMaterial color="#8a9995" side={DoubleSide} roughness={.8}/></mesh>;
}

function PreviewControls({target,distance,reset=0,elevation=.9}:{target:[number,number,number];distance:number;reset?:number;elevation?:number}){
  const controls=useRef<OrbitControlsImpl>(null);const {camera,gl,invalidate}=useThree();
  useEffect(()=>{const reset=()=>{camera.position.set(target[0]+distance,target[1]-distance*1.3,target[2]+distance*elevation);controls.current?.target.set(...target);controls.current?.update();invalidate();};reset();const canvas=gl.domElement;canvas.tabIndex=0;canvas.setAttribute('aria-label','Environment preview. Arrow keys orbit, Shift and arrows pan, plus and minus zoom, R resets.');
    const key=(e:KeyboardEvent)=>{const c=controls.current;if(!c||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','r','R'].includes(e.key))return;e.preventDefault();
      if(e.shiftKey&&e.key.startsWith('Arrow')){const v=new Vector3(e.key==='ArrowLeft'?-.12:e.key==='ArrowRight'?.12:0,e.key==='ArrowDown'?-.12:e.key==='ArrowUp'?.12:0,0).applyQuaternion(camera.quaternion);camera.position.add(v);c.target.add(v);}else if(e.key.toLowerCase()==='r'){reset();}else{const offset=new Vector3().copy(camera.position).sub(c.target);offset.applyQuaternion(camera.quaternion.clone().setFromUnitVectors(camera.up,new Vector3(0,1,0)));const s=new Spherical().setFromVector3(offset);
        if(e.key==='ArrowLeft')s.theta-=.12;if(e.key==='ArrowRight')s.theta+=.12;if(e.key==='ArrowUp')s.phi-=.12;if(e.key==='ArrowDown')s.phi+=.12;if(e.key==='+'||e.key==='=')s.radius*=.9;if(e.key==='-')s.radius*=1.1;s.makeSafe();offset.setFromSpherical(s).applyQuaternion(camera.quaternion.clone().setFromUnitVectors(new Vector3(0,1,0),camera.up));camera.position.copy(c.target).add(offset);}
      c.update();invalidate();};canvas.addEventListener('keydown',key);return()=>canvas.removeEventListener('keydown',key);},[camera,gl,invalidate,target[0],target[1],target[2],distance,reset,elevation]);
  return <OrbitControls ref={controls} makeDefault enableDamping={false} target={target}/>;
}

function PreviewRefresh({revision}:{revision:unknown}){
  const {invalidate}=useThree();
  useEffect(()=>{invalidate();},[invalidate,revision]);
  return null;
}

export default function WorldPreview({world}:{world:LibraryWorld}){
  const [preview,setPreview]=useState<components['schemas']['ImportPreview']|null>(null),[error,setError]=useState<string|null>(null);
  const [loading,setLoading]=useState(''),[bounds,setBounds]=useState<Box3|null>(null),[reset,setReset]=useState(0);
  const appearance=appearanceFor(world);
  const quality=useRenderQuality();
  useEffect(()=>{let active=true;setPreview(null);setError(null);setBounds(null);setLoading('');if(world.preview_available&&!appearance)workspaceApi.preview(world.id).then(p=>active&&setPreview(p)).catch(()=>active&&setError('Original geometry could not load.'));return()=>{active=false;};},[world.id]);
  const size=bounds?.getSize(new Vector3()),center=bounds?.getCenter(new Vector3());
  // Splat bounds can include distant outliers. Frame the aligned workcell ground
  // at an interior eye height rather than putting the camera below/above the room.
  const focus:[number,number,number]=appearance?.format==='spz'?[.2,.7,.35]:bounds&&center?center.toArray() as [number,number,number]:(world.mapping?.position_m as [number,number,number]|undefined)??[.4,0,0];
  const distance=appearance?.format==='spz'?2:bounds&&size?Math.max(...size.toArray())*1.1:world.mapping?Math.max(2.4,Math.max(...world.spec.geometries[0].size)*3.2):4;
  return <><div className="world-preview" aria-label={`${world.name}: static scene preview, not an executed experiment`}><SceneBoundary><Canvas frameloop="demand" dpr={qualityProfiles[quality].pixelRatio} gl={{antialias:false}} camera={{position:[4,-5,3.5],near:.015,far:150,fov:55}} onCreated={({camera,gl})=>{camera.up.set(0,0,1);gl.setClearColor('#262a2d');}}>
    <ambientLight intensity={world.spec.lighting.ambient}/><directionalLight position={[2,-2,6]} intensity={world.spec.lighting.key_intensity}/>
    {!appearance&&<mesh position={[.4,0,-.04]}><boxGeometry args={[1.4,1.3,.08]}/><meshStandardMaterial color="#b9ae95"/></mesh>}
    {!appearance&&world.source!=='worldlabs'&&world.spec.geometries.filter(g=>!preview||g.name!=='import_collision_proxy').map(g=><mesh key={g.name} position={g.position as [number,number,number]} rotation={g.type==='cylinder'?[Math.PI/2,0,0]:undefined}>{g.type==='box'?<boxGeometry args={g.size.map(v=>v*2) as [number,number,number]}/>:<cylinderGeometry args={[g.size[0],g.size[0],g.size[1]*2,24]}/>}<meshStandardMaterial color={`rgb(${g.rgba.slice(0,3).map(v=>Math.round(v*255)).join(',')})`}/></mesh>)}
    {preview&&world.mapping&&world.source!=='worldlabs'&&<ImportedVisual preview={preview} mapping={world.mapping}/>}<PreviewControls target={focus} distance={distance} reset={reset} elevation={appearance?.format==='spz'?.35:.9}/><PreviewRefresh revision={[preview,reset,bounds]}/>
    {appearance&&<EnvironmentAppearance world={world} appearance={appearance} onStatus={(m,failed)=>{setLoading(failed?'':m);setError(failed?m:null);}} onBounds={setBounds}/>}
  </Canvas></SceneBoundary></div><div className="scene-toolbar"><span>{appearance?(appearance.format==='spz'?'World Labs · colored 3D splats':'Original mesh · embedded materials'):'Simplified collision workcell'}</span><RenderQualityControl worldId={world.id}/><button onClick={()=>setReset(r=>r+1)}>Reset camera</button></div>{loading&&<p className="small" role="status">{loading}</p>}{world.source==='worldlabs'&&!appearance&&<p role="alert" className="negative">This older world has no visual asset recorded. Generate a new environment to load its colored appearance.</p>}{error&&<p role="alert" className="negative">{error}</p>}</>;
}
