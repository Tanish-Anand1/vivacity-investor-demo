import {API} from './api';
import {fetchRuntime} from './apiTransport';
import {readAPIResponse} from './apiResponse';
import {workspaceToken} from './workspaceApi';
import type {FactorySettings} from './factoryApi';

export type FulfillmentOrder={schema_version:'vivacity.fulfillment-order/1.0';id:string;order_label:string;
  created_unix_s:number;cell_id:string;run_id:string|null;attempts:string[];settings:FactorySettings;initial_state_hash:string;
  status:'ready'|'sorting'|'sort_completed'|'failed';sorted_count:number;
  items:{item_id:string;carton_id:string;status:'pending'|'sorted';lane:string|null;mass_kg:number|null;verified_simulation_time_s:number|null}[];
  tasks:{stage:string;status:string;reason:string|null}[];metrics:Record<string,unknown>;
  events:Record<string,unknown>[];scope:string};

async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{
  const response=await fetchRuntime(API+'/v1/fulfillment'+path,{method,
    headers:{'X-Workspace-Token':workspaceToken(),...(body===undefined?{}:{'Content-Type':'application/json'})},
    ...(body===undefined?{}:{body:JSON.stringify(body)})});
  return await readAPIResponse(response) as T;
}
export const fulfillmentApi={
  create:(order_label:string,item_ids:string[],settings:FactorySettings)=>request<FulfillmentOrder>('/orders','POST',{order_label,item_ids,settings}),
  get:(id:string)=>request<FulfillmentOrder>('/orders/'+encodeURIComponent(id)),
  start:(id:string)=>request<FulfillmentOrder>('/orders/'+encodeURIComponent(id)+'/start','POST'),
  list:()=>request<FulfillmentOrder[]>('/orders'),
};
