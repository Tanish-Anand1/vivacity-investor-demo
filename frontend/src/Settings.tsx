import { useState } from 'react';
import { ArrowRight, X } from '@phosphor-icons/react';
import { format, type Dict } from './domain';
import { clampPickupPosition, objectHalfSizes, pickupBounds, pickupSeparationValid } from './pickupWorkspace';
import PhysicsControls,{defaultPhysics,type Physics,type Material} from './PhysicsControls';
import type {components} from './generated/api';
export default function Settings({ config, disabled, apply, close }: { config: Dict; disabled: boolean; apply:(d:Dict)=>Promise<boolean|void>; close:()=>void }) {
  const [position,setPosition] = useState<number[]>(config.obstacle_position as number[] ?? [.45,.04,.22]);
  const [size,setSize] = useState<number[]>(config.obstacle_size as number[] ?? [.055,.13,.22]);
  const [target,setTarget] = useState<number[]>(config.target_position as number[] ?? [.55,.28,.22]);
  const pickup=config.task==='pick_place';
  const orbital=config.scene_profile==='orbital_salvage';
  const [cube,setCube]=useState<number[]>(config.cube_position as number[]??[.5,-.15,.026]);
  const [placement,setPlacement]=useState<number[]>(config.placement_position as number[]??[.5,.18,.026]);
  const [cubeHalfSizes,setCubeHalfSizes]=useState(objectHalfSizes(config));
  const [cubeMass,setCubeMass]=useState(Number(config.cube_mass??.06));
  const [cubeFriction,setCubeFriction]=useState(Number(config.cube_friction??1));
  const [obstacleEnabled,setObstacleEnabled]=useState(config.obstacle_enabled!==false);
  const [physics,setPhysics]=useState<Physics>({...defaultPhysics,...config.physics as Partial<Physics>});
  const [material,setMaterial]=useState<Material>(config.object_material as Material??'custom');
  const precision=config.program_id==='precision_assembly';
  const [assembly,setAssembly]=useState<components['schemas']['AssemblySettings']>((config.assembly as components['schemas']['AssemblySettings'])??{arm_speed_rad_s:.2,grasp_yaw_rad:0,placement_tolerance_m:.006,orientation_tolerance_rad:.12});
  const bounds=pickupBounds(cubeHalfSizes);
  const separationValid=!pickup||pickupSeparationValid(cube,placement);
  const submit = async () => {
    const nextCube=clampPickupPosition(cube[0],cube[1],cubeHalfSizes);
    const nextPlacement=clampPickupPosition(placement[0],placement[1],cubeHalfSizes);
    if(config.physical_operation==='stacking')nextPlacement[2]=3*cubeHalfSizes[2]+.001;
    const applied=await apply( {...config, obstacle_enabled:obstacleEnabled,obstacle_position:position, obstacle_size:size,target_position:target,
      cube_half_size:cubeHalfSizes[2],cube_half_sizes:pickup&&!orbital?cubeHalfSizes:null,cube_mass:cubeMass,cube_friction:cubeFriction,
      cube_position:pickup?nextCube:cube,placement_position:pickup?nextPlacement:placement,physics,object_material:material,
      ...(precision?{assembly}:{})}); if(applied!==false)close();
  };
  return <section className="environment-editor" aria-labelledby="environment-heading">
    <div className="section-heading"><h2 id="environment-heading">Change the scene</h2><button className="icon-button" onClick={close} aria-label="Close settings"><X size={18} /></button></div>
    <>
      <p>Apply to update the world. Then choose Start experiments when you’re ready.</p>
      <label className="select-field"><input type="checkbox" checked={obstacleEnabled} onChange={e=>setObstacleEnabled(e.target.checked)}/> Obstacle enabled</label>
      <div className="presets"><button onClick={()=>{setObstacleEnabled(true);setPosition(orbital?[.75,-.4,.33]:[.45,.04,.22]);setSize(orbital?[.18,.18,.33]:[.055,.13,.22]);}}>Original</button><button onClick={()=>{setObstacleEnabled(true);setPosition([.75,-.4,.2]);setSize(orbital?[.18,.18,.2]:[.055,.13,.22]);}}>Clear route</button><button onClick={()=>{setObstacleEnabled(true);setPosition([.5,.1,.3]);setSize([.35,.35,.3]);}}>Blocked scene</button></div>
      {['X','Y','Z'].map((axis,i)=><label className="range-field" key={axis}><span>{axis} position <output>{format(position[i],2)} m</output></span><input aria-label={`${axis} obstacle position`} type="range" min={[.15,-.5,.05][i]} max={[.8,.5,.6][i]} step=".01" value={position[i]} onChange={e=>setPosition(p=>p.map((v,j)=>j===i?Number(e.target.value):v))} /></label>)}
      {['X','Y'].map((axis,i)=><label className="range-field" key={`target-${axis}`}><span>{axis} {pickup?'pickup':'target'} position <output>{format(pickup?cube[i]:target[i],2)} m</output></span><input aria-label={`${axis} target position`} type="range" min={pickup?(i?bounds.y[0]:bounds.x[0]):(i?-.5:.15)} max={pickup?(i?bounds.y[1]:bounds.x[1]):(i?.5:.8)} step=".001" value={pickup?cube[i]:target[i]} onChange={e=>(pickup?setCube:setTarget)(p=>p.map((v,j)=>j===i?Number(e.target.value):v))}/></label>)}
      {pickup&&['X','Y'].map((axis,i)=><label className="range-field" key={`placement-${axis}`}><span>{axis} placement position <output>{format(placement[i],2)} m</output></span><input aria-label={`${axis} placement position`} type="range" min={i?bounds.y[0]:bounds.x[0]} max={i?bounds.y[1]:bounds.x[1]} step=".001" value={placement[i]} onChange={e=>setPlacement(p=>p.map((v,j)=>j===i?Number(e.target.value):v))}/></label>)}
      {pickup&&!separationValid&&<p className="setting-error" role="alert">Move the pickup or placement point so they are at least 10 cm apart.</p>}
      {pickup&&!orbital&&<>
        {['Width','Depth','Height'].map((name,i)=><label className="range-field" key={name}><span>Object {name.toLowerCase()} <output>{Math.round(cubeHalfSizes[i]*2000)} mm</output></span><input aria-label={`Object ${name.toLowerCase()}`} type="range" min=".02" max=".03" step=".001" value={cubeHalfSizes[i]} onChange={e=>setCubeHalfSizes(s=>s.map((v,j)=>j===i?Number(e.target.value):v) as typeof s)}/></label>)}
        <label className="range-field"><span>Object mass / weight <output>{Math.round(cubeMass*1000)} g · {format(cubeMass*physics.gravity_m_s2,2)} N</output></span><input aria-label="Object mass" type="range" min=".02" max={precision?'.30':'.15'} step=".005" value={cubeMass} onChange={e=>setCubeMass(Number(e.target.value))}/></label>
        <label className="range-field"><span>Object friction coefficient <output>{format(cubeFriction,2)}</output></span><input aria-label="Object friction" type="range" min=".05" max="1.5" step=".05" value={cubeFriction} onChange={e=>{setCubeFriction(Number(e.target.value));setMaterial('custom');}}/></label>
      </>}
      <p className="small">Obstacle half-sizes: {size.map(v=>format(v,3)).join(' × ')} m. Applying a change first stops the worker safely, then initializes new physical conditions. {pickup?'The cube is a dynamic free body held by finger friction.':'This legacy world verifies reaching only.'}</p>
    </>
    {pickup&&!orbital&&<PhysicsControls value={physics} material={material} onChange={setPhysics} onMaterial={(m,f)=>{setMaterial(m);if(f!==undefined)setCubeFriction(f);}}/>}
    {precision&&<details className="configuration-details"><summary>Precision assembly tolerances and motion</summary><div className="config-fields">{([
      ['arm_speed_rad_s','Arm speed (rad/s)',.12,.5,.01],['grasp_yaw_rad','Grasp yaw (rad)',-3.141593,3.141593,.01],
      ['placement_tolerance_m','Placement tolerance (m)',.001,.02,.001],['orientation_tolerance_rad','Orientation tolerance (rad)',.01,.4,.01]
    ] as const).map(([key,label,min,max,step])=><label key={key}>{label}<input type="number" min={min} max={max} step={step} value={assembly[key]} onChange={e=>setAssembly(value=>({...value,[key]:Number(e.target.value)}))}/></label>)}</div><p className="small">These values change the physical motion or the measured pass/fail rule when you apply the scene and run again.</p></details>}
    <button className="primary full" disabled={disabled||!separationValid} onClick={submit}>Apply settings <ArrowRight size={17} /></button>
  </section>;
}
