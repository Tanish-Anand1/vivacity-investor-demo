/** Offline, deterministic 3D film source. The shipped intro is rendered video.
 * Robots use compiled visual meshes from licensed MuJoCo models. Motion is
 * authored kinematic choreography; it is never presented as experiment data.
 */
import {
  ACESFilmicToneMapping,AmbientLight,BoxGeometry,BufferAttribute,BufferGeometry,CanvasTexture,
  Color,DirectionalLight,DoubleSide,Group,Mesh,MeshBasicMaterial,MeshPhysicalMaterial,
  MeshStandardMaterial,PCFSoftShadowMap,PerspectiveCamera,PlaneGeometry,PMREMGenerator,
  Quaternion,Scene,SpotLight,SRGBColorSpace,Vector3,WebGLRenderer,FogExp2,
} from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';

type Pose=[number[],number[]];
type GeometrySpec={body:number;mesh:number|null;type:string;position:number[];quaternion:number[];size:number[];rgba:number[]};
type Manifest={model:string;meshes:{id:number;positions:[number,number];indices:[number,number]}[];geoms:GeometrySpec[];poses:Pose[][]};
type ModelActor={root:Group;parts:{mesh:Mesh;body:number;localPosition:Vector3;localRotation:Quaternion}[];poses:Pose[][]};
const names=['panda','iiwa','xarm7','ur5e','unitree_h1','unitree_g1','berkeley_humanoid'] as const;
const coordinate=(a:number[])=>new Vector3(a[0],a[1],a[2]);
const rotation=(a:number[])=>new Quaternion(a[1],a[2],a[3],a[0]);
const clamp=(v:number,a:number,b:number)=>Math.min(b,Math.max(a,v));
const smooth=(v:number)=>{const x=clamp(v,0,1);return x*x*(3-2*x);};
const ramp=(t:number,a:number,b:number)=>smooth((t-a)/(b-a));
const hold=(t:number,start:number,end:number,fade=.25)=>ramp(t,start-fade,start)* (1-ramp(t,end,end+fade));
const mix=(a:number,b:number,f:number)=>a+(b-a)*f;

