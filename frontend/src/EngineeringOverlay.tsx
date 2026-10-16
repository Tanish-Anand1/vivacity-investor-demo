import {useEffect,useMemo} from 'react';
import {ArrowHelper,Vector3} from 'three';
import {Line} from '@react-three/drei';
import type {RobotFrame,Vec3} from './domain';
export type OverlayOptions={forces:boolean;velocity:boolean;center:boolean;trajectory:boolean;collision:boolean};
export const defaultOverlays:OverlayOptions={forces:true,velocity:true,center:true,trajectory:false,collision:false};
function VectorArrow({position,value,color,scale}:{position:number[];value:number[];color:string;scale:number}){
 const arrow=useMemo(()=>{const v=new Vector3(...value as Vec3),length=v.length();if(length<1e-8)return null;return new ArrowHelper(v.normalize(),new Vector3(...position as Vec3),Math.min(.6,Math.max(.015,length*scale)),color,.018,.009);},[position,value,color,scale]);
 // ArrowHelper owns its two materials; its geometry is shared by Three.js.
 useEffect(()=>()=>{if(arrow){for(const material of [arrow.line.material,arrow.cone.material].flat())material.dispose();}},[arrow]);
 return arrow?<primitive object={arrow}/>:null;
}
export default function EngineeringOverlay({frame,trace,options}:{frame:RobotFrame;trace:RobotFrame[];options:OverlayOptions}){
 const d=frame.inspection;
 const points=useMemo(()=>trace.map(f=>f.body_transforms.find(b=>b.name==='target')?.position).filter((p):p is Vec3=>!!p),[trace]);
 if(!d)return null;
 return <group>{options.forces&&d.contacts.map((c,i)=><VectorArrow key={i} position={c.position_m} value={c.force_on_geom2_n} color="#e5b97c" scale={.025}/>)}
 {options.forces&&<><VectorArrow position={d.object.center_of_mass_m} value={d.object.applied_force_n} color="#e58b7c" scale={.2}/><VectorArrow position={d.object.center_of_mass_m} value={d.object.applied_torque_nm} color="#bd9fca" scale={2}/></>}
 {options.velocity&&<><VectorArrow position={d.object.center_of_mass_m} value={d.object.linear_velocity_m_s} color="#8dd2c9" scale={.3}/><VectorArrow position={d.object.center_of_mass_m} value={d.object.angular_velocity_rad_s} color="#8caad8" scale={.1}/></>}
 {options.center&&<mesh position={d.object.center_of_mass_m as Vec3}><sphereGeometry args={[.005,12,8]}/><meshBasicMaterial color="#f4e5ba" depthTest={false}/></mesh>}
 {options.trajectory&&points.length>1&&<Line points={points} color="#8dd2c9" lineWidth={1.5} dashed={false}/>}</group>;
}
