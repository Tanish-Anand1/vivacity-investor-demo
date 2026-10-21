/** THE IMPOSSIBLE SHOT — deterministic, offline film source.
 *
 * Every object, camera, light and architectural movement is derived from the
 * authoritative 0–7.5 s clock. Robot meshes come from licensed MuJoCo
 * Menagerie models; their motion is authored cinematography, not experiment
 * evidence. The finished film is encoded for reliable browser playback.
 */
import {
  ACESFilmicToneMapping, AmbientLight, BoxGeometry, BufferAttribute,
  BufferGeometry, CanvasTexture, Color, CylinderGeometry, DirectionalLight,
  DoubleSide, Group, Mesh, MeshBasicMaterial, MeshPhysicalMaterial,
  MeshStandardMaterial, PCFSoftShadowMap, PerspectiveCamera, PlaneGeometry,
  PMREMGenerator, Quaternion, Scene, SpotLight, SRGBColorSpace, TorusGeometry,
  Vector3, WebGLRenderer,
} from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';

type Pose=[number[],number[]];
type GeometrySpec={body:number;mesh:number|null;type:string;position:number[];quaternion:number[];size:number[];rgba:number[]};
type Manifest={model:string;meshes:{id:number;positions:[number,number];indices:[number,number]}[];geoms:GeometrySpec[];poses:Pose[][]};
type ModelActor={root:Group;parts:{mesh:Mesh;body:number;localPosition:Vector3;localRotation:Quaternion}[];poses:Pose[][];baseYaw:number;toolBody:number};
type Key={t:number;p:[number,number,number]};
const DURATION=7.5;
const clamp=(n:number,a=0,b=1)=>Math.min(b,Math.max(a,n));
const smooth=(n:number)=>{const x=clamp(n);return x*x*(3-2*x);};
const ramp=(t:number,a:number,b:number)=>smooth((t-a)/(b-a));
const mix=(a:number,b:number,k:number)=>a+(b-a)*k;
const vec=(p:number[])=>new Vector3(p[0],p[1],p[2]);
const quat=(p:number[])=>new Quaternion(p[1],p[2],p[3],p[0]);
const Z=new Vector3(0,0,1);

