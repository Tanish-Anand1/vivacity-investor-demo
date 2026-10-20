import {useEffect,useMemo,useRef,useState} from 'react';
import {Canvas,useThree} from '@react-three/fiber';
import {OrbitControls,RoundedBox,Line} from '@react-three/drei';
import {Group,Quaternion,Vector3,PCFShadowMap,ACESFilmicToneMapping,ExtrudeGeometry,Shape} from 'three';
import type {OrbitControls as Controls} from 'three-stdlib';
import {loadAssets,GeomMesh,type Assets} from './RobotAssets';
import type {BodyPose,RobotFrame,Vec3} from './domain';
import SceneBoundary from './SceneBoundary';
import layout from './generated/factory_layout.json';

export type FactoryGeometry={name:string;shape:'sphere'|'cylinder'|'box';position:Vec3;quaternion_wxyz:number[];size:Vec3;moving_with_shuttle:boolean};
export type FactoryViewMode='fidelity'|'engineering'|'performance';
export interface FactoryVisualState {time:number;body_transforms:BodyPose[];qpos:number[];phase?:string;measurements?:{contacts:{position_m:number[];force_on_geom2_world_n:number[]}[]};carton_half_size_m?:number;conveyors?:Record<string,{roller_angles_rad?:number[]}>;}
const colors={steel:'#b1b8b7',dark:'#354044',roller:'#88948f',amber:'#dda344',floor:'#a3a39a',carton:'#b18c58'};

function Plate({position,size,color=colors.steel,metal=.7}:{position:Vec3;size:Vec3;color?:string;metal?:number}){
 return <RoundedBox args={size} radius={Math.min(.009,...size.map(v=>v/5))} smoothness={2} position={position} castShadow receiveShadow><meshStandardMaterial color={color} metalness={metal} roughness={metal?.35:.8}/></RoundedBox>;
}
function Tube({a,b,r=.009,color=colors.dark}:{a:Vec3;b:Vec3;r?:number;color?:string}){
 const d=new Vector3(...b).sub(new Vector3(...a));const q=new Quaternion().setFromUnitVectors(new Vector3(0,1,0),d.clone().normalize());
 return <mesh position={new Vector3(...a).add(new Vector3(...b)).multiplyScalar(.5)} quaternion={q} castShadow><cylinderGeometry args={[r,r,d.length(),12]}/><meshStandardMaterial color={color} metalness={.7} roughness={.4}/></mesh>;
}
function Profile({position,length,rotation=[0,0,0]}:{position:Vec3;length:number;rotation?:Vec3}){
 const g=useMemo(()=>{const s=new Shape();const p=[[-.02,-.02],[-.006,-.02],[-.006,-.012],[.006,-.012],[.006,-.02],[.02,-.02],[.02,.02],[.006,.02],[.006,.012],[-.006,.012],[-.006,.02],[-.02,.02]];p.forEach(([x,y],i)=>i?s.lineTo(x,y):s.moveTo(x,y));s.closePath();return new ExtrudeGeometry(s,{depth:length,bevelEnabled:false});},[length]);
 useEffect(()=>()=>g.dispose(),[g]);return <mesh geometry={g} position={position} rotation={rotation} castShadow><meshStandardMaterial color={colors.steel} metalness={.82} roughness={.31}/></mesh>;
}

