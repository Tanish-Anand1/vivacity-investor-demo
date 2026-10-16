import {useState} from 'react';
import {workspaceApi,type Run} from './workspaceApi';
import {errorMessage} from './api';
import type {components} from './generated/api';
export default function RobustnessReport({run}:{run:Run}){
 const [error,setError]=useState<string|null>(null),[comparison,setComparison]=useState<Record<string,unknown>|null>(null),[busy,setBusy]=useState(false);
 const r=run.robustness;if(!r||!Object.keys(r.partitions).some(k=>k!=='unpartitioned'))return null;
 const upload=async(file:File)=>{setBusy(true);setError(null);try{if(file.size>160*1024)throw new Error('Measurement JSON limit: 160 KiB.');
  const body=JSON.parse(await file.text()) as components['schemas']['MeasurementRequest'];setComparison(await workspaceApi.compareMeasurements(run.session_id,body));
 }catch(e){setError(errorMessage(e));}finally{setBusy(false);}};
 return <details className="robustness-report"><summary>Physical robustness · {run.session_id.slice(0,8)}</summary><table><caption>Completed configurations, evaluated from measured execution</caption><thead><tr><th>Partition</th><th>Completed</th><th>Success</th><th>Failure</th><th>Success rate</th></tr></thead><tbody>{Object.entries(r.partitions).map(([name,p])=><tr key={name}><th scope="row">{name.replaceAll('_',' ')}</th><td>{p.completed_configurations}</td><td>{p.successes}</td><td>{p.failures}</td><td>{(100*p.success_rate).toFixed(1)}%</td></tr>)}</tbody></table><p className="small">{r.scope}</p><details><summary>Failure conditions and input hashes</summary><pre className="generation-spec">{JSON.stringify(r,null,2)}</pre></details><details><summary>Compare supplied object measurements</summary><p className="small">Upload JSON containing experiment_id, branch_id, source_label, source_kind (user_recording or synthetic_reference), and samples: [&#123;time_s, position_m: [x,y,z]&#125;]. Use runtime Z-up meters. No extrapolation or automatic calibration. Source authenticity is not independently verified.</p><label>Measurement JSON<input type="file" accept=".json" disabled={busy} onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f);}}/></label>{comparison&&<pre className="generation-spec">{JSON.stringify(comparison,null,2)}</pre>}{error&&<p role="alert" className="negative">{error}</p>}</details></details>;
}
