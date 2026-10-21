import {useEffect,useState} from 'react';
import type {components} from './generated/api';
import {api,errorMessage} from './api';
import './precisionAssemblyResult.css';

type Report=components['schemas']['RoboticsExperimentReport'];
type Measurements={success?:boolean;status?:string;goal_error_m?:number;alignment_error_rad?:number;seated?:boolean;grasp_established?:boolean;retained_during_transport?:boolean;released?:boolean;peak_actuator_scalar?:Record<string,number>;execution_duration_s?:number};

export default function PrecisionAssemblyResult({experimentId,stale}:{experimentId:string;stale:boolean}){
  const [report,setReport]=useState<Report|null>(null);
  const [error,setError]=useState<string|null>(null);
  const [loading,setLoading]=useState(true);
  useEffect(()=>{let active=true;setLoading(true);setReport(null);setError(null);
    api.roboticsReport(experimentId).then(value=>{if(active)setReport(value);}).catch(e=>{if(active)setError(errorMessage(e));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[experimentId,stale]);
  const evaluation=(report?.measurements.evaluation??{}) as Measurements;
  const performance=(report?.measurements.performance??{}) as {simulation_steps?:number};
  const efforts=Object.entries(evaluation.peak_actuator_scalar??{});
  const download=()=>{if(!report)return;const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`v-robotics-${experimentId}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  return <section className="precision-result" aria-labelledby="precision-result-heading"><h3 id="precision-result-heading">Precision assembly verification</h3>
    {loading&&<p role="status">Reading persisted physics measurements…</p>}
    {error&&<p role="alert">{error}</p>}
    {report&&<><p role="status">{report.validation_status==='verified'?'Fixture seating verified in simulation':report.validation_status==='failed'?'No verified placement':'Experiment incomplete'}{report.stale||stale?' · Previous world version':''}</p>
      <dl><div><dt>Placement error</dt><dd>{typeof evaluation.goal_error_m==='number'?(evaluation.goal_error_m*1000).toFixed(2)+' mm':'Unavailable'}</dd></div><div><dt>Orientation error</dt><dd>{typeof evaluation.alignment_error_rad==='number'?evaluation.alignment_error_rad.toFixed(4)+' rad':'Unavailable'}</dd></div><div><dt>Grasp / retention</dt><dd>{evaluation.grasp_established&&evaluation.retained_during_transport?'Both measured':evaluation.grasp_established?'Grasp only':'Not established'}</dd></div><div><dt>Physics steps</dt><dd>{performance.simulation_steps?.toLocaleString()??'Unavailable'}</dd></div><div><dt>Termination</dt><dd>{report.termination_reason?.replaceAll('_',' ')??'Pending'}</dd></div></dl>
      {efforts.length>0&&<details><summary>Peak actuator output</summary><dl>{efforts.map(([name,value])=><div key={name}><dt>{name.replaceAll('_',' ')}</dt><dd>{value.toFixed(3)}</dd></div>)}</dl><p>Scalar outputs sampled by the physics solver at every step. Units depend on each actuator transmission; gripper output is not combined with joint torque.</p></details>}
      <button className="secondary" type="button" onClick={download}>Export verification record</button><p>Simulation evidence only. This task uses a modeled gripper fixture and has not been validated on hardware.</p></>}
  </section>;
}