export function RollerLine({x,start_y,end_y,detail=true,angles}:{x:number;start_y:number;end_y:number;detail?:boolean;angles?:number[]}){
 const count=Math.round((end_y-start_y)/layout.roller_spacing)+1;
 return <group>
  {Array.from({length:count},(_,i)=><group key={i} position={[x,start_y+i*layout.roller_spacing,-layout.roller_radius]} rotation={[angles?.[i]??0,0,0]}>
   <mesh rotation={[0,0,Math.PI/2]} castShadow receiveShadow><cylinderGeometry args={[layout.roller_radius,layout.roller_radius,layout.roller_width,detail?20:8]}/><meshStandardMaterial color={colors.roller} metalness={.85} roughness={.25}/></mesh>
   {detail&&[-1,1].map(sign=><mesh key={sign} position={[sign*.098,0,0]} rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[.009,.009,.018,12]}/><meshStandardMaterial color={colors.dark} metalness={.5} roughness={.45}/></mesh>)}
  </group>)}
  {[-1,1].map(side=><group key={side}>
   <Plate position={[x+side*.112,(start_y+end_y)/2,-.04]} size={[.023,end_y-start_y+.09,.11]} color={colors.dark}/>
   {detail&&Array.from({length:Math.max(2,Math.floor((end_y-start_y)/.2))},(_,i)=><mesh key={i} position={[x+side*.125,start_y+i*.2,-.02]} rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[.004,.004,.003,6]}/><meshStandardMaterial color="#cad0c9" metalness={.95} roughness={.25}/></mesh>)}
  </group>)}
  {[start_y+.05,end_y-.05].map((y,i)=><group key={i}>
   {[-1,1].map(side=><group key={side}><Profile position={[x+side*.107,y,-.75]} length={.65}/><mesh position={[x+side*.107,y,-.77]}><cylinderGeometry args={[.036,.034,.025,16]}/><meshStandardMaterial color="#262f30" roughness={.9}/></mesh></group>)}
   <Plate position={[x,y,-.57]} size={[.23,.03,.035]} color={colors.steel}/>
  </group>)}
  {detail&&<group position={[x+.16,start_y+.12,-.08]}><mesh rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[.039,.039,.11,24]}/><meshStandardMaterial color="#617678" metalness={.6} roughness={.4}/></mesh>{[-.04,-.02,0,.02,.04].map(z=><mesh key={z} position={[z,0,0]} rotation={[0,0,Math.PI/2]}><torusGeometry args={[.04,.002,5,24]}/><meshStandardMaterial color="#233639"/></mesh>)}</group>}
 </group>;
}

