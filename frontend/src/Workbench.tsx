import {useEffect,useMemo} from 'react';
import {ExtrudeGeometry,Shape} from 'three';

/** Authored extrusion-frame bench. Its upper surface matches MuJoCo's 1.4 ×
 * 1.3 m table at Z=0; trim, fasteners and legs are visual detailing only. */
export default function Workbench(){
  const geometry=useMemo(()=>{
    const top=new Shape();top.moveTo(-.696,-.646);top.lineTo(.696,-.646);top.lineTo(.696,.646);top.lineTo(-.696,.646);top.closePath();
    const plate=new ExtrudeGeometry(top,{depth:.072,bevelEnabled:true,bevelThickness:.004,bevelSize:.004,bevelSegments:2,steps:1});
    plate.translate(0,0,-.076);
    // Slotted aluminum structural profile, rather than solid furniture blocks.
    const profile=new Shape();const points=[[-.025,-.025],[-.006,-.025],[-.006,-.014],[.006,-.014],[.006,-.025],[.025,-.025],[.025,-.006],[.014,-.006],[.014,.006],[.025,.006],[.025,.025],[.006,.025],[.006,.014],[-.006,.014],[-.006,.025],[-.025,.025],[-.025,.006],[-.014,.006],[-.014,-.006],[-.025,-.006]];
    points.forEach(([x,y],i)=>i?profile.lineTo(x,y):profile.moveTo(x,y));profile.closePath();
    const leg=new ExtrudeGeometry(profile,{depth:.7,bevelEnabled:false});
    const railX=new ExtrudeGeometry(profile,{depth:1.2,bevelEnabled:false});
    const railY=new ExtrudeGeometry(profile,{depth:1.1,bevelEnabled:false});
    return {plate,leg,railX,railY};
  },[]);
  useEffect(()=>()=>Object.values(geometry).forEach(g=>g.dispose()),[geometry]);
  return <group position={[.4,0,0]} dispose={null}>
    <mesh geometry={geometry.plate} castShadow receiveShadow><meshStandardMaterial color="#aeb2b1" metalness={.52} roughness={.42}/></mesh>
    {[-.6,.6].flatMap(x=>[-.55,.55].map(y=><group key={x+':'+y} position={[x,y,-.78]}><mesh geometry={geometry.leg} castShadow><meshStandardMaterial color="#656f76" metalness={.8} roughness={.3}/></mesh><mesh position={[0,0,-.005]} rotation={[Math.PI/2,0,0]}><cylinderGeometry args={[.04,.04,.025,24]}/><meshStandardMaterial color="#20272c" roughness={.72}/></mesh></group>))}
    {[-.55,.55].map(y=><mesh key={y} geometry={geometry.railX} position={[-.6,y,-.12]} rotation={[0,Math.PI/2,0]} castShadow><meshStandardMaterial color="#737e84" metalness={.8} roughness={.32}/></mesh>)}
    {[-.6,.6].map(x=><mesh key={x} geometry={geometry.railY} position={[x,.55,-.12]} rotation={[Math.PI/2,0,0]} castShadow><meshStandardMaterial color="#737e84" metalness={.8} roughness={.32}/></mesh>)}
    {[-.58,.58].flatMap(x=>[-.53,.53].map(y=><mesh key={x+':'+y} position={[x,y,.0003]} rotation={[Math.PI/2,0,0]}><cylinderGeometry args={[.004,.004,.001,6]}/><meshStandardMaterial color="#626c73" metalness={.9} roughness={.25}/></mesh>))}
  </group>;
}