const scene=new Scene();scene.background=new Color('#030504');
const camera=new PerspectiveCamera(39,innerWidth/innerHeight,.025,80);camera.up.copy(Z);
const renderer=new WebGLRenderer({antialias:true,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setSize(innerWidth,innerHeight);renderer.setPixelRatio(1);
renderer.outputColorSpace=SRGBColorSpace;renderer.toneMapping=ACESFilmicToneMapping;
renderer.toneMappingExposure=1.12;renderer.shadowMap.enabled=true;renderer.shadowMap.type=PCFSoftShadowMap;
document.body.append(renderer.domElement);
const pmrem=new PMREMGenerator(renderer);scene.environment=pmrem.fromScene(new RoomEnvironment(),.04).texture;
const ambient=new AmbientLight('#d7dcd5',.13);scene.add(ambient);
const keyLight=new DirectionalLight('#f4eee3',2.15);keyLight.position.set(-2.9,-3.8,8.2);
keyLight.castShadow=true;keyLight.shadow.mapSize.set(1536,1536);keyLight.shadow.camera.left=-12;
keyLight.shadow.camera.right=12;keyLight.shadow.camera.top=9;keyLight.shadow.camera.bottom=-9;
keyLight.shadow.bias=-.00025;scene.add(keyLight);
const rim=new DirectionalLight('#b7c9c5',1.45);rim.position.set(6,3.8,5);scene.add(rim);
for(const [x,y,z,power] of [[-2.4,-1.2,4.7,28],[.3,-.8,4.8,25],[3.7,-1.3,4.5,30],[6.8,-.9,5.2,35]]){
 const spot=new SpotLight('#e7dfd1',power,7,Math.PI/5,.55,1.4);
 spot.position.set(x,y,z);spot.target.position.set(x,.5,.85);scene.add(spot,spot.target);
}

const graphite=new MeshStandardMaterial({color:'#151b19',metalness:.49,roughness:.48});
const darkMetal=new MeshStandardMaterial({color:'#0a100f',metalness:.68,roughness:.3});
const titanium=new MeshPhysicalMaterial({color:'#aeb6b0',metalness:.79,roughness:.27,clearcoat:.3});
const edgeMetal=new MeshStandardMaterial({color:'#b9a27e',metalness:.85,roughness:.28});
const architectural=new MeshStandardMaterial({color:'#252d2a',metalness:.44,roughness:.5,side:DoubleSide});
const floorMat=new MeshStandardMaterial({color:'#0b100e',metalness:.17,roughness:.85});
function box(parent:Group|Scene,size:[number,number,number],position:[number,number,number],material:MeshStandardMaterial|MeshPhysicalMaterial|MeshBasicMaterial,shadow=true){
 const item=new Mesh(new BoxGeometry(...size),material);item.position.set(...position);
 item.castShadow=shadow;item.receiveShadow=true;parent.add(item);return item;
}
function cylinder(parent:Group,radius:number,height:number,position:[number,number,number],material:MeshStandardMaterial|MeshPhysicalMaterial,sides=18){
 const item=new Mesh(new CylinderGeometry(radius,radius,height,sides),material);item.rotation.x=Math.PI/2;
 item.position.set(...position);item.castShadow=true;parent.add(item);return item;
}
function rod(parent:Group,thickness:number,material:MeshStandardMaterial|MeshPhysicalMaterial){
 const mesh=new Mesh(new CylinderGeometry(thickness,thickness,1,10),material);mesh.castShadow=true;
 parent.add(mesh);return mesh;
}
function fitRod(mesh:Mesh,a:Vector3,b:Vector3){
 const direction=b.clone().sub(a);mesh.position.copy(a).add(b).multiplyScalar(.5);
 mesh.quaternion.setFromUnitVectors(new Vector3(0,1,0),direction.clone().normalize());mesh.scale.y=direction.length();
}

// A restrained, full-scale industrial room. No conveyor or decorative HUD.
box(scene,[18,8,.16],[2.8,0,-.16],floorMat,false);
for(let i=-4;i<11;i+=1){
 box(scene,[.008,7.9,.002],[i+.3,0,-.074],graphite,false);
}
for(const y of [-2.8,2.8])box(scene,[17,.016,.018],[3.0,y,-.055],edgeMetal,false);
for(const x of [-3.1,-1,1.35]){
 const heavy=x===-1,size=heavy?1.13:.8,y=heavy?.64:-.6;
 box(scene,[size,size,.46],[x,y,.23],graphite);
 box(scene,[size+.05,size+.05,.028],[x,y,.475],titanium);
 box(scene,[size+.1,size+.1,.013],[x,y,.493],edgeMetal,false);
}
box(scene,[.63,.63,.22],[-1,.64,.61],darkMetal);
// The cube's destination is an architectural object, not a conveyor station.
box(scene,[1.12,.95,.62],[3.5,.05,.27],darkMetal);
box(scene,[1.15,.98,.065],[3.5,.05,.61],graphite);
box(scene,[1.19,1.02,.016],[3.5,.05,.653],titanium,false);
for(const x of [3.1,3.9])box(scene,[.018,1.02,.025],[x,.05,.677],darkMetal,false);

const actorPositions:{[key:string]:[number,number,number,number,number]}={
 panda:[-3.1,-.6,.5,.08,1],ur5e:[-1.0,.64,.6,Math.PI,1.31],
 xarm7:[1.55,-.65,.5,.03,1.05],unitree_h1:[6.55,1.5,.02,Math.PI,.9],
};
async function loadModel(name:string):Promise<ModelActor>{
 const prefix='/cinematic/generated/';
 const [manifestResponse,binaryResponse]=await Promise.all([fetch(`${prefix}${name}.json`),fetch(`${prefix}${name}.bin`)]);
 if(!manifestResponse.ok||!binaryResponse.ok)throw Error(`Missing licensed cinematic asset: ${name}`);
 const manifest=await manifestResponse.json() as Manifest;
 const binary=await binaryResponse.arrayBuffer();const geometries=new Map<number,BufferGeometry>();
 for(const spec of manifest.meshes){
  const geometry=new BufferGeometry();
  geometry.setAttribute('position',new BufferAttribute(new Float32Array(binary,spec.positions[0],spec.positions[1]),3));
  geometry.setIndex(new BufferAttribute(new Uint32Array(binary,spec.indices[0],spec.indices[1]),1));
  geometry.computeVertexNormals();geometries.set(spec.id,geometry);
 }
 const root=new Group();const [x,y,z,yaw,scale]=actorPositions[name];
 root.position.set(x,y,z);root.rotation.z=yaw;root.scale.setScalar(scale);scene.add(root);
 const parts:ModelActor['parts']=[];
 for(const geom of manifest.geoms){
  if(geom.mesh===null)continue;const shape=geometries.get(geom.mesh);if(!shape)continue;
  const [r,g,b,a]=geom.rgba;const original=new Color().setRGB(r,g,b,SRGBColorSpace);
  const muted=name==='unitree_h1'?.77:.68;
  const color=new Color().setRGB(mix(.42,original.r,muted),mix(.46,original.g,muted),mix(.44,original.b,muted));
  const material=new MeshPhysicalMaterial({color,metalness:.42,roughness:.37,clearcoat:.32,transparent:a<.999,opacity:a});
  const mesh=new Mesh(shape,material);mesh.castShadow=true;mesh.receiveShadow=true;root.add(mesh);
  parts.push({mesh,body:geom.body,localPosition:vec(geom.position),localRotation:quat(geom.quaternion)});
 }
 return {root,parts,poses:manifest.poses,baseYaw:yaw,toolBody:Math.max(...manifest.geoms.map(g=>g.body))};
}
const [panda,ur5e,xarm7,humanoid]=await Promise.all(['panda','ur5e','xarm7','unitree_h1'].map(loadModel));
humanoid.root.visible=false;
function poseActor(actor:ModelActor,fraction:number){
 const index=clamp(fraction)*12,low=Math.floor(index),high=Math.min(low+1,12),weight=index-low;
 const a=actor.poses[low],b=actor.poses[high];
 for(const part of actor.parts){
  const [pa,qa]=a[part.body],[pb,qb]=b[part.body];const orientation=quat(qa).slerp(quat(qb),weight);
  part.mesh.position.copy(vec(pa).lerp(vec(pb),weight)).add(part.localPosition.clone().applyQuaternion(orientation));
  part.mesh.quaternion.copy(orientation.multiply(part.localRotation));
 }
}
// Purpose-built parallel manipulator: three radial motor casings, articulated
// upper links, paired carbon pushrods, precision bearings and a tool platform.
const delta=new Group();delta.position.set(.35,.05,2.65);scene.add(delta);
cylinder(delta,.57,.18,[0,0,0],graphite,24);
cylinder(delta,.45,.038,[0,0,-.11],titanium,24);
const ring=new Mesh(new TorusGeometry(.49,.028,8,36),edgeMetal);ring.position.z=-.13;delta.add(ring);
const deltaTool=new Group();delta.add(deltaTool);
cylinder(deltaTool,.18,.075,[0,0,0],titanium,16);
cylinder(deltaTool,.115,.09,[0,0,-.075],darkMetal,16);
for(const y of [-.105,.105])box(deltaTool,[.22,.035,.15],[0,y,-.15],titanium);
const deltaArms:{theta:number;upper:Mesh;lowerA:Mesh;lowerB:Mesh;elbow:Mesh}[]=[];
for(let i=0;i<3;i++){
 const theta=i*2*Math.PI/3;const x=Math.cos(theta)*.48,y=Math.sin(theta)*.48;
 cylinder(delta,.13,.22,[x,y,-.095],titanium,16);
 const bolt=cylinder(delta,.042,.245,[x,y,-.095],darkMetal,14);bolt.rotation.z=theta;
 const upper=rod(delta,.052,graphite),lowerA=rod(delta,.018,titanium),lowerB=rod(delta,.018,titanium);
 const elbow=cylinder(delta,.062,.085,[x,y,-.58],edgeMetal,12);
 deltaArms.push({theta,upper,lowerA,lowerB,elbow});
}
function poseDelta(t:number){
 const active=ramp(t,1.47,1.78)*(1-ramp(t,2.12,2.3));
 const reach=active*.19;
 deltaTool.position.set(reach,.02*Math.sin(t*9),-1.16+active*.12);
 for(const arm of deltaArms){
  const c=Math.cos(arm.theta),s=Math.sin(arm.theta);
  const shoulder=new Vector3(.48*c,.48*s,-.17);
  const elbow=new Vector3((.72+.08*active)*c,(.72+.08*active)*s,-.61+.1*active);
  const effector=deltaTool.position.clone().add(new Vector3(.17*c,.17*s,.025));
  fitRod(arm.upper,shoulder,elbow);arm.elbow.position.copy(elbow);
  const tangent=new Vector3(-s,c,0).multiplyScalar(.039);
  fitRod(arm.lowerA,elbow.clone().add(tangent),effector.clone().add(tangent));
  fitRod(arm.lowerB,elbow.clone().sub(tangent),effector.clone().sub(tangent));
 }
}

// The source robot's wrist is extended with a recognisable end-effector on
// models that ship without a gripper mesh. The Panda has its own jaw geometry.
function makeTool(actor:ModelActor){
 const group=new Group();actor.root.add(group);
 box(group,[.17,.12,.065],[0,0,0],darkMetal);
 for(const y of [-.075,.075]){
  box(group,[.11,.031,.17],[.09,y,-.085],titanium);
  box(group,[.065,.024,.044],[.17,y,-.15],graphite);
 }
 return group;
}
const heavyTool=makeTool(ur5e),collaborativeTool=makeTool(xarm7);
function positionTool(actor:ModelActor,tool:Group,fraction:number){
 const index=clamp(fraction)*12,low=Math.floor(index),high=Math.min(12,low+1),mixAmount=index-low;
 const [pa,qa]=actor.poses[low][actor.toolBody],[pb,qb]=actor.poses[high][actor.toolBody];
 tool.position.copy(vec(pa).lerp(vec(pb),mixAmount));tool.quaternion.copy(quat(qa).slerp(quat(qb),mixAmount));
}

const cube=new Group();scene.add(cube);
const cubeCore=new Mesh(new RoundedBoxGeometry(.245,.245,.245,6,.014),
 new MeshPhysicalMaterial({color:'#b9c1bb',metalness:.92,roughness:.18,clearcoat:.65,clearcoatRoughness:.11}));
cubeCore.castShadow=true;cube.add(cubeCore);
for(const sign of [-1,1]){
 box(cube,[.19,.003,.003],[0,sign*.124,0],darkMetal,false);
 box(cube,[.003,.19,.003],[sign*.124,0,0],darkMetal,false);
}
// An engraved inlay gives the cube a persistent orientation during every pass.
box(cube,[.074,.005,.008],[0,-.126,.061],edgeMetal,false);

// Four contact nodes, one continuous cubic path. The cube never disappears or
// reappears at another world coordinate, including during the fracture.
const cubeTrack:Key[]=[
 {t:0,p:[-2.54,-.62,1.08]},{t:.6,p:[-2.51,-.6,1.08]},
 {t:1.1,p:[-2.48,-.39,1.15]},{t:1.43,p:[-.9,.22,1.22]},
 {t:1.68,p:[-.72,.13,1.41]},{t:1.89,p:[.4,.05,1.43]},
 {t:2.0,p:[.54,.04,1.4]},{t:2.1,p:[1.22,-.18,1.3]},
 {t:2.2,p:[2.05,-.48,1.15]},{t:2.27,p:[2.12,-.34,1.13]},
 {t:2.65,p:[2.83,-.31,1.3]},{t:2.97,p:[3.5,.05,1.42]},
 {t:3.12,p:[3.5,.05,1.42]},{t:3.37,p:[3.5,.05,.82]},
 {t:4.12,p:[3.5,.05,.82]},{t:5.1,p:[5.02,.05,1.05]},
 {t:5.72,p:[6.76,-.17,.78]},{t:6.1,p:[7.36,-.42,.31]},
 {t:7.5,p:[7.38,-.9,.28]},
];
function sample(keys:Key[],time:number){
 const t=clamp(time,keys[0].t,keys[keys.length-1].t);
 let i=0;while(i<keys.length-2&&t>keys[i+1].t)i++;
 const current=keys[i],next=keys[i+1],previous=keys[Math.max(0,i-1)],following=keys[Math.min(keys.length-1,i+2)];
 const dt=next.t-current.t,u=(t-current.t)/dt;
 const p0=vec(current.p),p1=vec(next.p);
 const m0=vec(next.p).sub(vec(previous.p)).multiplyScalar(dt/(next.t-previous.t));
 const m1=vec(following.p).sub(vec(current.p)).multiplyScalar(dt/(following.t-current.t));
 return p0.multiplyScalar(2*u*u*u-3*u*u+1).add(m0.multiplyScalar(u*u*u-2*u*u+u))
  .add(p1.multiplyScalar(-2*u*u*u+3*u*u)).add(m1.multiplyScalar(u*u*u-u*u));
}

// The room fractures by translating weighty architectural layers on directed
// rails. The parts reunite into a portal/identity frame rather than exploding.
type Layer={group:Group;base:Vector3;breakBy:Vector3;turn:number;settle:Vector3};
const layers:Layer[]=[];
function slab(size:[number,number,number],base:[number,number,number],breakBy:[number,number,number],turn:number,settle:[number,number,number],trim=false){
 const group=new Group();group.position.set(...base);scene.add(group);
 box(group,size,[0,0,0],architectural);
 if(trim)box(group,[size[0]*.9,.014,.014],[0,-size[1]/2-.006,size[2]/2-.018],edgeMetal,false);
 if(size[2]>3)box(group,[.018,.024,size[2]*.87],[-size[0]/2+.023,-size[1]/2-.016,0],titanium,false);
 layers.push({group,base:vec(base),breakBy:vec(breakBy),turn,settle:vec(settle)});
}
box(scene,[3.22,3.12,.01],[3.5,.05,-.075],darkMetal,false);
for(const [ix,x] of [[-1,2.75],[1,4.25]] as const)for(const [iy,y] of [[-1,-.69],[1,.79]] as const){
 slab([1.42,1.39,.14],[x,y,-.045],[ix*.45,iy*.83,.16+(iy>0?.13:0)],ix*iy*.045,[x+ix*.08,y+iy*.08,-.045],true);
}
for(let i=0;i<6;i++){
 const x=4.15+i*.75;
 slab([.72,5.35,.15],[x,.18,-.085],[i%2?-.36:.44,i%2?1.2:-1.1,(i%3)*.2],(i%2?1:-1)*.075,[x+.18,.18,-.085],true);
}
for(let i=0;i<5;i++){
 const x=4.35+i*.91;
 slab([.86,.2,3.8],[x,2.25,1.9],[i%2?.25:-.2,.63+(i%3)*.18,(i%2?.34:-.22)],(i%2?1:-1)*.09,[x+.15,2.15,1.9]);
}
for(let i=0;i<4;i++){
 const x=4.6+i*1.02;
 slab([.9,2.9,.2],[x,.35,3.7],[i%2?-.15:.16,i%2?-.8:.7,.55+(i%2)*.25],(i%2?-1:1)*.055,[x+.1,.35,3.8]);
}
// Layered alternate environments exist physically behind the moving planes.
const possibilities=new Group();scene.add(possibilities);
box(possibilities,[4.1,.16,3.05],[5.91,3.0,1.84],graphite);
for(const [x,tint] of [[4.75,'#63706b'],[5.9,'#a6aa9e'],[7.05,'#88968d']] as const){
 const shell=new MeshStandardMaterial({color:tint,metalness:.46,roughness:.53});
 box(possibilities,[1.17,.91,.075],[x,1.98,.63],shell);
 box(possibilities,[.89,.64,.023],[x,1.98,.68],darkMetal);
}
// Industrial, humanoid and manipulation silhouettes occupy staggered depths
// of one room. The two small arms reuse the same licensed model meshes.
poseActor(panda,0);poseActor(xarm7,0);
function duplicateActor(source:ModelActor,position:[number,number,number],scale:number,yaw:number):ModelActor{
 const root=source.root.clone(true);root.position.set(...position);root.scale.setScalar(scale);root.rotation.z=yaw;
 possibilities.add(root);
 return {root,poses:source.poses,baseYaw:yaw,toolBody:source.toolBody,
  parts:source.parts.map((part,index)=>({...part,mesh:root.children[index] as Mesh}))};
}
const industrialMini=duplicateActor(panda,[4.75,2,.67],.83,.34);
const alternateMini=duplicateActor(xarm7,[7.05,2,.68],.78,-.56);
humanoid.root.position.set(5.9,2.05,.65);humanoid.root.scale.setScalar(.82);humanoid.root.rotation.z=Math.PI;

const wordmarkCanvas=document.createElement('canvas');wordmarkCanvas.width=2048;wordmarkCanvas.height=1100;
const ctx=wordmarkCanvas.getContext('2d')!;
const wordmarkTexture=new CanvasTexture(wordmarkCanvas);wordmarkTexture.colorSpace=SRGBColorSpace;
function drawWordmark(){
 ctx.clearRect(0,0,2048,1100);
 ctx.fillStyle='#edece4';ctx.textBaseline='middle';
 ctx.font='600 276px "Instrument Sans", Arial, sans-serif';
 ctx.fillText('ISABELLA',56,362);ctx.fillText('LABS',56,666);
 ctx.fillStyle='#c7ad85';ctx.font='700 52px "Instrument Sans", Arial, sans-serif';
 ctx.fillText('BY VIVACITY',70,931);wordmarkTexture.needsUpdate=true;
}
document.fonts.ready.then(drawWordmark);drawWordmark();
const identity=new Group();scene.add(identity);
identity.position.set(7.36,1.67,1.82);
identity.scale.setScalar(.76);
const sign=new Mesh(new PlaneGeometry(5.15,2.77),new MeshBasicMaterial({map:wordmarkTexture,transparent:true,side:DoubleSide,depthWrite:false}));
sign.rotation.x=Math.PI/2;identity.add(sign);
box(identity,[5.42,.09,.055],[0,.27,1.45],edgeMetal,false);
box(identity,[5.42,.09,.055],[0,.27,-1.45],edgeMetal,false);
const leftGate=box(identity,[2.74,.18,2.9],[-1.37,-.16,0],architectural);
const rightGate=box(identity,[2.74,.18,2.9],[1.37,-.16,0],architectural);
for(const gate of [leftGate,rightGate]){
 const rib=new Mesh(new BoxGeometry(.018,.19,2.75),titanium);
 rib.position.x=gate===leftGate?1.34:-1.34;gate.add(rib);
}

const cameraPosition:Key[]=[
 {t:0,p:[-2.68,-1.02,1.17]},{t:.6,p:[-2.75,-1.42,1.36]},
 {t:1.2,p:[-2.0,-2.55,1.92]},{t:1.72,p:[-.53,-2.35,1.79]},
 {t:2.18,p:[1.42,-2.25,1.7]},{t:2.92,p:[2.64,-2.15,1.83]},
 {t:3.46,p:[3.82,-2.42,1.94]},{t:4.11,p:[4.28,-2.29,1.72]},
 {t:5.1,p:[5.83,-2.4,1.84]},{t:5.82,p:[7.02,-2.87,1.94]},
 {t:6.2,p:[7.17,-2.89,1.91]},{t:7.5,p:[7.38,1.86,1.82]},
];
const cameraTarget:Key[]=[
 {t:0,p:[-2.5,-.6,1.08]},{t:.6,p:[-2.5,-.58,1.08]},
 {t:1.2,p:[-1.67,-.13,1.2]},{t:1.72,p:[.12,.03,1.35]},
 {t:2.18,p:[1.82,-.42,1.22]},{t:2.92,p:[3.5,.05,1.35]},
 {t:3.46,p:[3.5,.05,.86]},{t:4.11,p:[4.42,.14,1.76]},
 {t:5.1,p:[5.48,.76,1.83]},{t:5.82,p:[7.36,1.67,1.82]},
 {t:6.2,p:[7.36,1.67,1.82]},{t:7.5,p:[7.38,3.28,1.82]},
];
function setTime(input:number){
 const t=clamp(input,0,DURATION),portrait=innerWidth/innerHeight<.86;
 camera.aspect=innerWidth/innerHeight;
 camera.fov=portrait?mix(52,57,ramp(t,.55,1.3)):mix(32,46,ramp(t,.5,1.35));
 camera.updateProjectionMatrix();
 const position=sample(cameraPosition,t),target=sample(cameraTarget,t);
 if(portrait){
  const pullBack=ramp(t,.5,1.12);
  position.y-=1.3*pullBack;position.x-=.42*ramp(t,1.6,2.08)*(1-ramp(t,3.15,3.6));
  position.z+=.08*pullBack;target.z+=.03;
  const centered=ramp(t,4.92,5.48);
  const followCube=ramp(t,.38,.7)*(1-ramp(t,3.03,3.45));
  target.lerp(sample(cubeTrack,t),followCube);
  target.x-=.55*ramp(t,2.14,2.46)*(1-ramp(t,3.05,3.38));
  target.z-=.23*ramp(t,.63,.96)*(1-ramp(t,2.22,2.8));
  position.x=mix(position.x,7.36,centered);
  position.y=mix(position.y,-4.42,centered*(1-ramp(t,6.4,7.5)));
  target.x=mix(target.x,7.36,centered);
 }
 camera.position.copy(position);camera.lookAt(target);
 keyLight.intensity=mix(.06,2.15,ramp(t,.03,.85));
 ambient.intensity=mix(.015,.13,ramp(t,0,.75));rim.intensity=mix(.06,1.45,ramp(t,.18,1.15));
 const pandaPhase=ramp(t,.23,1.4),heavyPhase=ramp(t,1.18,1.81),collabPhase=ramp(t,1.91,3.04);
 poseActor(panda,pandaPhase);poseActor(ur5e,heavyPhase);poseActor(xarm7,collabPhase);
 poseActor(industrialMini,ramp(t,4.09,5.07));poseActor(alternateMini,ramp(t,4.2,5.03));
 poseActor(humanoid,ramp(t,4.2,5.0));poseDelta(t);
 panda.root.rotation.z=panda.baseYaw+.14*Math.sin(Math.PI*pandaPhase);
 ur5e.root.rotation.z=ur5e.baseYaw-.56*Math.sin(Math.PI*heavyPhase);
 xarm7.root.rotation.z=xarm7.baseYaw+.21*Math.sin(Math.PI*collabPhase);
 positionTool(ur5e,heavyTool,heavyPhase);positionTool(xarm7,collaborativeTool,collabPhase);
 const cubePosition=sample(cubeTrack,t);
 const heavyGrip=ramp(t,1.38,1.5)*(1-ramp(t,1.67,1.82));
 const deltaGrip=ramp(t,1.83,1.9)*(1-ramp(t,1.99,2.06));
 const cobotGrip=ramp(t,2.11,2.28)*(1-ramp(t,2.4,2.58));
 const heavyPoint=heavyTool.localToWorld(new Vector3(.18,0,-.12));
 const deltaPoint=deltaTool.localToWorld(new Vector3(0,0,-.16));
 const cobotPoint=collaborativeTool.localToWorld(new Vector3(.18,0,-.12));
 cubePosition.lerp(heavyPoint,heavyGrip);
 cubePosition.lerp(deltaPoint,deltaGrip);
 cubePosition.lerp(cobotPoint,cobotGrip);
 cube.position.copy(cubePosition);
 (window as Window&{__cinemaCube?:number[];__cinemaPoints?:object}).__cinemaCube=cube.position.toArray();
 (window as Window&{__cinemaPoints?:object}).__cinemaPoints={track:sample(cubeTrack,t).toArray(),heavy:heavyPoint.toArray(),delta:deltaPoint.toArray(),cobot:cobotPoint.toArray(),weights:[heavyGrip,deltaGrip,cobotGrip]};
 cube.rotation.set(.05*Math.sin(t*2),.11*Math.sin(t*3),.16*Math.sin(t*2.2));
 const impact=ramp(t,3.12,3.37);
 if(t>=3.12&&t<=3.43)cube.rotation.x+=impact*.35;
 const fracture=ramp(t,3.34,4.1),rebuild=ramp(t,5.08,6.08);
 for(const layer of layers){
  layer.group.position.copy(layer.base).add(layer.breakBy.clone().multiplyScalar(fracture*(1-rebuild))).lerp(layer.settle,rebuild);
  layer.group.rotation.set(layer.turn*fracture*(1-rebuild),0,layer.turn*.8*fracture*(1-rebuild));
 }
 possibilities.visible=t>=3.98&&t<=5.47;humanoid.root.visible=possibilities.visible;
 identity.visible=t>=5.05;
 identity.scale.setScalar(portrait?.53:.76);
 const reveal=ramp(t,5.16,6.08),open=ramp(t,6.13,7.42);
 leftGate.position.x=-1.37-3.05*reveal-1.7*open;
 rightGate.position.x=1.37+3.05*reveal+1.7*open;
 identity.position.z=1.82+.12*ramp(t,6.2,7.5);
 (sign.material as MeshBasicMaterial).opacity=1-ramp(t,6.45,6.88);
 sign.visible=t<6.9;
 // The last shot approaches a pale workcell aperture, matching the light on
 // the homepage's right-hand visual field before the DOM is revealed.
 renderer.toneMappingExposure=1.1*Math.pow(ramp(t,0,.6),1.6);
 renderer.render(scene,camera);
}
function resize(){renderer.setSize(innerWidth,innerHeight);setTime((window as Window&{__cinemaTime?:number}).__cinemaTime??0);}
window.addEventListener('resize',resize);
const control=window as Window&{__cinemaReady?:boolean;__cinemaTime?:number;__setCinemaTime?:(t:number)=>void;__cinemaCanvas?:HTMLCanvasElement;__cinemaCube?:number[]};
control.__setCinemaTime=(t:number)=>{control.__cinemaTime=t;setTime(t);};
control.__cinemaCanvas=renderer.domElement;control.__cinemaReady=true;control.__setCinemaTime(0);