function Bin({x,label}:{x:number;label:string}){
 return <group position={[x,1.53,-.24]}>
  <Plate position={[0,0,-.14]} size={[.32,.4,.025]} color="#616f68"/>
  {[-1,1].map(v=><group key={v}><Plate position={[v*.16,0,0]} size={[.018,.4,.29]} color="#7a8d83"/><Plate position={[0,v*.2,0]} size={[.32,.018,.29]} color="#7a8d83"/></group>)}
  <Plate position={[0,-.211,.025]} size={[.14,.005,.07]} color={label==='A'?'#d2b26c':'#b9c6be'} metal={0}/>
  {[-1,1].flatMap(x=>[-1,1].map(y=><mesh key={x+':'+y} position={[x*.13,y*.16,-.19]} rotation={[Math.PI/2,0,0]}><cylinderGeometry args={[.028,.028,.016,16]}/><meshStandardMaterial color="#232b2c"/></mesh>))}
 </group>;
}
function Guarding(){
 return <group>{[[-.65,-1.55,1.65],[1.25,.8,1.65]].map(([x,start,end])=><group key={x}>
  {[start,(start+end)/2,end].map(y=><Profile key={y} position={[x,y,-.8]} length={1.5}/>)}
  {[-.6,.55].map(z=><Tube key={z} a={[x,start,z]} b={[x,end,z]} r={.014} color="#c8a653"/>)}
  <mesh position={[x,(start+end)/2,-.1]} rotation={[0,Math.PI/2,0]}><planeGeometry args={[1.2,end-start,12,Math.ceil((end-start)*10)]}/><meshStandardMaterial color="#596563" wireframe transparent opacity={.22}/></mesh>
 </group>)}</group>;
}
function Room(){
 return <group>
  <mesh position={[0,0,-.804]} receiveShadow><planeGeometry args={[40,40]}/><meshStandardMaterial color={colors.floor} roughness={.83} metalness={.12}/></mesh>
  {[-2,-1,0,1,2,3].map(x=><mesh key={x} position={[x,0,-.802]}><planeGeometry args={[.002,12]}/><meshBasicMaterial color="#838b83"/></mesh>)}
  {[-1.65,1.8].map(y=><mesh key={y} position={[.3,y,-.801]}><planeGeometry args={[2.5,.025]}/><meshStandardMaterial color="#cfb26c" roughness={.8}/></mesh>)}
  <Plate position={[0,4,1.2]} size={[12,.08,4]} color="#a1aaa6" metal={.15}/>
  {Array.from({length:13},(_,i)=><Plate key={i} position={[-6+i,3.945,1.2]} size={[.028,.035,4]} color="#818b88"/>)}
  {[-3,0,3].map(x=><group key={x}><Profile position={[x,3.7,-.8]} length={4.2}/><Plate position={[x,3.65,2.8]} size={[.8,.015,.36]} color="#cfd5cc" metal={0}/></group>)}
  {[-1.5,1.5].map(x=><group key={x}><Plate position={[x,.2,2.4]} size={[.13,2.3,.025]} color="#f0eee1"/><rectAreaLight position={[x,.2,2.35]} rotation={[Math.PI,0,0]} intensity={5} width={.13} height={2.3} color="#f2ecde"/></group>)}
  <group position={[-.62,-1.1,-.8]}><Profile position={[0,0,0]} length={.9}/><group rotation={[Math.PI/12,0,0]}><Plate position={[0,-.015,1.04]} size={[.3,.065,.21]} color="#273336"/><Plate position={[0,-.052,1.055]} size={[.25,.004,.13]} color="#7d9a99" metal={0}/></group><Plate position={[0,-.15,.84]} size={[.32,.24,.025]} color="#b6c0b9"/></group>
 </group>;
}

