import {useEffect,useState} from 'react';
import {workspaceApi} from './workspaceApi';
import type {components} from './generated/api';

export type Physics=Required<components['schemas']['PhysicsSettings']>;
export const defaultPhysics:Physics={schema_version:'vivacity.physics/1.0',gravity_m_s2:9.81,air_density_kg_m3:0,air_viscosity_pa_s:0,wind_velocity_m_s:[0,0,0],blunt_drag_coefficient:.5,contact_damping_ratio:1,gripper_force_scale:1,object_force_n:[0,0,0],object_torque_nm:[0,0,0]};
export type Material=NonNullable<components['schemas']['RoboticsConfig']['object_material']>;
export default function PhysicsControls({value,material,onChange,onMaterial}:{value:Physics;material:Material;onChange:(p:Physics)=>void;onMaterial:(m:Material,friction?:number)=>void}){
 const [materials,setMaterials]=useState<Record<string,{name:string;sliding:number}>>({}),[error,setError]=useState('');
 useEffect(()=>{let active=true;workspaceApi.materials().then(r=>{if(active)setMaterials(r.materials);}).catch(()=>{if(active)setError('Material registry unavailable. Custom physical coefficients remain usable.');});return()=>{active=false;};},[]);
 const scalar=(label:string,key:'gravity_m_s2'|'air_density_kg_m3'|'air_viscosity_pa_s'|'blunt_drag_coefficient'|'contact_damping_ratio'|'gripper_force_scale',min:number,max:number,step:number)=><label>{label}<input type="number" min={min} max={max} step={step} required value={value[key]} onChange={e=>onChange({...value,[key]:Number(e.target.value)})}/></label>;
 return <div className="physics-controls"><label>Physical material<select value={material} onChange={e=>onMaterial(e.target.value as Material,materials[e.target.value]?.sliding)}><option value="custom">Custom contact coefficients</option>{Object.entries(materials).map(([id,m])=><option key={id} value={id}>{m.name}</option>)}</select></label>
 <p className="small">Material presets set sliding, torsional and rolling friction. Mass stays independent. Values are illustrative, not calibrated to a real material pair.</p>{error&&<p role="status" className="small">{error}</p>}
 <details><summary>Gravity, air & contact mechanics</summary><div className="config-fields">
 {scalar('Gravity (m/s²)','gravity_m_s2',0,20,.01)}{scalar('Air density (kg/m³)','air_density_kg_m3',0,5,.001)}{scalar('Air viscosity (Pa·s)','air_viscosity_pa_s',0,.001,.000001)}
 {['X','Y','Z'].map((axis,i)=><label key={axis}>Wind {axis} (m/s)<input type="number" min={-20} max={20} step={.5} value={value.wind_velocity_m_s[i]} onChange={e=>onChange({...value,wind_velocity_m_s:value.wind_velocity_m_s.map((v,j)=>j===i?Number(e.target.value):v)})}/></label>)}
 {scalar('Blunt drag coefficient','blunt_drag_coefficient',0,3,.05)}{scalar('Contact damping ratio','contact_damping_ratio',.2,1,.05)}{scalar('Gripper actuator force limit scale','gripper_force_scale',.05,1,.05)}
 </div><p className="small">Air is disabled at zero density and viscosity. Use 1.225 kg/m³ and 0.000018 Pa·s for an illustrative air experiment. The simulator uses simplified fluid models. Contact damping is not an exact restitution coefficient. The gripper scale limits its actuator, not a prescribed measured jaw force.</p></details>
 <details><summary>Applied object force & torque</summary><div className="config-fields">{(['object_force_n','object_torque_nm'] as const).flatMap(key=>['X','Y','Z'].map((axis,i)=><label key={key+axis}>{key==='object_force_n'?'Force':'Torque'} {axis} ({key==='object_force_n'?'N':'Nm'})<input type="number" min={key==='object_force_n'?-2:-.2} max={key==='object_force_n'?2:.2} step={key==='object_force_n'?.05:.005} value={value[key][i]} onChange={e=>onChange({...value,[key]:value[key].map((v,j)=>j===i?Number(e.target.value):v)})}/></label>))}</div><p className="small">Constant external force and torque in world coordinates, applied throughout the experiment. These can make a grasp fail.</p></details>
 </div>;
}
