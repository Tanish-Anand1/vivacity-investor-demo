import {useState} from 'react';
import {factoryApi,type FactoryImport} from './factoryApi';
import {errorMessage} from './api';

export function saveFactoryJSON(value:unknown,name:string){
 const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export async function downloadFactoryReport(kind:'run'|'benchmark',id:string,format:'pdf'|'zip',projectId?:string){
 const blob=await factoryApi.report(kind,id,format,projectId),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`vivacity-${id}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export default function FactoryExchange({cellId,runId,disabled,onImport}:{cellId:string;runId?:string;disabled:boolean;onImport:(value:FactoryImport)=>void}){
 const [error,setError]=useState<string|null>(null),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 async function action(fn:()=>Promise<void>){setBusy(true);setError(null);setMessage('');try{await fn();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}
 return <details className="factory-readout factory-exchange"><summary>Reproduce & export</summary><p>Configuration and benchmark files preserve units, versions, physical settings and seeds. Import prepares an idle cell. Run it to obtain new measured results.</p>
  <fieldset disabled={disabled||busy} className="factory-file-controls"><legend>Versioned files</legend><div className="factory-file-actions">
   <button onClick={()=>action(async()=>saveFactoryJSON(await factoryApi.exportConfiguration(cellId),'vivacity-configuration.json'))}>Download configuration</button>
   {runId&&<button onClick={()=>action(async()=>saveFactoryJSON(await factoryApi.exportRecord(runId),'vivacity-run-'+runId+'.json'))}>Download complete run</button>}
   {runId&&<><button onClick={()=>action(()=>downloadFactoryReport('run',runId,'pdf'))}>Download engineering PDF</button><button onClick={()=>action(()=>downloadFactoryReport('run',runId,'zip'))}>Download evidence ZIP</button></>}
   <label>Import configuration or benchmark<input type="file" accept=".json,application/json" onChange={e=>{const file=e.target.files?.[0];if(!file)return;action(async()=>{if(file.size>262144)throw new Error('Configuration files must be 256 KiB or smaller. Raw result archives are inspection-only.');const value=await factoryApi.importConfiguration(JSON.parse(await file.text()));onImport(value);setMessage(value.message);});e.target.value='';}}/></label>
  </div></fieldset>{error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  <p className="factory-stage-note">Complete run files include all saved samples, full integration states, events and metrics. They are inspection archives; import accepts reproducible configuration and benchmark definitions. Imported files are retained as provenance, never promoted to verified results.</p>
 </details>;
}
