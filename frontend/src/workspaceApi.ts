import {API,APIError} from './api';
import {fetchRuntime} from './apiTransport';
import type {components} from './generated/api';

export type LibraryWorld=Omit<components['schemas']['LibraryWorld'],'spec'> & {appearance?:Record<string,unknown>|null;spec:{name:string;description:string;dimensions_m:number[];lighting:{ambient:number;key_intensity:number};geometries:{name:string;type:'box'|'cylinder';position:number[];size:number[];rgba:number[];friction:number}[]}};
export type Configuration=Required<components['schemas']['ExperimentConfiguration']>;
export type SavedConfiguration=Omit<components['schemas']['ConfigurationResponse'],'configuration'> & {configuration:Configuration};
export type Generation=components['schemas']['GenerationResponse'];
export type Resolved=components['schemas']['ResolvedConfiguration'];
export type Option={id:string;name:string;status:string;scope:string;manufacturer?:string;dof?:number;category?:string;model?:string;grippers?:string[];robots?:string[]};
export type Capabilities={openai_configured:boolean;worldlabs_configured:boolean;max_physics_trials:number;generations_per_day:number;registry:{robots:Option[];grippers:Option[];operations:Option[]}};
export function workspaceToken(){
  let token=localStorage.getItem('vivacity:workspace-capability');
  if(!token){token=crypto.randomUUID().replaceAll('-','')+crypto.randomUUID().replaceAll('-','');localStorage.setItem('vivacity:workspace-capability',token);}
  return token;
}
async function request<T>(path:string,method='GET',body?:unknown,extra:Record<string,string>={}):Promise<T>{
  const r=await fetchRuntime(API+'/v1/workspace'+path,{method,headers:{'X-Workspace-Token':workspaceToken(),...(body!==undefined?{'Content-Type':'application/json'}:{}),...extra},
    ...(body!==undefined?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(60000)});
  const value=await r.json().catch(()=>null);
  if(!r.ok)throw new APIError(r.status,value?.detail??'Workspace request could not complete.');
  if(value===null)throw new Error('Workspace returned an unreadable response.');
  return value as T;
}
export const workspaceApi={
  materials:()=>request<{materials:Record<string,{name:string;sliding:number;torsional:number;rolling:number;density_kg_m3:number}>;scope:string}>('/materials'),
  validatePhysics:()=>request<PhysicsValidation>('/physics-validations','POST'),
  capabilities:()=>request<Capabilities>('/capabilities'),
  worlds:()=>request<LibraryWorld[]>('/worlds'),
  world:(id:string)=>request<LibraryWorld>('/worlds/'+encodeURIComponent(id)),
  rename:(id:string,name:string)=>request<LibraryWorld>('/worlds/'+encodeURIComponent(id),'PATCH',{name}),
  duplicate:(id:string)=>request<LibraryWorld>('/worlds','POST',{source_id:id}),
  archive:(id:string)=>request<LibraryWorld>(`/worlds/${encodeURIComponent(id)}/archive`,'POST'),
  restore:(id:string)=>request<LibraryWorld>(`/worlds/${encodeURIComponent(id)}/restore`,'POST'),
  preview:(id:string)=>request<components['schemas']['ImportPreview']>(`/worlds/${encodeURIComponent(id)}/preview`),
  stagedPreview:(id:string)=>request<components['schemas']['ImportPreview']>(`/imports/${encodeURIComponent(id)}/preview`),
  generate:(prompt:string,provider:'openai'|'worldlabs',key:string,input_type:Generation['input_type']='text',inputs:Generation['inputs']=[])=>request<Generation>('/generations','POST',{prompt,provider,seed:7,model:'marble-1.1',input_type,inputs},{'Idempotency-Key':key}),
  async capture(file:File){
    if(file.size>16*1024*1024)throw new Error('Capture limit: 16 MiB per file.');
    const r=await fetchRuntime(`${API}/v1/workspace/captures?filename=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'X-Workspace-Token':workspaceToken(),'Content-Type':'application/octet-stream'},body:file,signal:AbortSignal.timeout(60000)});
    const value=await r.json();if(!r.ok)throw new APIError(r.status,value.detail);return value as components['schemas']['CaptureResponse'];
  },
  generation:(id:string)=>request<Generation>('/generations/'+encodeURIComponent(id)),
  generations:()=>request<Generation[]>('/generations'),
  retry:(id:string)=>request<Generation>(`/generations/${encodeURIComponent(id)}/retry-retrieval`,'POST'),
  async upload(file:File){
    const r=await fetchRuntime(`${API}/v1/workspace/imports?filename=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'X-Workspace-Token':workspaceToken(),'Content-Type':'application/octet-stream'},body:file,signal:AbortSignal.timeout(60000)});
    const value=await r.json();if(!r.ok)throw new APIError(r.status,value.detail);return value as components['schemas']['ImportResponse'];
  },
  map:(id:string,mapping:components['schemas']['ImportMapping'])=>request<LibraryWorld>(`/imports/${encodeURIComponent(id)}/map`,'POST',mapping),
  resolve:(configuration:Configuration)=>request<Resolved>('/configurations/resolve','POST',configuration),
  save:(configuration:Configuration)=>request<SavedConfiguration>('/configurations','POST',configuration),
  configurations:()=>request<SavedConfiguration[]>('/configurations'),
  start:(id:string,config?:Record<string,unknown>)=>request<{session:components['schemas']['SessionResponse'];session_token:string}>(`/configurations/${encodeURIComponent(id)}/runs`,'POST',{config:config??null}),
  runs:()=>request<Run[]>('/runs'),
  compareMeasurements:(sid:string,body:components['schemas']['MeasurementRequest'])=>request<Record<string,unknown>>(`/runs/${encodeURIComponent(sid)}/measurements`,'POST',body),
  interpret:(prompt:string,environment_id:string)=>request<{proposal:{supported:boolean;explanation:string;configuration:Configuration};provenance:Record<string,unknown>}>('/operations/interpret','POST',{prompt,environment_id}),
};
export type Robustness={partitions:Record<string,{completed_configurations:number;successes:number;failures:number;success_rate:number}>;configurations:Record<string,unknown>[];failure_regions:Record<string,unknown>[];scope:string;hardware_validation:string};
export type Run={robustness?:Robustness;session_id:string;configuration_id:string;created_unix_s:number;provenance:Record<string,unknown>;initial_configuration:{config:Record<string,unknown>};session:components['schemas']['SessionResponse'];experiments:{experiment:components['schemas']['ExperimentResponse'];validation_count:number;successful_validations:number;success_rate:number|null;evaluations:{branch_id:string;evaluation:Record<string,unknown>;performance:Record<string,unknown>}[];energy_joules:null;energy_scope:string}[]};
export type PhysicsValidation=components['schemas']['PhysicsValidationResponse'];
export const defaultConfiguration=(world='desktop'):Configuration=>({variation:{enabled:false,position_radius_m:.04,friction_min:.15,friction_max:1.2,mass_min_kg:.04,mass_max_kg:.1,held_out_fraction:.25},physics:{schema_version:'vivacity.physics/1.0',gravity_m_s2:9.81,air_density_kg_m3:0,air_viscosity_pa_s:0,wind_velocity_m_s:[0,0,0],blunt_drag_coefficient:.5,contact_damping_ratio:1,gripper_force_scale:1,object_force_n:[0,0,0],object_torque_nm:[0,0,0]},object_material:'custom',schema_version:'vivacity.configuration/1.0',name:'My robotic experiment',environment_id:world,robot_id:'panda',gripper_id:'panda_parallel',operation_id:'pick_place',seed:7,
  target_position:[.5,-.15,.026],destination_position:[.5,.18,.026],object_half_sizes:[.025,.025,.025],object_mass_kg:.06,object_friction:1,
  sort_property:'mass',sort_threshold:.08,alternate_destination_position:[.5,.35,.026],trial_mode:'adaptive',validation_trials:3,randomization_cycles:1,realtime_speed:1});
