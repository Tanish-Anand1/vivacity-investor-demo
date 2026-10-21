import type { Backend, World, Experiment, Branch, Replay, Dict, Event } from './domain';
import type { components } from './generated/api';

import {fetchRuntime,runtimeEndpoints,runtimeSocketURL} from './apiTransport';
const endpoints=runtimeEndpoints(import.meta.env.PROD,import.meta.env.VITE_API_BASE_URL,window.location.origin);
export const API=endpoints.http;
export const BACKEND=endpoints.backend;
let sessionToken: string | null = null;
export function setSessionToken(token: string) { sessionToken = token; }
export function liveProtocols() { return sessionToken ? ['vivacity.live', `vivacity.token.${sessionToken}`] : []; }
export {APIError} from './apiResponse';
import {APIError,readAPIResponse} from './apiResponse';
type ValidationIssue = { msg?: unknown; loc?: unknown; type?: unknown };
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (sessionToken && !headers.has('X-Session-Token')) headers.set('X-Session-Token',sessionToken);
  const response = await fetchRuntime(API + path, {...init,headers});
  // JSON null is a valid response from the optional cached live-frame route.
  return await readAPIResponse(response) as T;
}
const json = (method: string, body?: object, headers: Record<string,string> = {}): RequestInit => ({
  method, headers: body ? { 'Content-Type': 'application/json', ...headers } : headers,
  ...(body ? { body: JSON.stringify(body) } : {})
});
const defaultConfig = (backend: Backend): Dict | undefined => backend==='mujoco'
  ? {task:'pick_place',obstacle_enabled:false,obstacle_position:[.75,-.4,.22]} : undefined;
export const api = {
  createSession: async (backend: Backend, token: string, config?: Dict) => {
    const health=await request<{limits?:{max_physics_trials:number}}>('/health');
    const computeBudget=Math.min(health.limits?.max_physics_trials??12,12);
    return request<components['schemas']['SessionResponse']>('/v1/sessions',json('POST',{
      backend,seed:7,max_cycles:1,realtime_execution:true,
      adaptive_trials:backend==='mujoco',physics_trials:0,
      search_candidates:backend==='mujoco'?256:5000,
      physics_budget:backend==='mujoco'?computeBudget:3,
      config:config??defaultConfig(backend)
    },{'X-Session-Token':token}));
  },
  session: (id:string) => request<components['schemas']['SessionResponse']>(`/v1/sessions/${encodeURIComponent(id)}`),
  stopSession: (id:string) => request<components['schemas']['SessionResponse']>(`/v1/sessions/${encodeURIComponent(id)}/stop`,json('POST')),
  pauseSession: (id:string) => request<components['schemas']['SessionResponse']>(`/v1/sessions/${encodeURIComponent(id)}/pause`,json('POST')),
  resumeSession: (id:string) => request<components['schemas']['SessionResponse']>(`/v1/sessions/${encodeURIComponent(id)}/resume`,json('POST')),
  live: (id:string) => request<components['schemas']['LiveState']|null>(`/v1/experiments/${encodeURIComponent(id)}/live`),
  resolveTemplate: (selection:{arm:string;world:string;task:string}) => request<components['schemas']['CreateWorld']>('/v1/templates/resolve',json('POST',selection)),
  health: () => request<{ status: string; backends: Record<string,string>; limits?: {max_physics_trials:number} }>('/health'),
  create: (backend: Backend, config = defaultConfig(backend)) => request<World>('/v1/worlds', json('POST', { backend, seed: 7, config })),
  world: (id: string) => request<World>(`/v1/worlds/${encodeURIComponent(id)}`),
  state: (id: string) => request<components['schemas']['StateResponse']>(`/v1/worlds/${encodeURIComponent(id)}/state`),
  submit: (id: string, key: string, settings: Dict) => request<Experiment>(`/v1/worlds/${id}/experiments`, json('POST', settings, { 'Idempotency-Key': key })),
  experiment: (id: string) => request<Experiment>(`/v1/experiments/${encodeURIComponent(id)}`),
  cancel: (id: string) => request<Experiment>(`/v1/experiments/${encodeURIComponent(id)}/cancel`,json('POST')),
  branches: (id: string) => request<Branch[]>(`/v1/experiments/${encodeURIComponent(id)}/branches`),
  events: (id: string, after=0) => request<Event[]>(`/v1/experiments/${encodeURIComponent(id)}/events?after=${after}`),
  download:async(eid:string,bid:string)=>{
    const response=await fetchRuntime(`${API}/v1/experiments/${encodeURIComponent(eid)}/branches/${encodeURIComponent(bid)}/export`,{headers:sessionToken?{'X-Session-Token':sessionToken}:{}});
    if(!response.ok)throw new APIError(response.status,(await response.json()).detail);
    const data=await response.json();
    if(data.schema_version!=='vivacity.branch/1.0'||data.branch_id!==bid||!Array.isArray(data.recorded_frames))throw new Error('Invalid branch export');
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`vivacity-${bid}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  },
  replay: (id: string) => request<Replay>(`/v1/experiments/${encodeURIComponent(id)}/replay`),
  environment: (id: string, config: Dict) => request<World>(`/v1/worlds/${id}/environment`, json('PATCH', { config })),
  reset: (id: string) => request<World>(`/v1/worlds/${id}/reset`, json('POST')),
  commit: (id: string, experiment_id: string, branch_id: string) => request<World>(`/v1/worlds/${id}/commit`, json('POST', { experiment_id, branch_id })),
};
export function websocketURL(id: string, after: number) {
  return runtimeSocketURL(BACKEND,id,'events',after);
}
export function liveWebsocketURL(id:string) {
  return runtimeSocketURL(BACKEND,id,'live');
}
export function errorMessage(error: unknown) {
  if (error instanceof APIError) {
    if (Array.isArray(error.detail)) {
      const issues=error.detail as ValidationIssue[];
      const relevant=issues.find(issue=>Array.isArray(issue.loc)&&issue.loc.includes('RoboticsConfig')&&issue.type==='value_error')
        ??issues.find(issue=>issue.type==='value_error')??issues[0];
      const message=typeof relevant?.msg==='string'?relevant.msg.replace(/^Value error,\s*/,''):'Check the scene settings and try again.';
      return `${error.status}: ${message}`;
    }
    if(typeof error.detail==='string')return `${error.status}: ${error.detail}`;
    return `${error.status}: The simulation request was rejected. Check the scene settings and try again.`;
  }
  return error instanceof Error ? error.message : String(error);
}
