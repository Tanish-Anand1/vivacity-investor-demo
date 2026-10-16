import {useEffect,useRef} from 'react';
import {useThree,useFrame} from '@react-three/fiber';
import {Box3,Vector3,PerspectiveCamera} from 'three';
import {SparkRenderer,SplatMesh,SplatFileType} from '@sparkjsdev/spark';
import {API} from './api';
import {workspaceToken,type LibraryWorld} from './workspaceApi';
import EmbeddedGltf from './EmbeddedGltf';
import warehouseProvenance from './generated/warehouseProvenance.json';
import {useRenderQuality} from './QualityControl';
import {qualityProfiles,visualStages,type RenderQuality} from './renderQuality';
const updates=new WeakMap<object,Promise<void>>();

export type Appearance={format:'spz'|'glb';url?:string;urls?:Record<string,string>;qualities?:string[];quality?:string;semantics?:{metric_scale_factor:number;ground_plane_offset:number}|null;metric_scale_verified?:boolean;coordinate_system?:string;visual_scale?:number;visual_ground_y?:number};
// Curated calibration for this older export, whose provider omitted metric metadata.
export const laboratoryAppearance:Appearance={format:'spz',url:'/environments/laboratory/world.spz',quality:'500k',semantics:null,metric_scale_verified:false,coordinate_system:'marble_export_y_up',visual_scale:2.5,visual_ground_y:-.756103516};
export function appearanceFor(world?:LibraryWorld):Appearance|null{
  if(world?.id==='warehouse')return {...(world.appearance??warehouseProvenance.appearance),url:'/environments/warehouse/world.spz',qualities:['100k','500k'],urls:{'100k':'/environments/warehouse/world-100k.spz','500k':'/environments/warehouse/world.spz'}} as Appearance;
  if(world?.id==='robotics_lab')return {...laboratoryAppearance,...world.appearance,qualities:['100k','500k'],urls:{'100k':'/environments/laboratory/world-100k.spz','500k':'/environments/laboratory/world.spz'}} as Appearance;
  if(world?.appearance)return world.appearance as Appearance;
  return null;
}

function SparkEngine({onStatus,quality}:{onStatus:(message:string,error?:boolean)=>void;quality:RenderQuality}){
  const {gl,scene,invalidate,camera}=useThree();
  const state=useRef<{spark:SparkRenderer;active:boolean;pending:Promise<void>|null;signature:string;dirty:boolean}|null>(null);
  const status=useRef(onStatus);status.current=onStatus;
  useEffect(()=>{
    const spark=new SparkRenderer({renderer:gl,autoUpdate:false,minSortIntervalMs:0,maxPixelRadius:128,
      enableLod:true,lodSplatCount:qualityProfiles[quality].splats,lodRenderScale:qualityProfiles[quality].renderScale,
      // A completed sort/LoD update needs a draw, not another collection.
      // Marking collection dirty here recursively drives work while idle.
      onDirty:()=>{if(state.current?.active)invalidate();}});
    const current={spark,active:true,pending:null as Promise<void>|null,signature:'',dirty:true};state.current=current;scene.add(spark);
    return()=>{
      current.active=false;scene.remove(spark);state.current=null;
      // Spark's synchronous dispose invalidates GPU readback targets. Complete
      // the owned update before releasing those targets and its worker.
      if(current.pending)void current.pending.then(()=>spark.dispose(),()=>spark.dispose());else spark.dispose();
    };
  },[gl,scene,invalidate]);
  useEffect(()=>{const current=state.current;if(current){current.spark.lodSplatCount=qualityProfiles[quality].splats;current.spark.lodRenderScale=qualityProfiles[quality].renderScale;current.dirty=true;invalidate();}},[quality,invalidate]);
  useFrame(()=>{
    const current=state.current;if(!current?.active||current.pending)return;
    const keys=[...camera.position.toArray(),...camera.quaternion.toArray(),(camera as PerspectiveCamera).zoom,...camera.projectionMatrix.elements];
    const splats:string[]=[];scene.traverse(o=>{if(o instanceof SplatMesh&&o.isInitialized)splats.push(o.uuid+':'+o.version+':'+o.mappingVersion+':'+o.numSplats+':'+o.position.toArray()+':'+o.scale.toArray()+':'+o.quaternion.toArray());});
    const signature=keys.join(',')+'|'+splats.join('|');if(signature===current.signature&&!current.dirty)return;current.signature=signature;current.dirty=false;
    if(!splats.length){current.spark.clearSplats();invalidate();return;}
    current.pending=current.spark.update({scene,camera}).then(async()=>{
      // update() awaits sorting but starts LoD asynchronously. Queue a public
      // worker barrier so teardown cannot dispose textures during LoD upload.
      await current.spark.lodWorker?.exclusive(async()=>{});
    }).catch(e=>{if(current.active)status.current('Environment rendering failed: '+e.message,true);}).finally(()=>{current.pending=null;if(current.active)invalidate();});
    updates.set(gl,current.pending);
  },-2);
  return null;
}

