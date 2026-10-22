import {useEffect,useState} from 'react';
import {errorMessage} from './api';
import {factoryApi,factoryDefaults,type FactoryCell,type FactoryRun,type FactorySettings} from './factoryApi';
import {fulfillmentApi,type FulfillmentOrder} from './fulfillmentApi';

const key='vivacity:fulfillment-order';
export default function FulfillmentPanel({cell,active,onCell,onRun}:{cell:FactoryCell;active:boolean;
  onCell:(cell:FactoryCell)=>void;onRun:(run:FactoryRun)=>void}){
  const [order,setOrder]=useState<FulfillmentOrder|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{const id=localStorage.getItem(key);if(!id)return;let live=true;
    fulfillmentApi.get(id).then(record=>{if(live)setOrder(record);}).catch(()=>{if(live)localStorage.removeItem(key);});
    return()=>{live=false;};},[]);
  useEffect(()=>{if(!order||order.status!=='sorting')return;let live=true;
    const timer=setInterval(()=>fulfillmentApi.get(order.id).then(value=>{if(live)setOrder(value);}).catch(cause=>{if(live)setError(errorMessage(cause));}),750);
    return()=>{live=false;clearInterval(timer);};},[order?.id,order?.status]);
  const create=async(settings:FactorySettings)=>{
    setBusy(true);setError('');try{
      const ids=Array.from({length:settings.carton_count},(_,i)=>`item_${i+1}`);
      const next=await fulfillmentApi.create(`${settings.carton_count}-item trial order`,ids,settings);
      localStorage.setItem(key,next.id);setOrder(next);onCell(await factoryApi.cell(next.cell_id));
    }catch(cause){setError(errorMessage(cause));}finally{setBusy(false);}
  };
  const start=async()=>{
    if(!order)return;setBusy(true);setError('');try{
      const next=await fulfillmentApi.start(order.id);setOrder(next);
      onCell(await factoryApi.cell(next.cell_id));
      if(next.run_id)onRun(await factoryApi.run(next.run_id));
    }catch(cause){setError(errorMessage(cause));}finally{setBusy(false);}
  };
  return <details className="fulfillment-panel">
    <summary>Autonomous work <span>Order → Sort → Collect → Pack → Seal → Label → Dispatch</span></summary>
    <div className="fulfillment-content">
      <p>The industrial arm sorts the order through measured contact and bin arrival. Collection, packing and shipping remain blocked until their shared-world controllers pass physical tests.</p>
      <div className="fulfillment-actions">
        <button type="button" disabled={busy||active} onClick={()=>void create({...factoryDefaults,name:'Three-item order sorting',realtime_speed:8})}>Create three-item order</button>
        <button type="button" disabled={busy||active} onClick={()=>void create(cell.config)}>Use current conditions</button>
        {order&&<button type="button" disabled={busy||active||order.status==='sorting'} onClick={()=>void start()}>{order.run_id?'Retry physical sort':'Run physical sort'}</button>}
      </div>
      {busy&&<p role="status">Preparing measured order state…</p>}
      {error&&<p role="alert" className="negative">{error}</p>}
      {order&&<>
        <p role="status">{order.order_label} · {order.sorted_count}/{order.items.length} items physically sorted · {order.status.replaceAll('_',' ')}</p>
        <ol className="fulfillment-timeline">{order.tasks.map(task=><li key={task.stage} data-state={task.status}><strong>{task.stage}</strong><span>{task.status}</span>{task.reason&&<small>{task.reason}</small>}</li>)}</ol>
        <details><summary>Item evidence and model scope</summary><ul>{order.items.map(item=><li key={item.item_id}>{item.item_id}: {item.status}{item.lane?` · bin ${item.lane} · measured ${item.mass_kg?.toFixed(3)} kg`:''}</li>)}</ul><p>{order.scope}</p><p>Order {order.id} · simulation cell {order.cell_id} · run {order.run_id??'not started'}</p></details>
      </>}
    </div>
  </details>;
}
