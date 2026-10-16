import { Component, memo, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react';
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { Group, Plane, Quaternion, Vector3, PCFShadowMap } from 'three';
import { type Dict, type RobotFrame, type Vec3 } from './domain';
import { clampPickupPosition, objectHalfSizes } from './pickupWorkspace';
import {ImportedVisual} from './WorldPreview';
import {workspaceApi,type LibraryWorld} from './workspaceApi';
import type {components} from './generated/api';
import EnvironmentAppearance,{appearanceFor} from './EnvironmentAppearance';
import {loadAssets,GeomMesh,type Assets} from './RobotAssets';
export {loadAssets,GeomMesh,type Assets} from './RobotAssets';
import EngineeringOverlay,{type OverlayOptions} from './EngineeringOverlay';
import RenderQualityControl,{useRenderQuality} from './QualityControl';
import {qualityProfiles} from './renderQuality';

type CameraController={target:Vector3;getPolarAngle:()=>number;setPolarAngle:(n:number)=>void;getAzimuthalAngle:()=>number;setAzimuthalAngle:(n:number)=>void;update:()=>unknown};
function CameraInteraction({command,enabled,catalog=false}:{command:{key:string;seq:number};enabled:boolean;catalog?:boolean}){
  const controls=useRef<CameraController|null>(null);
  const {camera,invalidate}=useThree();
  const orbitTarget=useMemo(()=>catalog?[.12,0,.35] as Vec3:[.35,0,.3] as Vec3,[catalog]);
  useEffect(()=>{
    const c=controls.current;if(!c)return;
    if(!command.key||command.key.startsWith('preset:')){const preset=command.key.slice(7);camera.position.set(...(preset==='top'?[.4,-.01,2.8]:preset==='side'?[1.9,0,.8]:catalog?[1.1,-1.2,.9]:[1.8,-2.1,1.35]) as Vec3);c.target.set(...(catalog?[.12,0,.35]:[.35,0,.3]) as Vec3);c.update();invalidate();return;}
    if(command.key.startsWith('Shift+Arrow')){const right=new Vector3(1,0,0).applyQuaternion(camera.quaternion),up=new Vector3(0,1,0).applyQuaternion(camera.quaternion);const delta=(command.key.includes('Left')||command.key.includes('Right')?right:up).multiplyScalar(command.key.includes('Left')||command.key.includes('Down')?-.08:.08);camera.position.add(delta);c.target.add(delta);c.update();invalidate();return;}
    if(command.key==='ArrowLeft'||command.key==='ArrowRight')c.setAzimuthalAngle(c.getAzimuthalAngle()+(command.key==='ArrowLeft'?.12:-.12));
    if(command.key==='ArrowUp'||command.key==='ArrowDown')c.setPolarAngle(Math.max(.1,Math.min(Math.PI*.49,c.getPolarAngle()+(command.key==='ArrowUp'?-.1:.1))));
    if(['+','=','-'].includes(command.key)){camera.position.sub(c.target).multiplyScalar(command.key==='-'?1.15:1/1.15).add(c.target);c.update();}
    invalidate();
  },[command,camera,invalidate,catalog]);
  return <OrbitControls ref={c=>{controls.current=c;}} enabled={enabled} makeDefault target={orbitTarget} minDistance={.7} maxDistance={4} maxPolarAngle={Math.PI*.49} enableDamping={false} />;
}

type CubeDrag = { pointerId:number; start:Vec3; draft:Vec3; offsetX:number; offsetY:number; moved:boolean };
function MeasuredRobot({ assets, frames, cursor, config, playing, renderTime, canMoveCube, onMoveCube, onDragging, onHover, onDragError, onSelect }: { assets: Assets; frames: RobotFrame[]; cursor: RefObject<number>; config: Dict; playing:boolean; renderTime:number; canMoveCube:boolean; onMoveCube:(point:Vec3)=>Promise<boolean>; onDragging:(active:boolean)=>void; onHover:(active:boolean)=>void; onDragError:(message:string|null)=>void;onSelect:(s:'object'|'robot')=>void }) {
  const invalidate=useThree(state=>state.invalidate);
  useEffect(()=>{invalidate();},[invalidate,frames,playing,renderTime]);
  const groups = useRef(new Map<string,Group>());
  const poseA = new Vector3(), poseB = new Vector3(), qa = new Quaternion(), qb = new Quaternion();
  const frameTimes = useRef<number[]>([]);
  const drag=useRef<CubeDrag|null>(null),preview=useRef<Vec3|null>(null);
  const halfSizes=objectHalfSizes(config);
  const dragPlane=useMemo(()=>new Plane(new Vector3(0,0,1),-(halfSizes[2]+.001)),[halfSizes[2]]);
  const dragPoint=new Vector3();
  useEffect(()=>{preview.current=null;drag.current=null;onDragging(false);invalidate();},[config.cube_position,invalidate,onDragging]);
  const pointOnTable=(event:ThreeEvent<PointerEvent>)=>event.ray.intersectPlane(dragPlane,dragPoint);
  const pointerDown=(event:ThreeEvent<PointerEvent>)=>{
    onSelect('object');
    if(!canMoveCube)return;
    const point=pointOnTable(event),group=groups.current.get('target');if(!point||!group)return;
    event.stopPropagation();(event.target as Element|null)?.setPointerCapture(event.pointerId);
    const start=group.position.toArray() as Vec3;
    drag.current={pointerId:event.pointerId,start,draft:start,offsetX:start[0]-point.x,offsetY:start[1]-point.y,moved:false};
    preview.current=start;onDragging(true);onDragError(null);invalidate();
  };
  const pointerMove=(event:ThreeEvent<PointerEvent>)=>{
    const active=drag.current;if(!active||active.pointerId!==event.pointerId)return;
    const point=pointOnTable(event);if(!point)return;
    event.stopPropagation();
    const next=clampPickupPosition(point.x+active.offsetX,point.y+active.offsetY,halfSizes);
    active.draft=next;active.moved ||= Math.hypot(next[0]-active.start[0],next[1]-active.start[1])>.002;
    preview.current=next;invalidate();
  };
  const pointerUp=(event:ThreeEvent<PointerEvent>)=>{
    const active=drag.current;if(!active||active.pointerId!==event.pointerId)return;
    event.stopPropagation();(event.target as Element|null)?.releasePointerCapture(event.pointerId);
    drag.current=null;onDragging(false);
    if(!active.moved){preview.current=null;invalidate();return;}
    void onMoveCube(active.draft).then(applied=>{
      if(!applied)onDragError('The object could not be moved. Check the scene settings and try again.');
      preview.current=null;invalidate();
    });
  };
  const pointerCancel=(event:ThreeEvent<PointerEvent>)=>{
    if(!drag.current||drag.current.pointerId!==event.pointerId)return;
    drag.current=null;preview.current=null;onDragging(false);invalidate();
  };
  const lastPlaybackFrame=useRef<number|null>(null);
  useEffect(()=>{lastPlaybackFrame.current=playing?performance.now():null;if(playing)frameTimes.current=[];},[playing]);
  useFrame((_state,delta) => {
    if(playing) invalidate();
    if (!frames.length) return;
    const t = frames[0].time+cursor.current;
    let i = frames.findIndex(frame => frame.time >= t); if (i < 0) i = frames.length-1;
    const a = frames[Math.max(0,i-1)], b = frames[i];
    const alpha = b.time > a.time ? Math.max(0,Math.min(1,(t-a.time)/(b.time-a.time))) : 0;
    const diagnostics: Record<string,number[]> = {};
    const orientations:Record<string,number[]>={};
    a.body_transforms.forEach((pose,index) => {
      const next = b.body_transforms[index]; const group = groups.current.get(pose.name);
      if (!group || !next) return;
      group.position.copy(poseA.fromArray(pose.position).lerp(poseB.fromArray(next.position),alpha));
      if(pose.name==='target'&&preview.current)group.position.fromArray(preview.current);
      qa.set(pose.quaternion_wxyz[1],pose.quaternion_wxyz[2],pose.quaternion_wxyz[3],pose.quaternion_wxyz[0]);
      qb.set(next.quaternion_wxyz[1],next.quaternion_wxyz[2],next.quaternion_wxyz[3],next.quaternion_wxyz[0]);
      group.quaternion.copy(qa.slerp(qb,alpha)); diagnostics[pose.name] = group.position.toArray();
      orientations[pose.name]=[group.quaternion.w,group.quaternion.x,group.quaternion.y,group.quaternion.z];
    });
    const end = poseA.fromArray(a.end_effector).lerp(poseB.fromArray(b.end_effector),alpha);
    (window as unknown as {__vivacityScene: unknown}).__vivacityScene = { time: t, endEffector: end.toArray(), bodies: diagnostics, orientationsWXYZ:orientations, cameraPosition:_state.camera.position.toArray(), source: preview.current?'interactive_preview_uncommitted':'measured_mujoco_frames', interpolated: alpha > 0 && alpha < 1 };
    const now=performance.now();
    if(playing && lastPlaybackFrame.current!==null){frameTimes.current.push(now-lastPlaybackFrame.current);lastPlaybackFrame.current=now;}
    if (frameTimes.current.length > 180) frameTimes.current.shift();
    if (frameTimes.current.length >= 2 && playing) {
      const d = window as unknown as {__vivacityPerformance: Dict};
      d.__vivacityPerformance = { ...d.__vivacityPerformance, playbackFrameSamples:frameTimes.current.length, renderMeanFrameMs: frameTimes.current.reduce((s,n)=>s+n,0)/frameTimes.current.length,
        renderP95FrameMs:[...frameTimes.current].sort((a,b)=>a-b)[Math.ceil(frameTimes.current.length*.95)-1] };
    }
  });
  const last = frames.at(-1);
  return <group dispose={null}>
    {assets.manifest.bodies.map(body => <group key={body.id} ref={g=>{ if (g) groups.current.set(body.name,g); else groups.current.delete(body.name); }}
      onPointerDown={body.name==='target'?pointerDown:body.name!=='world'?()=>onSelect('robot'):undefined} onPointerMove={body.name==='target'?pointerMove:undefined}
      onPointerUp={body.name==='target'?pointerUp:undefined} onPointerCancel={body.name==='target'?pointerCancel:undefined}
      onPointerOver={body.name==='target'&&canMoveCube?()=>onHover(true):undefined}
      onPointerOut={body.name==='target'?()=>onHover(false):undefined}>
      {assets.manifest.geoms.filter(g=>g.body_id === body.id && !(config.catalog&&(g.body_id===0||body.name==='target')) && (g.group === 0 || g.group === 2) && !(config.show_environment_appearance&&g.type==='plane') && !(g.name==='obstacle_geom'&&config.obstacle_enabled===false) && !last?.environment_geometries?.some(measured=>measured.name===g.name)).map(geom=><GeomMesh key={geom.id} geom={geom} assets={assets} config={config} />)}
      {!!config.collision_overlay&&assets.manifest.geoms.filter(g=>g.body_id===body.id&&(g.group===3||g.name==='cube')).map(g=><GeomMesh key={'collision-'+g.id} geom={g} assets={assets} config={{...config,collision_overlay:true}}/>)}
      {body.name==='target'&&canMoveCube&&<mesh><boxGeometry args={[.1,.1,.08]}/><meshBasicMaterial transparent opacity={0} depthWrite={false}/></mesh>}
    </group>)}
    {last?.environment_geometries?.filter(geom=>!(config.show_imported_appearance&&geom.name==='environment_import_collision_proxy')&&!config.show_environment_appearance).map((geom,i)=><GeomMesh key={geom.name} geom={{...geom,id:i,body_id:0,group:0,mesh_id:null}} assets={assets} config={{}} />)}
  </group>;
}

class SceneBoundary extends Component<{children: ReactNode;onError:()=>void}, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() { return { error: true }; }
  componentDidCatch() { this.props.onError(); }
  render() { return this.state.error ? null : this.props.children; }
}