const scene=new Scene();scene.background=new Color('#040807');scene.fog=new FogExp2('#060b09',.035);
const camera=new PerspectiveCamera(43,innerWidth/innerHeight,.035,80);camera.up.set(0,0,1);
const renderer=new WebGLRenderer({antialias:true,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setSize(innerWidth,innerHeight);renderer.setPixelRatio(1);
renderer.outputColorSpace=SRGBColorSpace;renderer.shadowMap.enabled=true;renderer.shadowMap.type=PCFSoftShadowMap;
renderer.toneMapping=ACESFilmicToneMapping;renderer.toneMappingExposure=1.2;document.body.append(renderer.domElement);
const pmrem=new PMREMGenerator(renderer);scene.environment=pmrem.fromScene(new RoomEnvironment(),.04).texture;
const ambient=new AmbientLight('#d8ded5',.19);scene.add(ambient);
const mainKey=new DirectionalLight('#f0eadb',1.65);mainKey.position.set(-4,-4,8);mainKey.castShadow=true;
mainKey.shadow.mapSize.set(2048,2048);mainKey.shadow.camera.left=-15;mainKey.shadow.camera.right=15;
mainKey.shadow.camera.top=10;mainKey.shadow.camera.bottom=-10;mainKey.shadow.bias=-.0003;scene.add(mainKey);
const rim=new DirectionalLight('#bfd8d2',1.75);rim.position.set(7,3,5);scene.add(rim);
const humKey=new DirectionalLight('#e5d8c3',1.3);humKey.position.set(4.8,-3.2,4);scene.add(humKey);

const iron=new MeshStandardMaterial({color:'#171e1b',metalness:.54,roughness:.42});
const blackMetal=new MeshStandardMaterial({color:'#09110e',metalness:.68,roughness:.3});
const warmMetal=new MeshStandardMaterial({color:'#a98553',metalness:.76,roughness:.28});
const concrete=new MeshStandardMaterial({color:'#0b110e',metalness:.15,roughness:.87});
const floor=new Mesh(new BoxGeometry(19,7,.18),concrete);floor.position.set(2.2,0,-.16);floor.receiveShadow=true;scene.add(floor);
const wallMaterial=new MeshStandardMaterial({color:'#0c1511',metalness:.34,roughness:.68});
for(let x=-6.2;x<10.1;x+=1.65){
 const panel=new Mesh(new BoxGeometry(1.63,.07,4.9),wallMaterial);panel.position.set(x,3.1,2.38);panel.receiveShadow=true;scene.add(panel);
 const joint=new Mesh(new BoxGeometry(.012,.084,4.9),iron);joint.position.set(x+.81,3.055,2.38);scene.add(joint);
}
for(let x=-6;x<=10;x+=1.2){
 const seam=new Mesh(new BoxGeometry(.006,7,.002),iron);seam.position.set(x,0,-.065);scene.add(seam);
}
for(const y of [-2.65,2.65]){
 const rail=new Mesh(new BoxGeometry(18,.012,.012),warmMetal);rail.position.set(2.2,y,.015);scene.add(rail);
}
const conveyor=new Group();scene.add(conveyor);
const belt=new Mesh(new BoxGeometry(9.1,.46,.045),blackMetal);belt.position.set(-.35,0,.68);belt.receiveShadow=true;conveyor.add(belt);
for(let i=0;i<67;i++){
 const rib=new Mesh(new BoxGeometry(.009,.43,.006),iron);rib.position.set(-4.7+i*.135,0,.706);conveyor.add(rib);
}
for(const y of [-.27,.27]){const guard=new Mesh(new BoxGeometry(9.1,.018,.045),warmMetal);guard.position.set(-.35,y,.73);conveyor.add(guard);}
for(const x of [-4.2,-1.3,1.5,3.2])for(const y of [-.19,.19]){
 const leg=new Mesh(new BoxGeometry(.045,.045,.66),iron);leg.position.set(x,y,.25);leg.castShadow=true;conveyor.add(leg);
}
const stagePositions:{[key:string]:[number,number,number,number,number]}={
 panda:[-3.95,-1.47,.48,.1,1],
 iiwa:[-1.7,1.48,.52,Math.PI,1.05],
 xarm7:[.4,-1.45,.47,0,1],
 ur5e:[2.05,1.52,.5,Math.PI,1.03],
 unitree_h1:[4.65,1.05,0,-.2,1],
 unitree_g1:[5.95,1.2,0,.16,1],
 berkeley_humanoid:[7.0,.68,0,-.15,1],
};
for(const key of ['panda','iiwa','xarm7','ur5e']){
 const [x,y,z]=stagePositions[key];const platform=new Mesh(new BoxGeometry(.77,.77,z),iron);
 platform.position.set(x,y,z/2);platform.castShadow=true;platform.receiveShadow=true;scene.add(platform);
 const lip=new Mesh(new BoxGeometry(.8,.8,.035),warmMetal);lip.position.set(x,y,z+.016);scene.add(lip);
}
for(const x of [-3.8,-1.4,.65,2.3,4.9,6.3]){
 const spot=new SpotLight(x<3?'#e3c89b':'#c7dbd4',x<3?23:30,6,Math.PI/5,.65,1.4);
 spot.position.set(x,-1.35,4.8);spot.target.position.set(x,.5,.4);scene.add(spot,spot.target);
}
for(const x of [4.65,5.95,7.0]){
 const podium=new Mesh(new BoxGeometry(.9,.85,.065),iron);podium.position.set(x,1.02,-.025);podium.castShadow=true;podium.receiveShadow=true;scene.add(podium);
 const edge=new Mesh(new BoxGeometry(.94,.89,.012),warmMetal);edge.position.set(x,1.02,-.055);scene.add(edge);
}

const chrome=new MeshPhysicalMaterial({color:'#f1e6d6',metalness:.88,roughness:.09,clearcoat:1,clearcoatRoughness:.05});
const parcel=new RoundedBoxGeometry(.31,.31,.31,5,.024);
const object=new Mesh(parcel,chrome);object.castShadow=true;scene.add(object);
const branches=[-1,0,1].map((_,i)=>{
 const material=new MeshPhysicalMaterial({color:i===0?'#adbdac':i===1?'#e5cfac':'#9caeaa',metalness:.82,roughness:.17,transparent:true,opacity:0});
 const mesh=new Mesh(parcel,material);mesh.castShadow=true;scene.add(mesh);return mesh;
});
for(const offset of [-.52,0,.52]){
 const track=new Mesh(new BoxGeometry(2.15,.014,.014),warmMetal);track.position.set(5.75,offset,.71);scene.add(track);
}
const titleCanvas=document.createElement('canvas');titleCanvas.width=2048;titleCanvas.height=1024;
const titleContext=titleCanvas.getContext('2d')!;
const titleTexture=new CanvasTexture(titleCanvas);titleTexture.colorSpace=SRGBColorSpace;
const titlePlane=new Mesh(new PlaneGeometry(5.6,2.8),new MeshBasicMaterial({map:titleTexture,transparent:true,side:DoubleSide,depthWrite:false,opacity:0}));
titlePlane.rotation.x=Math.PI/2;titlePlane.position.set(7.25,1.68,1.65);scene.add(titlePlane);
function drawWordmark(){
 titleContext.clearRect(0,0,2048,1024);
 titleContext.fillStyle='#f4f1e8';
 titleContext.textBaseline='top';titleContext.font='700 306px "Instrument Sans", Arial, sans-serif';
 titleContext.fillText('ISABELLA',32,130);titleContext.fillText('LABS',32,425);
 titleContext.fillStyle='#d5ac71';titleContext.font='700 48px Manrope, Arial, sans-serif';
 titleContext.fillText('BY VIVACITY',42,804);titleTexture.needsUpdate=true;
}
document.fonts.ready.then(drawWordmark);drawWordmark();

async function loadModel(name:string):Promise<ModelActor>{
 const prefix='/cinematic/generated/';
 const [manifestResponse,binaryResponse]=await Promise.all([fetch(`${prefix}${name}.json`),fetch(`${prefix}${name}.bin`)]);
 if(!manifestResponse.ok||!binaryResponse.ok)throw new Error(`Missing authored asset ${name}`);
 const manifest=await manifestResponse.json() as Manifest;
 const binary=await binaryResponse.arrayBuffer();const geometry=new Map<number,BufferGeometry>();
 for(const spec of manifest.meshes){
  const g=new BufferGeometry();
  g.setAttribute('position',new BufferAttribute(new Float32Array(binary,spec.positions[0],spec.positions[1]),3));
  g.setIndex(new BufferAttribute(new Uint32Array(binary,spec.indices[0],spec.indices[1]),1));
  g.computeVertexNormals();geometry.set(spec.id,g);
 }
 const root=new Group();const [x,y,z,angle,scale]=stagePositions[name];root.position.set(x,y,z);root.rotation.z=angle;root.scale.setScalar(scale);scene.add(root);
 const parts:ModelActor['parts']=[];
 for(const geom of manifest.geoms){
  if(geom.mesh===null)continue;
  const shape=geometry.get(geom.mesh);if(!shape)continue;
  const [r,g,b,a]=geom.rgba;
  const color=new Color().setRGB(r,g,b,SRGBColorSpace);
  if(name.includes('humanoid')||name.includes('unitree')){
   color.r=Math.min(1,color.r*1.35+.12);color.g=Math.min(1,color.g*1.35+.13);color.b=Math.min(1,color.b*1.35+.13);
  }
  const material=new MeshPhysicalMaterial({color,metalness:name==='panda'?.48:.35,roughness:.35,clearcoat:.28,transparent:a<.999,opacity:a});
  const mesh=new Mesh(shape,material);mesh.castShadow=true;mesh.receiveShadow=true;root.add(mesh);
  parts.push({mesh,body:geom.body,localPosition:coordinate(geom.position),localRotation:rotation(geom.quaternion)});
 }
 return {root,parts,poses:manifest.poses};
}
const actors=await Promise.all(names.map(loadModel));
const actorByName=new Map(names.map((name,i)=>[name,actors[i]]));
function updateActor(actor:ModelActor,phase:number){
 const index=clamp(phase,0,1)*12;const low=Math.floor(index),high=Math.min(12,low+1),weight=index-low;
 const first=actor.poses[low],second=actor.poses[high];
 for(const part of actor.parts){
  const [aPosition,aQuaternion]=first[part.body],[bPosition,bQuaternion]=second[part.body];
  const q=rotation(aQuaternion).slerp(rotation(bQuaternion),weight);
  part.mesh.position.copy(coordinate(aPosition).lerp(coordinate(bPosition),weight)).add(part.localPosition.clone().applyQuaternion(q));
  part.mesh.quaternion.copy(q.multiply(part.localRotation));
 }
}

type CameraKey={t:number;position:[number,number,number];target:[number,number,number]};
const shots:CameraKey[]=[
 {t:0,position:[-4.05,-1.63,1.14],target:[-3.77,-1.34,1.0]},
 {t:.7,position:[-4.35,-1.91,1.5],target:[-3.53,-1.11,1.05]},
 {t:1.2,position:[-4.26,-3.1,2.12],target:[-2.15,.0,1.0]},
 {t:2.0,position:[-.9,-2.48,1.85],target:[.4,.0,1.05]},
 {t:2.6,position:[2.44,-1.62,1.49],target:[3.42,.0,1.01]},
 {t:3.1,position:[3.37,-.42,1.08],target:[4.15,.55,1.08]},
 {t:3.55,position:[4.5,-1.35,1.42],target:[5.1,1.0,1.2]},
 {t:4.1,position:[5.12,-1.52,1.5],target:[5.68,1.0,1.03]},
 {t:5.55,position:[6.0,-1.73,1.6],target:[5.95,1.02,1.03]},
 {t:6.25,position:[6.55,-2.23,1.72],target:[7.05,1.25,1.45]},
 {t:7.5,position:[7.42,-2.96,2.08],target:[7.25,1.64,1.62]},
];
function cameraPoint(t:number,kind:'position'|'target'){
 const i=Math.max(0,shots.findIndex(shot=>shot.t>=t)-1);const current=shots[Math.min(i,shots.length-2)];
 const next=shots[Math.min(i+1,shots.length-1)];const u=clamp((t-current.t)/(next.t-current.t),0,1);
 const previous=shots[Math.max(0,i-1)],following=shots[Math.min(shots.length-1,i+2)];
 const p0=coordinate(current[kind]),p1=coordinate(next[kind]);
 const m0=coordinate(next[kind]).sub(coordinate(previous[kind])).multiplyScalar((next.t-current.t)/(next.t-previous.t));
 const m1=coordinate(following[kind]).sub(coordinate(current[kind])).multiplyScalar((next.t-current.t)/(following.t-current.t));
 return p0.multiplyScalar(2*u*u*u-3*u*u+1).add(m0.multiplyScalar(u*u*u-2*u*u+u))
  .add(p1.multiplyScalar(-2*u*u*u+3*u*u)).add(m1.multiplyScalar(u*u*u-u*u));
}
function objectPoint(t:number){
 if(t<2.6)return new Vector3(mix(-3.65,3.28,smooth(t/2.6)),0,.98+.12*Math.sin(t*7));
 if(t<4.1)return new Vector3(mix(3.28,5.15,smooth((t-2.6)/1.5)),0,1.02+.13*Math.sin(t*3));
 return new Vector3(mix(5.15,6.5,smooth((t-4.1)/2.1)),0,1.05);
}
function setTime(input:number){
 const t=clamp(input,0,7.5);const portrait=innerWidth/innerHeight<.85;
 camera.aspect=innerWidth/innerHeight;camera.fov=portrait?60:43;camera.updateProjectionMatrix();
 const p=cameraPoint(t,'position'),target=cameraPoint(t,'target');
 if(portrait){p.y-=.8;p.z+=.12;}
 camera.position.copy(p);camera.lookAt(target);
 mainKey.intensity=mix(.08,1.65,ramp(t,.05,.9));ambient.intensity=mix(.01,.19,ramp(t,0,.85));
 rim.intensity=mix(.1,1.75,ramp(t,.25,1.2));humKey.intensity=1.3*ramp(t,2.8,3.5);
 for(const [name,actor] of actorByName){
  const phase=name==='panda'?ramp(t,.15,1.4):name==='iiwa'?ramp(t,1.0,2.25):name==='xarm7'?ramp(t,1.42,2.55):name==='ur5e'?ramp(t,1.75,2.75):ramp(t,3.25,5.0);
  updateActor(actor,phase);
 }
 object.position.copy(objectPoint(t));object.rotation.set(t*.7,t*1.15,t*.42);
 (object.material as MeshPhysicalMaterial).opacity=1-ramp(t,4.05,4.28)+ramp(t,5.75,6.05);
 (object.material as MeshPhysicalMaterial).transparent=t>4.04&&t<6.05;
 for(let i=0;i<branches.length;i++){
  const branch=branches[i];const delta=i-1,split=ramp(t,4.1,4.7)*(1-ramp(t,5.48,5.85));
  branch.position.copy(objectPoint(t)).add(new Vector3(0,delta*.52*split,delta*.28*split));
  branch.rotation.set(t*.7+delta*.2,t*1.15,t*.42);
  (branch.material as MeshPhysicalMaterial).opacity=hold(t,4.16,5.73,.12)*.9;
 }
 (titlePlane.material as MeshBasicMaterial).opacity=ramp(t,5.85,6.7);
 // Keep the complete spatial wordmark inside the narrow portrait frustum.
 titlePlane.scale.setScalar(portrait?.4:1);
 titlePlane.position.z=portrait?2.18:1.65;
 const exposure=mix(.6,1.08,ramp(t,0,.9));renderer.toneMappingExposure=exposure;
 renderer.render(scene,camera);
}
function resize(){renderer.setSize(innerWidth,innerHeight);setTime((window as Window&{__cinemaTime?:number}).__cinemaTime??0);}
window.addEventListener('resize',resize);
const control=window as Window&{__cinemaReady?:boolean;__cinemaTime?:number;__setCinemaTime?:(t:number)=>void;__cinemaCanvas?:HTMLCanvasElement};
control.__setCinemaTime=(t:number)=>{control.__cinemaTime=t;setTime(t);};
control.__cinemaCanvas=renderer.domElement;control.__cinemaReady=true;control.__setCinemaTime(0);
