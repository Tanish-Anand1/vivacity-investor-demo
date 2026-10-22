/** THE ONE: deterministic authored cinema, never simulation evidence.
 * Metres, Z up. MuJoCo FK poses preserve robot articulation. Architecture is
 * intentionally impossible; this source never calls the experiment runtime.
 */
import {ACESFilmicToneMapping,AmbientLight,BoxGeometry,BufferAttribute,BufferGeometry,Color,DirectionalLight,Euler,ExtrudeGeometry,Group,Mesh,MeshBasicMaterial,MeshPhysicalMaterial,MeshStandardMaterial,PCFSoftShadowMap,PerspectiveCamera,PMREMGenerator,Quaternion,Scene,Shape,SpotLight,Vector3,WebGLRenderer,SRGBColorSpace} from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {FontLoader} from 'three/addons/loaders/FontLoader.js';
import {TextGeometry} from 'three/addons/geometries/TextGeometry.js';
import {EffectComposer} from 'three/addons/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/addons/postprocessing/RenderPass.js';
import {BokehPass} from 'three/addons/postprocessing/BokehPass.js';
import {OutputPass} from 'three/addons/postprocessing/OutputPass.js';
import {GTAOPass} from 'three/addons/postprocessing/GTAOPass.js';
import {mergeVertices} from 'three/addons/utils/BufferGeometryUtils.js';
import {ISABELLA_OPENING_CONFIG as isabellaOpening} from '../src/openingConfig';