function RobotView({ frames, cursor, config, playing, renderTime, canMoveCube=false, onMoveCube=async()=>false,visualWorld,overlays,trace=[],onSelect=()=>{} }: { frames: RobotFrame[]; cursor: RefObject<number>; config: Dict; replaying: boolean; playing:boolean; renderTime:number; canMoveCube?:boolean; onMoveCube?:(point:Vec3)=>Promise<boolean>;visualWorld?:LibraryWorld;overlays?:OverlayOptions;trace?:RobotFrame[];onSelect?:(s:'object'|'robot')=>void }) {
  const [assets,setAssets] = useState<Assets | null>(null), [error,setError] = useState<string | null>(null);
  const [appearanceStatus,setAppearanceStatus]=useState(''),[appearanceError,setAppearanceError]=useState(false);
  const appearance=appearanceFor(visualWorld);
  const quality=useRenderQuality();
  const [dragging,setDragging]=useState(false),[hovering,setHovering]=useState(false),[dragError,setDragError]=useState<string|null>(null);
  const [cameraCommand,setCameraCommand]=useState({key:'',seq:0});
  const [imported,setImported]=useState<components['schemas']['ImportPreview']|null>(null),[showImported,setShowImported]=useState(true);
  useEffect(()=>{let active=true;setImported(null);setAppearanceError(false);if(visualWorld?.preview_available&&!appearance)workspaceApi.preview(visualWorld.id).then(p=>active&&setImported(p)).catch(()=>active&&setDragError('Imported appearance could not load. Physical collision geometry remains available.'));return()=>{active=false;};},[visualWorld?.id]);
  const resetCamera=()=>setCameraCommand(c=>({key:'',seq:c.seq+1}));
  const robot=String(config.robot_model??'panda');
  useEffect(() => { let active = true;setAssets(null);setError(null);loadAssets(robot).then(a=>active&&setAssets(a)).catch(e=>active&&setError(String(e))); return ()=>{ active=false; }; },[robot]);
  return <><div className="robot-viewport" data-testid="robot-viewport" tabIndex={0} role="region" aria-label={`${robot==='panda'?'Franka Panda':robot} workcell. ${canMoveCube?'Drag the blue object on the supported table. Change conditions provides keyboard position controls. ':''}Arrow keys orbit, Shift and arrows pan, plus and minus zoom, R resets camera.`} onKeyDown={e=>{if(e.target!==e.currentTarget)return;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-'].includes(e.key)){e.preventDefault();setCameraCommand(c=>({key:e.shiftKey?'Shift+'+e.key:e.key,seq:c.seq+1}));}else if(e.key.toLowerCase()==='r'){e.preventDefault();resetCamera();}}}>
    {!error&&assets&&frames.length>0&&<SceneBoundary onError={()=>setError('3D rendering is unavailable. Your experiment data remains accessible in the inspector. Try a WebGL2-capable browser.')}>
      <Canvas frameloop="demand" shadows={{type:PCFShadowMap}} dpr={qualityProfiles[quality].pixelRatio} style={{cursor:canMoveCube?(dragging?'grabbing':hovering?'grab':'auto'):'auto',touchAction:'none'}} camera={{ position:[1.8,-2.1,1.35], fov: 42, near: .015, far: 100 }} gl={{ antialias: false }} onCreated={({camera,gl})=>{ camera.up.set(0,0,1); gl.setClearColor('#262a2d'); performance.mark('vivacity:robot-scene-ready'); }}>
        <ambientLight intensity={visualWorld?.spec.lighting.ambient??.72} /><hemisphereLight args={['#ffffff','#6f706a',1.8]} />
        <directionalLight position={[1,-1.5,3]} intensity={visualWorld?.spec.lighting.key_intensity??3.2} castShadow shadow-mapSize={[1024,1024]} shadow-bias={-.00005} shadow-normalBias={.008} shadow-camera-left={-1.5} shadow-camera-right={1.5} shadow-camera-top={1.5} shadow-camera-bottom={-1.5} />
        <directionalLight position={[-2,1,1.5]} intensity={1.3} />
        <MeasuredRobot assets={assets} frames={frames} cursor={cursor} config={{...config,show_imported_appearance:(!!imported||!!appearance)&&showImported,show_environment_appearance:!!appearance&&showImported,collision_overlay:overlays?.collision}} playing={playing} renderTime={renderTime} canMoveCube={canMoveCube} onMoveCube={onMoveCube} onDragging={setDragging} onHover={setHovering} onDragError={setDragError} onSelect={onSelect} />
        {overlays&&frames.at(-1)&&<EngineeringOverlay frame={frames.at(-1)!} trace={trace} options={overlays}/>}
        {imported&&showImported&&visualWorld?.mapping&&<ImportedVisual preview={imported} mapping={visualWorld.mapping}/>}
        {appearance&&showImported&&<EnvironmentAppearance world={visualWorld} appearance={appearance} onStatus={(message,failed=false)=>{setAppearanceStatus(message);setAppearanceError(failed);}}/>}
        <CameraInteraction command={cameraCommand} enabled={!dragging} catalog={!!config.catalog} />
      </Canvas>
    </SceneBoundary>}
  </div>
    <div className="scene-toolbar"><span>{robot==='panda'?'Franka Panda':robot.toUpperCase()} · {visualWorld?.name??'Physical workcell'}</span><label>View<select aria-label="Camera preset" value={cameraCommand.key.startsWith('preset:')?cameraCommand.key.slice(7):'perspective'} onChange={e=>setCameraCommand(c=>({key:'preset:'+e.target.value,seq:c.seq+1}))}><option value="perspective">Perspective</option><option value="top">Top</option><option value="side">Side</option></select></label><button type="button" onClick={resetCamera}>Reset camera</button>{(imported||appearance)&&<label><input type="checkbox" checked={showImported} onChange={e=>setShowImported(e.target.checked)}/> Environment</label>}</div>
    <div className="scene-quality"><RenderQualityControl worldId={visualWorld?.id}/></div>
    {appearanceStatus&&<p className={appearanceError?'negative small':'small'} role={appearanceError?'alert':'status'}>{appearanceStatus}</p>}
    {(error||dragError)&&<p className="negative" role="alert">{error??dragError}</p>}
    {!error&&(!assets||!frames.length)&&<p className="small" role="status">{!assets?'Loading Panda geometry…':'Waiting for a measured world state…'}</p>}
  </>;
}
export default memo(RobotView);