/** Color, opacity, covariance and spherical harmonics remain in the original SPZ.
 * MuJoCo collision geometry is intentionally not derived from visible splats. */
function Splats({world,appearance,onStatus,onBounds}:{world?:LibraryWorld;appearance:Appearance;onStatus:(message:string,error?:boolean)=>void;onBounds?:(bounds:Box3)=>void}){
  const {gl,scene,invalidate}=useThree();
  const quality=useRenderQuality(),callbacks=useRef({onStatus,onBounds});callbacks.current={onStatus,onBounds};
  useEffect(()=>{
    let active=true,mesh:SplatMesh|undefined,loading:SplatMesh|undefined;
    const abort=new AbortController();
    const status=(message:string,error=false)=>{if(active)callbacks.current.onStatus(message,error);};
    const released=new WeakSet<SplatMesh>();
    const release=(value:SplatMesh)=>{if(released.has(value))return;released.add(value);scene.remove(value);void (updates.get(gl)??Promise.resolve()).then(()=>value.dispose(),()=>value.dispose());};
    status('Loading environment appearance…');
    const load=async()=>{
     for(const detail of visualStages(quality,appearance.qualities??Object.keys(appearance.urls??{}))){
      const started=performance.now();
      const url=appearance.urls?.[detail]??appearance.url??`${API}/v1/workspace/worlds/${encodeURIComponent(world!.id)}/appearance${appearance.qualities?.length?'?quality='+detail:''}`;
      const response=await fetch(url,{signal:abort.signal,headers:appearance.url||appearance.urls?{}:{'X-Workspace-Token':workspaceToken()}});
      if(!response.ok)throw new Error(`Environment asset could not load (${response.status}).`);
      if(!response.body)throw new Error('Environment response has no readable stream.');
      let receivedBytes=0;
      const stream=response.body.pipeThrough(new TransformStream<Uint8Array,Uint8Array>({transform(chunk,controller){receivedBytes+=chunk.byteLength;controller.enqueue(chunk);}}));
      const next=new SplatMesh({stream,streamLength:Number(response.headers.get('Content-Length'))||undefined,fileType:SplatFileType.SPZ,
        raycastable:false,lod:true,lodScale:qualityProfiles[quality].detail,
        onProgress:event=>status(`Loading ${detail} environment${event.lengthComputable?' · '+Math.round(event.loaded/event.total*100)+'%':''}…`)});loading=next;
      try{await next.initialized;}catch(e){release(next);loading=undefined;throw e;}
      loading=undefined;if(!active){release(next);return;}
      const semantics=appearance.semantics;
      const rawBounds=next.getBoundingBox();
      const legacy=!semantics;
      const scale=semantics?.metric_scale_factor??appearance.visual_scale??3.2/Math.max(.1,rawBounds.max.y-rawBounds.min.y);
      next.scale.setScalar(scale);
      // Marble raw OpenCV -> Three Y-up (180 X) -> runtime Z-up (90 X).
      next.rotation.x=legacy?Math.PI/2:-Math.PI/2;
      next.position.z=legacy?-.8-(appearance.visual_ground_y??rawBounds.min.y)*scale:-.8+semantics.ground_plane_offset;
      next.updateMatrixWorld(true);
      const bounds=next.getBoundingBox().applyMatrix4(next.matrixWorld);
      if(!Number.isFinite(bounds.getSize(new Vector3()).length())){release(next);throw new Error('Environment has invalid bounds.');}
      scene.add(next);if(mesh)release(mesh);mesh=next;
      callbacks.current.onBounds?.(bounds);status('');invalidate();
      window.dispatchEvent(new CustomEvent('vivacity:world-loaded',{detail:{world:world?.id,quality,asset:detail,
        source_splats:next.packedSplats?.numSplats||next.extSplats?.numSplats||null,
        lod_tree_splats:next.packedSplats?.lodSplats?.numSplats||next.extSplats?.lodSplats?.numSplats||null,load_ms:performance.now()-started,lod:true,
        asset_bytes:receivedBytes,lod_budget:qualityProfiles[quality].splats,
        geometry_count:gl.info.memory.geometries,texture_count:gl.info.memory.textures}}));
     }
    };
    load().catch(e=>{if(active&&e.name!=='AbortError')status(mesh?'Higher detail unavailable. The loaded environment remains usable.':e.message||'Environment rendering failed.',true);});
    return()=>{active=false;abort.abort();if(mesh)release(mesh);if(loading)void loading.initialized.then(value=>release(value),()=>{});invalidate();};
  },[gl,scene,invalidate,world?.id,appearance.url,quality]);
  return <SparkEngine onStatus={onStatus} quality={quality}/>;
}

export default function EnvironmentAppearance(props:{world?:LibraryWorld;appearance:Appearance;onStatus:(message:string,error?:boolean)=>void;onBounds?:(bounds:Box3)=>void}){
  return props.appearance.format==='glb'&&props.world?<EmbeddedGltf world={props.world} onStatus={props.onStatus} onBounds={props.onBounds}/>:<Splats {...props}/>;
}