type XYZ=[number,number,number];type Pose=[number[],number[]];
type Manifest={meshes:{id:number;positions:[number,number];indices:[number,number]}[];geoms:{body:number;mesh:number|null;position:number[];quaternion:number[];rgba:number[]}[]};
type Frame={time:number;poses:Pose[];cube:{position:number[];quaternion:number[]}};
type Actor={root:Group;parts:{mesh:Mesh;body:number;p:Vector3;q:Quaternion}[]};
type Key={t:number;p:XYZ};
const clamp=(v:number,a=0,b=1)=>Math.min(b,Math.max(a,v));
const smooth=(v:number)=>{const x=clamp(v);return x*x*x*(x*(x*6-15)+10);};
const ramp=(t:number,a:number,b:number)=>smooth((t-a)/(b-a));
const mix=(a:number,b:number,k:number)=>a+(b-a)*k;
const v=(a:number[])=>new Vector3(a[0],a[1],a[2]);
const q=(a:number[])=>new Quaternion(a[1],a[2],a[3],a[0]);
const portrait=innerHeight>innerWidth,previz=new URLSearchParams(location.search).has('previz');
const scene=new Scene();scene.background=new Color('#030405');
const camera=new PerspectiveCamera(38,innerWidth/innerHeight,.015,150);camera.up.set(0,0,1);
const renderer=new WebGLRenderer({antialias:true,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setPixelRatio(1);renderer.setSize(innerWidth,innerHeight);renderer.outputColorSpace=SRGBColorSpace;
renderer.toneMapping=ACESFilmicToneMapping;renderer.shadowMap.enabled=!previz;renderer.shadowMap.type=PCFSoftShadowMap;
document.body.append(renderer.domElement);
// Original studio reflection cards, not a photograph or an on-screen backdrop.
const studio=new Scene();studio.background=new Color('#080b0d');
for(const [size,pos,intensity] of [ [[14,.15,8],[0,-7,5],3.8], [[.12,9,7],[-6,0,4],2.9], [[.16,8,2],[7,2,5],1.8], [[12,10,.1],[0,0,10],2.5] ] as [XYZ,XYZ,number][]){
 const mesh=new Mesh(new BoxGeometry(...size),new MeshBasicMaterial({color:new Color('#f6efe1').multiplyScalar(intensity)}));mesh.position.set(...pos);studio.add(mesh);
}
const pmrem=new PMREMGenerator(renderer);const environment=pmrem.fromScene(studio,.03);scene.environment=environment.texture;
const ambient=new AmbientLight('#d6dbe0',.18);scene.add(ambient);
const keyLight=new DirectionalLight('#f5ecdd',3.2);keyLight.position.set(2,-5,9);keyLight.castShadow=true;
keyLight.shadow.mapSize.set(2048,2048);Object.assign(keyLight.shadow.camera,{left:-12,right:12,top:20,bottom:-8,near:.1,far:60});
keyLight.shadow.normalBias=.008;keyLight.shadow.bias=-.00015;scene.add(keyLight);
const rim=new DirectionalLight('#bccbd6',2.1);rim.position.set(-6,6,10);scene.add(rim);
const fill=new DirectionalLight('#e0ddd5',.7);fill.position.set(0,-15,7);scene.add(fill);
const detail=new SpotLight('#fff3df',40,8,.52,.7,1);detail.position.set(1,-2,5);detail.target.position.set(1,0,1);scene.add(detail,detail.target);
const titanium=new MeshPhysicalMaterial({color:'#b7b8b4',metalness:.88,roughness:.25,clearcoat:.12});
const black=new MeshPhysicalMaterial({color:'#111416',metalness:.65,roughness:.35});
const graphite=new MeshPhysicalMaterial({color:'#24292c',metalness:.7,roughness:.37});
const polished=new MeshPhysicalMaterial({color:'#cbd0ce',metalness:.96,roughness:.16,clearcoat:.22});
const warm=new MeshStandardMaterial({color:'#a58e69',metalness:.82,roughness:.26});
const ivory=new MeshStandardMaterial({color:'#e3e1d8',metalness:.3,roughness:.31});
// Smooth geometry and restrained roughness avoid screen-space machining moire.
function block(parent:Group|Scene,size:XYZ,pos:XYZ,mat:MeshStandardMaterial=graphite,bevel=.018){
 const geo=bevel?new RoundedBoxGeometry(...size,2,Math.min(bevel,...size.map(s=>s/4))):new BoxGeometry(...size);
 const mesh=new Mesh(geo,mat);mesh.position.set(...pos);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;
}
function prism(points:number[][],depth:number,mat:MeshStandardMaterial){
 const shape=new Shape();shape.moveTo(...points[0] as [number,number]);points.slice(1).forEach(p=>shape.lineTo(p[0],p[1]));shape.closePath();
 const mesh=new Mesh(new ExtrudeGeometry(shape,{depth,bevelEnabled:true,bevelSegments:2,steps:1,bevelSize:.025,bevelThickness:.025,curveSegments:1}),mat);
 mesh.castShadow=true;mesh.receiveShadow=true;return mesh;
}
function beam(parent:Group,a:XYZ,b:XYZ,width:number,depth:number,mat:MeshStandardMaterial){
 const start=v(a),end=v(b),delta=end.clone().sub(start);
 const mesh=block(parent,[width,depth,delta.length()],start.clone().add(end).multiplyScalar(.5).toArray() as XYZ,mat);
 mesh.quaternion.setFromUnitVectors(new Vector3(0,0,1),delta.normalize());return mesh;
}
async function checked(url:string){const r=await fetch(url);if(!r.ok)throw Error(`Cinematic asset unavailable: ${url}`);return r;}
const [manifest,bin,motion,fontData]=await Promise.all([
 checked('/cinematic/generated/panda.json').then(r=>r.json() as Promise<Manifest>),
 checked('/cinematic/generated/panda.bin').then(r=>r.arrayBuffer()),
 checked('/cinematic/generated/the-one-panda-motion.json').then(r=>r.json() as Promise<{frames:Frame[]}>),
 checked('/cinematic/fonts/instrument-sans-outline.json').then(r=>r.json()),
]);
const geometries=new Map<number,BufferGeometry>();
for(const spec of manifest.meshes){const geo=new BufferGeometry();geo.setAttribute('position',new BufferAttribute(new Float32Array(bin,spec.positions[0],spec.positions[1]),3));geo.setIndex(new BufferAttribute(new Uint32Array(bin,spec.indices[0],spec.indices[1]),1));const welded=mergeVertices(geo,1e-5);welded.computeVertexNormals();geometries.set(spec.id,welded);}
function robot(parent:Group):Actor{
 const root=new Group();root.position.set(0,0,.54);root.scale.setScalar(1.8);parent.add(root);const parts:Actor['parts']=[];
 for(const spec of manifest.geoms){if(spec.mesh===null||!geometries.has(spec.mesh))continue;
  const lum=(spec.rgba[0]+spec.rgba[1]+spec.rgba[2])/3;
  const mesh=new Mesh(geometries.get(spec.mesh),lum<.28?black:titanium);mesh.castShadow=true;mesh.receiveShadow=true;root.add(mesh);
  parts.push({mesh,body:spec.body,p:v(spec.position),q:q(spec.quaternion)});
 }return {root,parts};
}
function getFrame(t:number){return motion.frames[Math.min(motion.frames.length-1,Math.max(0,Math.round(t*60)))];}
function pose(actor:Actor,t:number){for(const part of actor.parts){const [p0,q0]=getFrame(t).poses[part.body],rot=q(q0);part.mesh.position.copy(v(p0)).add(part.p.clone().applyQuaternion(rot));part.mesh.quaternion.copy(rot.multiply(part.q));}}
function cube(parent:Group|Scene){
 const root=new Group();parent.add(root);const shell=new Mesh(new RoundedBoxGeometry(.06,.06,.06,4,.0022),polished);shell.castShadow=true;root.add(shell);
 for(const sign of [-1,1]){block(root,[.042,.0006,.0012],[0,sign*.0301,.015],black,0);block(root,[.0012,.0006,.036],[-.015,sign*.0301,0],black,0);block(root,[.008,.0007,.0024],[.015,sign*.0302,-.016],warm,0);}return root;
}
type World={root:Group;deck:Group;rail:Group;walls:Group;actor:Actor;cube:Group;base:Vector3;split:Vector3;phase:number};
const worlds:World[]=[],bases:XYZ[]=[[0,0,0],[0,6,0],[0,12,0],[0,18,0]];
const splits:XYZ[]=portrait?[[0,0,0],[-2.2,2,3.2],[2.2,3,6.4],[0,4,9.6]]:[[0,0,0],[-6.2,2,1.4],[6.3,4,3.4],[.2,8,6.8]];
for(let i=0;i<4;i++){
 const root=new Group();scene.add(root);const deck=new Group(),rail=new Group(),walls=new Group();root.add(deck,rail,walls);
 const cutFace=new MeshStandardMaterial({color:'#646b6e',metalness:.55,roughness:.43});
 // These are contiguous six-metre slices of one long industrial hall. The
 // exposed foundation and sawtooth wall sections retain their mass on separation.
 const floor=prism([[-3.35,-3],[3.35,-3],[3.35,2.65],[3,3],[-3,3],[-3.35,2.65]],.88,cutFace);floor.position.z=-.9;deck.add(floor);
 const inset=prism([[-3.08,-3],[3.08,-3],[3.08,2.55],[2.75,3],[-2.75,3],[-3.08,2.55]],.045,black);inset.position.z=-.01;deck.add(inset);
 // A machined edge and recessed core read as a real fractured slab, not a tray.
 block(deck,[6.45,.18,.22],[0,-2.94,-.19],cutFace,.018);
 block(deck,[5.72,.05,.34],[0,-3.035,-.55],black,.008);
 for(const x of [-3.18,3.18]){
  beam(deck,[x,-2.85,-.14],[x,2.75,-.14],.065,.08,titanium);
  beam(deck,[x,-2.65,-.86],[x,.1,-1.55],.32,.4,graphite);
  beam(deck,[x,.1,-1.55],[x,2.65,-.86],.32,.4,graphite);
 }
 for(const x of [-2.3,0,2.3])block(deck,[.12,.08,.34],[x,-3.06,-.55],titanium,.008);
 for(const y of [-2.2,0,2.2])block(deck,[6.08,.008,.003],[0,y,.041],graphite,0);
 // Structural floor edges become the same folded confluence symbol at the end.
 beam(rail,[-3,3,0],[0,-3,0],.22,.34,titanium);beam(rail,[0,-3,0],[3,3,0],.22,.34,titanium);
 beam(rail,[-2.94,3,.12],[0,-2.86,.12],.025,.027,warm);beam(rail,[0,-2.86,.12],[2.94,3,.12],.025,.027,warm);
 block(deck,[1.12,1.02,.49],[0,0,.25],black);block(deck,[1.18,1.08,.04],[0,0,.515],titanium,.01);
 for(const side of [-1,1]){
  // The diagonal shear walls carry the cantilevered roof. The large opening
  // remains part of the hall, rather than a thin frame around a robot display.
  const wall=prism([[-3,0],[3,0],[3,5.65],[1.35,5.65],[-.15,2.15],[-3,1.2]],.62,graphite);
  wall.rotation.set(0,Math.PI/2,Math.PI/2);
  wall.position.x=side<0?-3.45:2.83;walls.add(wall);
  const x=side*3.03;
  beam(walls,[x,-2.82,1.22],[x,-.15,2.15],.18,.26,cutFace);
  beam(walls,[x,-.15,2.15],[x,1.35,5.65],.27,.44,cutFace);
  beam(walls,[x-side*.14,-.15,2.15],[x-side*.14,1.35,5.65],.045,.07,titanium);
  block(walls,[.82,1.1,5.6],[side*3.05,2.4,2.8],graphite,.055);
  block(walls,[.11,.08,5.37],[side*2.61,1.81,2.8],black,.012);
  // A restrained undercut separates each supporting pier from the roof mass.
  block(walls,[.96,.92,.09],[side*3.05,2.35,5.59],black,.012);
 }
 block(walls,[7.2,2.45,.58],[0,1.78,5.94],graphite,.055);
 block(walls,[6.95,.16,.3],[0,.61,5.84],cutFace,.018);
 block(walls,[5.2,1.86,.12],[0,1.85,5.61],black,.022);
 beam(walls,[-2.4,.8,5.53],[2.4,.8,5.53],.045,.065,ivory);
 block(deck,[.8,.82,.6],[1,.45,.3],black,.04).name='contact-surface';
 const actor=robot(deck),object=cube(actor.root);worlds.push({root,deck,rail,walls,actor,cube:object,base:v(bases[i]),split:v(splits[i]),phase:[3.05,.45,1.48,2.65][i]});
}
const seam=block(scene,[.014,23,.006],[0,7.5,.035],warm,0);
const resolvedCube=cube(scene);resolvedCube.scale.setScalar(1.8);
for(const world of worlds)for(const child of world.rail.children)child.userData.restX=child.position.x;
const font=new FontLoader().parse(fontData);
function word(text:string,size:number,tracking:number,material:MeshStandardMaterial){
 const group=new Group();let cursor=0;
 for(const letter of text){
  const geo=new TextGeometry(letter,{font,size,depth:.035,curveSegments:12,bevelEnabled:true,bevelSize:.002,bevelThickness:.002,bevelSegments:2});
  const mesh=new Mesh(geo,material);mesh.position.x=cursor;mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);cursor+=fontData.glyphs[letter].ha/1000*size+tracking;
 }group.children.forEach(c=>c.position.x-=(cursor-tracking)/2);group.rotation.x=Math.PI/2;return group;
}
const identity=new Group();scene.add(identity);
const wordmark=word('VIVACITY',1.18,.043,ivory);identity.add(wordmark);
const lab=word(isabellaOpening.labName.toUpperCase(),portrait?.34:.47,.025,ivory),byline=word(isabellaOpening.labSubtitle.toUpperCase(),.135,.027,warm);
lab.position.set(0,0,-.72);byline.position.set(0,0,-1.05);identity.add(lab,byline);
const shutter=block(identity,[7.9,.19,1.55],[0,-.12,.42],black,.025);
/** Time-aware C1 Hermite camera rig. Fixed destinations, no randomized orbit. */
function sample(keys:Key[],t:number){
 let i=0;while(i<keys.length-2&&t>keys[i+1].t)i++;const a=keys[i],b=keys[i+1],prev=keys[Math.max(0,i-1)],next=keys[Math.min(keys.length-1,i+2)];
 const u=clamp((t-a.t)/(b.t-a.t)),dt=b.t-a.t,m0=v(b.p).sub(v(prev.p)).multiplyScalar(dt/(b.t-prev.t)),m1=v(next.p).sub(v(a.p)).multiplyScalar(dt/(next.t-a.t));
 // Monotone tangent limiting avoids a macro lens overshooting through the hand.
 for(const axis of ['x','y','z'] as const){const d=v(b.p)[axis]-v(a.p)[axis];if(Math.abs(d)<1e-8){m0[axis]=0;m1[axis]=0;}else{m0[axis]=Math.sign(d)*clamp(m0[axis]*Math.sign(d),0,3*Math.abs(d));m1[axis]=Math.sign(d)*clamp(m1[axis]*Math.sign(d),0,3*Math.abs(d));}}
 return v(a.p).multiplyScalar(2*u**3-3*u*u+1).add(m0.multiplyScalar(u**3-2*u*u+u)).add(v(b.p).multiplyScalar(-2*u**3+3*u*u)).add(m1.multiplyScalar(u**3-u*u));
}
const startCube=v(getFrame(0).cube.position).multiplyScalar(1.8).add(new Vector3(0,0,.54));
const releaseCube=v(getFrame(2.65).cube.position).multiplyScalar(1.8).add(new Vector3(0,0,.54));
const contactCube=v(getFrame(3.05).cube.position).multiplyScalar(1.8).add(new Vector3(0,0,.54));
const breakRotation=new Quaternion().setFromEuler(new Euler(0,-.1125,-.11));
const convergenceOrigin=contactCube.clone().applyQuaternion(breakRotation);
const convergenceRotation=breakRotation.clone().multiply(q(getFrame(3.05).cube.quaternion));
for(const world of worlds){const surface=world.deck.getObjectByName('contact-surface') as Mesh;const h=contactCube.z-.054;surface.position.set(contactCube.x,contactCube.y,h/2);surface.scale.z=h/.6;}
const cameraKeys:Key[]=[
 {t:0,p:startCube.clone().add(new Vector3(.12,-.23,-.025)).toArray() as XYZ},{t:.8,p:startCube.clone().add(new Vector3(.44,-.72,.12)).toArray() as XYZ},
 {t:1.4,p:portrait?[4.5,-6.4,3.6]:[3.6,-5.2,3.1]},{t:2.2,p:portrait?[4.5,-7,3.8]:[4.1,-6.4,3.5]},
 {t:2.65,p:releaseCube.clone().add(new Vector3(2.6,-4.1,1.35)).toArray() as XYZ},{t:3.05,p:releaseCube.clone().add(new Vector3(2.9,-4.5,1.5)).toArray() as XYZ},
 {t:3.65,p:portrait?[4,-23,10]:[6,-13,6.5]},{t:4.4,p:portrait?[1,-28,12]:[3,-15,8.5]},{t:4.65,p:portrait?[1,-26,12]:[1,-14,8.5]},
 {t:5.1,p:portrait?[1.4,-19,7]:[2.8,-15,7]},{t:5.55,p:portrait?[.9,-20,4.6]:[.9,-12.8,4.5]},
 {t:6.5,p:portrait?[.9,-20,4.6]:[.9,-12.8,4.5]},{t:6.9,p:portrait?[.9,-14,4.6]:[.9,-8,4.5]},{t:7.5,p:[.9,2,4.5]},
];
const lookKeys:Key[]=[{t:0,p:startCube.toArray() as XYZ},{t:.8,p:startCube.toArray() as XYZ},{t:1.4,p:[.6,1.1,1.55]},{t:2.2,p:[.8,1.3,1.6]},
 {t:2.65,p:releaseCube.toArray() as XYZ},{t:3.05,p:contactCube.toArray() as XYZ},{t:3.65,p:[0,4,3]},{t:4.4,p:[0,5,4]},
 {t:4.65,p:[0,5,4]},{t:5.1,p:[.9,2.6,4.1]},{t:5.55,p:[.9,2.5,4.3]},{t:6.5,p:[.9,2.5,4.3]},{t:6.9,p:[.9,2.5,4.3]},{t:7.5,p:[.9,8,4.5]}];
const composer=new EffectComposer(renderer);composer.addPass(new RenderPass(scene,camera));
const ao=new GTAOPass(scene,camera,innerWidth,innerHeight);ao.updateGtaoMaterial({radius:.32,thickness:.18});ao.blendIntensity=.6;ao.enabled=!previz;composer.addPass(ao);
const dof=new BokehPass(scene,camera,{focus:1,aperture:.0006,maxblur:.008});composer.addPass(dof);composer.addPass(new OutputPass());
const dofUniforms=dof.uniforms as Record<string,{value:number}>;
const control=window as Window&{__cinemaReady?:boolean;__cinemaTime?:number;__setCinemaTime?:(t:number)=>void;__cinemaCanvas?:HTMLCanvasElement;__cinemaCube?:number[];__cinemaPoints?:object;__cinemaMetrics?:object};
function setTime(input:number){
 const t=clamp(input,0,7.5);control.__cinemaTime=t;const split=ramp(t,3.05,4.4),join=ramp(t,4.65,5.55),entry=ramp(t,6.5,7.5);
 for(let i=0;i<worlds.length;i++){
  const w=worlds[i];w.root.position.copy(w.base).lerp(w.split,split).lerp(new Vector3(.9,2.8+i*.12,4.72),join);
  w.root.scale.set(mix(1,1-i*.16,join),1,1);w.root.rotation.set(Math.PI/2*join,(i-1.5)*.075*split*(1-join),(i%2?1:-1)*.11*split*(1-join));
  for(const child of w.rail.children){const rest=child.userData.restX as number;child.position.x=rest+Math.sign(rest)*entry*8;}
  w.deck.position.z=-4.2*ramp(t,4.75,5.48);w.deck.visible=t<5.55;w.walls.position.z=5*ramp(t,4.65,5.48);w.walls.visible=t<5.55;
  const poseTime=Math.max(0,t<3.05?t-Math.min(i*.14,t):mix(3.05,w.phase,ramp(t,3.1,3.75)));pose(w.actor,poseTime);
  const f=getFrame(poseTime);w.cube.position.copy(v(f.cube.position));w.cube.quaternion.copy(q(f.cube.quaternion));
 }
 worlds[0].root.updateMatrixWorld(true);
 resolvedCube.visible=t>=4.65;worlds[0].cube.visible=t<4.65;
 resolvedCube.position.copy(convergenceOrigin).lerp(new Vector3(.9,2.45,1.72),join);resolvedCube.quaternion.copy(convergenceRotation).slerp(q(getFrame(3.05).cube.quaternion),join);
 const heroPosition=t<4.65?worlds[0].cube.getWorldPosition(new Vector3()):resolvedCube.position.clone();control.__cinemaCube=heroPosition.toArray();
 seam.scale.y=ramp(t,3.05,3.38);seam.visible=t>=3.05&&t<3.65;
 camera.position.copy(sample(cameraKeys,t));camera.lookAt(sample(lookKeys,t));camera.fov=portrait?40:38;camera.updateProjectionMatrix();
 identity.position.set(.9,1.85,.45);identity.scale.setScalar(portrait?.76:1);identity.visible=t>=5.18&&t<7.4;
 shutter.visible=t<5.55;shutter.rotation.z=-Math.PI/2*ramp(t,5.24,5.55);shutter.position.z=.42+2.3*ramp(t,5.24,5.55);
 wordmark.position.z=-2*ramp(t,6.5,6.82);wordmark.rotation.x=Math.PI/2;wordmark.visible=t<6.82;
 lab.visible=byline.visible=t>=6.5;lab.position.y=byline.position.y=mix(2,0,ramp(t,6.5,6.87));
 lab.position.z=3.65;byline.position.z=3.25;
 scene.environmentIntensity=mix(.08,.9,ramp(t,.3,1.2));ambient.intensity=mix(.008,.32,ramp(t,.4,1.3));keyLight.intensity=mix(.15,2.9,ramp(t,.2,1.2));rim.intensity=mix(.3,2.4,ramp(t,.4,1.3));fill.intensity=.7*ramp(t,.65,1.4);
 const wide=ramp(t,2.9,3.5);Object.assign(keyLight.shadow.camera,{left:mix(-3,-12,wide),right:mix(4,12,wide),top:mix(5,20,wide),bottom:mix(-3,-8,wide)});keyLight.shadow.camera.updateProjectionMatrix();
 renderer.toneMappingExposure=1.03*ramp(t,0,.3);dof.enabled=!previz&&t<1.2;dofUniforms.focus.value=camera.position.distanceTo(heroPosition);dofUniforms.aperture.value=.00035*(1-ramp(t,.65,1.2));
 composer.render();control.__cinemaPoints={contact:contactCube.toArray(),split,join,entry,worlds:worlds.map(w=>w.root.position.toArray()),hero_ndc:heroPosition.clone().project(camera).toArray(),identity_ndc:identity.getWorldPosition(new Vector3()).project(camera).toArray()};
 control.__cinemaMetrics={t,triangles:renderer.info.render.triangles,calls:renderer.info.render.calls,portrait,previz};
}
control.__setCinemaTime=setTime;control.__cinemaCanvas=renderer.domElement;
window.addEventListener('resize',()=>{renderer.setSize(innerWidth,innerHeight);composer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;setTime(control.__cinemaTime??0);});
setTime(0);control.__cinemaReady=true;