export function FactoryRobot({assets,frame,engineering=false}:{assets:Assets;frame:FactoryVisualState;engineering?:boolean}){
 const poses=new Map(frame.body_transforms.map(p=>[p.name,p]));
 return <group dispose={null}>{assets.manifest.bodies.filter(b=>b.name.startsWith('link')||['hand','left_finger','right_finger'].includes(b.name)).map(b=>{const p=poses.get(b.name);if(!p)return null;return <group key={b.name} position={p.position} quaternion={new Quaternion(p.quaternion_wxyz[1],p.quaternion_wxyz[2],p.quaternion_wxyz[3],p.quaternion_wxyz[0])}>
  {assets.manifest.geoms.filter(g=>g.body_id===b.id&&(engineering?g.group===3:g.group===2)).map(g=><GeomMesh key={g.id} geom={g} assets={assets} config={{collision_overlay:engineering}}/>)}
  {engineering&&<axesHelper args={[.07]}/>}
 </group>;})}</group>;
}
function Camera({command}:{command:{name:string;seq:number}}){
 const ref=useRef<Controls>(null),{camera,invalidate,gl}=useThree();
 useEffect(()=>{const c=ref.current;if(!c)return;const reset=()=>{camera.position.set(...(command.name==='top'?[.38,-.08,3.5]:command.name==='station'?[1.65,-1.45,.8]:[2.6,-3.3,2.05]) as Vec3);c.target.set(.3,.08,-.12);c.update();invalidate();};reset();const el=gl.domElement;el.tabIndex=0;el.setAttribute('aria-label','Factory view. Arrow keys orbit, plus and minus zoom, R resets.');const key=(e:KeyboardEvent)=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','r','R'].includes(e.key))return;e.preventDefault();if(e.key.toLowerCase()==='r')return reset();if(e.key.includes('Arrow')){c.setAzimuthalAngle(c.getAzimuthalAngle()+(e.key==='ArrowLeft'?.12:e.key==='ArrowRight'?-.12:0));c.setPolarAngle(Math.max(.05,Math.min(1.53,c.getPolarAngle()+(e.key==='ArrowUp'?-.1:e.key==='ArrowDown'?.1:0))));}else camera.position.sub(c.target).multiplyScalar(e.key==='-'?1.1:.9).add(c.target);c.update();invalidate();};el.addEventListener('keydown',key);return()=>el.removeEventListener('keydown',key);},[camera,command,gl,invalidate]);
 return <OrbitControls ref={ref} makeDefault enableDamping={false} minDistance={.6} maxDistance={9} maxPolarAngle={Math.PI*.49}/>;
}
function Refresh({revision}:{revision:unknown}){const invalidate=useThree(s=>s.invalidate);useEffect(()=>invalidate(),[revision,invalidate]);return null;}

export default function FactoryView({frame,mode='fidelity',status='idle',geometry=[],trajectory=[],onVisualReady,onVisualError}:{frame:FactoryVisualState|null;mode?:FactoryViewMode;status?:string;geometry?:FactoryGeometry[];trajectory?:Vec3[];onVisualReady?:()=>void;onVisualError?:(message:string)=>void}){
 const [assets,setAssets]=useState<Assets|null>(null),[error,setError]=useState<string|null>(null),[camera,setCamera]=useState({name:'overview',seq:0});
 const [sceneCreated,setSceneCreated]=useState(false);
 useEffect(()=>{if(error)onVisualError?.(error);},[error,onVisualError]);
 useEffect(()=>{if(!assets||!sceneCreated||!onVisualReady)return;let second=0;const first=requestAnimationFrame(()=>{second=requestAnimationFrame(onVisualReady);});return()=>{cancelAnimationFrame(first);cancelAnimationFrame(second);};},[assets,sceneCreated,onVisualReady]);
 useEffect(()=>{let active=true,attempt=0,timer:ReturnType<typeof setTimeout>;
  function load(){loadAssets().then(value=>{if(active){setAssets(value);setError(null);}}).catch(error=>{if(!active)return;if(++attempt<3)timer=setTimeout(load,750*attempt);else setError(String(error));});}
  load();return()=>{active=false;clearTimeout(timer);};
 },[]);
 const detailed=mode==='fidelity';
 const poses=new Map(frame?.body_transforms.map(p=>[p.name,p])??[]);
 const cartons=[...poses.values()].filter(p=>p.name==='target'||/^carton_\d+$/.test(p.name));
 const rollerAngles=(prefix:string)=>frame?.conveyors?.[prefix.replace('_roller_','')]?.roller_angles_rad;
 return <section className="factory-scene" aria-label="Factory simulation">
  <div className="factory-canvas"><SceneBoundary><Canvas frameloop="demand" shadows={detailed?{type:PCFShadowMap}:false} dpr={detailed?1.5:1} camera={{position:[2.6,-3.3,2.05],fov:42,near:.01,far:80}} gl={{antialias:detailed,toneMapping:ACESFilmicToneMapping}} onCreated={({camera,gl})=>{camera.up.set(0,0,1);gl.setClearColor(detailed?'#a5aca5':'#1a2328');gl.toneMappingExposure=1.05;setSceneCreated(true);}}>
   <hemisphereLight args={['#f5f3e9','#6d776c',2]}/><directionalLight position={[1.5,-2,4]} intensity={4} castShadow={detailed} shadow-mapSize={[2048,2048]} shadow-camera-left={-3} shadow-camera-right={3} shadow-camera-top={3} shadow-camera-bottom={-3} shadow-normalBias={.004}/><directionalLight position={[-2,2,2]} intensity={1.5}/>
   {detailed?<><Room/><Guarding/></>:<mesh position={[0,0,-.8]}><planeGeometry args={[8,8]}/><meshStandardMaterial color="#303c41"/></mesh>}
   {mode!=='engineering'&&<><Plate position={[0,0,-.4]} size={[.32,.32,.8]} color={colors.dark}/><Plate position={[0,0,-.02]} size={[.37,.37,.04]}/>
   <RollerLine {...layout.infeed} detail={detailed} angles={rollerAngles('infeed_roller_')}/><RollerLine {...layout.transfer} detail={detailed} angles={rollerAngles('transfer_roller_')}/>
   <group position={[poses.get('shuttle')?.position[0]??0,0,0]}><RollerLine {...layout.shuttle} detail={detailed} angles={rollerAngles('shuttle_roller_')}/></group>
   {layout.lanes.map(l=><group key={l.id}><RollerLine {...l} detail={detailed} angles={rollerAngles('lane_'+l.id+'_roller_')}/><Bin x={l.x} label={l.id}/></group>)}
   </>}
   {mode==='engineering'&&geometry.map(g=><group key={g.name} position={[g.position[0]+(g.moving_with_shuttle?(poses.get('shuttle')?.position[0]??0):0),g.position[1],g.position[2]]} quaternion={new Quaternion(g.quaternion_wxyz[1],g.quaternion_wxyz[2],g.quaternion_wxyz[3],g.quaternion_wxyz[0])}><mesh rotation={g.shape==='cylinder'?[Math.PI/2,0,0]:[0,0,0]}>{g.shape==='box'?<boxGeometry args={[2*g.size[0],2*g.size[1],2*g.size[2]]}/>:g.shape==='cylinder'?<cylinderGeometry args={[g.size[0],g.size[0],2*g.size[1],12]}/>:<sphereGeometry args={[g.size[0],12,8]}/>}<meshStandardMaterial color="#78978e" wireframe/></mesh></group>)}
   {mode==='engineering'&&frame?.measurements?.contacts.map((c,i)=>{const force=new Vector3(...c.force_on_geom2_world_n as Vec3),length=force.length();return <group key={i}><mesh position={c.position_m as Vec3}><sphereGeometry args={[.003,6,6]}/><meshBasicMaterial color="#f3b158"/></mesh>{length>0&&<arrowHelper args={[force.normalize(),new Vector3(...c.position_m as Vec3),Math.min(.15,length*.002),0xf3b158,.008,.005]}/>}</group>;})}
   {frame&&assets&&<FactoryRobot assets={assets} frame={frame} engineering={mode==='engineering'}/>}
   {cartons.map(cube=><group key={cube.name} scale={(frame?.carton_half_size_m??.025)/.025} position={cube.position} quaternion={new Quaternion(cube.quaternion_wxyz[1],cube.quaternion_wxyz[2],cube.quaternion_wxyz[3],cube.quaternion_wxyz[0])}><Plate position={[0,0,0]} size={[.05,.05,.05]} color={colors.carton} metal={0}/>{detailed&&<><Plate position={[0,0,.02515]} size={[.012,.0502,.0004]} color="#ccba87" metal={0}/><Plate position={[.0251,0,0]} size={[.0004,.024,.019]} color="#ede6cf" metal={0}/></>}</group>)}
   {mode==='engineering'&&trajectory.length>1&&<Line points={trajectory} color="#a6cec0" lineWidth={1.5}/>}
   <Camera command={camera}/><Refresh revision={[frame,mode,status]}/>
  </Canvas></SceneBoundary>{error&&<p role="alert">{error}</p>}</div>
  <div className="factory-view-tools"><span>Sorting cell 01 <small>· Panda / Z-up / metres</small></span>{mode==='engineering'&&<small>Collision surfaces · body axes · force on geom 2 (2 mm/N, capped at 0.15 m)</small>}<div>{[['overview','Overview'],['station','Robot station'],['top','Plan']].map(([id,label])=><button key={id} aria-pressed={camera.name===id} onClick={()=>setCamera(c=>({name:id,seq:c.seq+1}))}>{label}</button>)}</div></div>
 </section>;
}
