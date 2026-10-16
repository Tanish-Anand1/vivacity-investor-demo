import {useMemo} from 'react';
import {BufferAttribute,BufferGeometry,Color,Quaternion,Vector3,SRGBColorSpace} from 'three';
import type {Dict,Vec3} from './domain';
import {objectHalfSizes} from './pickupWorkspace';
import Workbench from './Workbench';
type MeshSpec = { id: number; positions: { byte_offset: number; count: number }; indices: { byte_offset: number; count: number } };
type Geom = { id: number; name: string; body_id: number; type: string; group: number; mesh_id: number | null; position: Vec3; quaternion_wxyz: number[]; size: Vec3; rgba: number[] };
type Manifest = { bodies: {id: number; name: string}[]; geoms: Geom[]; meshes: MeshSpec[] };
export type Assets = { manifest: Manifest; geometry: Map<number,BufferGeometry> };
const assetPromises=new Map<string,Promise<Assets>>();
export function loadAssets(robot='panda') {
  if (!assetPromises.has(robot)) assetPromises.set(robot,(async () => {
    const start = performance.now();
    const prefix=robot==='panda'?'/vivacity':`/vivacity/robots/${encodeURIComponent(robot)}`;
    const [a,b] = await Promise.all([fetch(prefix+'/robot-geometry.json'), fetch(prefix+'/robot-meshes.bin')]);
    if (!a.ok || !b.ok) throw new Error('Robot geometry assets could not be loaded.');
    const manifest = await a.json() as Manifest, buffer = await b.arrayBuffer();
    const geometry = new Map<number,BufferGeometry>();
    for (const mesh of manifest.meshes) {
      const g = new BufferGeometry();
      g.setAttribute('position', new BufferAttribute(new Float32Array(buffer, mesh.positions.byte_offset, mesh.positions.count),3));
      g.setIndex(new BufferAttribute(new Uint32Array(buffer,mesh.indices.byte_offset,mesh.indices.count),1));
      g.computeVertexNormals(); g.computeBoundingSphere(); geometry.set(mesh.id,g);
    }
    (window as unknown as { __vivacityPerformance: Dict }).__vivacityPerformance = {
      ...((window as unknown as {__vivacityPerformance?: Dict}).__vivacityPerformance ?? {}), robotAssetLoadMs: performance.now()-start, meshBytes: buffer.byteLength
    };
    return { manifest, geometry };
  })().catch(err => { assetPromises.delete(robot); throw err; }));
  return assetPromises.get(robot)!;
}
const quaternion = (q: number[]) => new Quaternion(q[1],q[2],q[3],q[0]);

export function GeomMesh({ geom, assets, config }: { geom: Geom; assets: Assets; config: Dict }) {
  const q = quaternion(geom.quaternion_wxyz);
  if(geom.type==='cylinder'||geom.type==='capsule')q.multiply(new Quaternion().setFromAxisAngle(new Vector3(1,0,0),Math.PI/2));
  const size = (geom.name === 'obstacle_geom' ? config.obstacle_size ?? geom.size : geom.name === 'cube' && config.task === 'pick_place'
    ? objectHalfSizes(config) : geom.size) as Vec3;
  const color = useMemo(() => new Color().setRGB(geom.rgba[0],geom.rgba[1],geom.rgba[2],SRGBColorSpace),[geom]);
  if(geom.name==='table'&&geom.size.every((v,i)=>Math.abs(v-[.7,.65,.04][i])<1e-6)&&geom.position.every((v,i)=>Math.abs(v-[.4,0,-.04][i])<1e-6))return <Workbench/>;
  return <mesh position={geom.position} quaternion={q} geometry={geom.mesh_id !== null ? assets.geometry.get(geom.mesh_id) : undefined} castShadow={geom.type !== 'plane'} receiveShadow>
    {geom.type === 'box' && <boxGeometry args={[size[0]*2,size[1]*2,size[2]*2]} />}
    {geom.type === 'plane' && <planeGeometry args={[6,6]} />}
    {geom.type === 'cylinder' && <cylinderGeometry args={[size[0],size[0],size[1]*2,36]} />}
    {geom.type === 'capsule' && <capsuleGeometry args={[size[0],size[1]*2,8,20]} />}
    <meshStandardMaterial color={config.collision_overlay?'#a8d4cb':color} wireframe={!!config.collision_overlay} transparent={!!config.collision_overlay} opacity={config.collision_overlay?.65:1} roughness={geom.name === 'table' ? .78 : .38} metalness={geom.group === 2 ? .18 : .05} />
  </mesh>;
}

