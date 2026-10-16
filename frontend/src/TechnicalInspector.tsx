import { useEffect, useRef } from 'react';
import { format, type Branch, type Event } from './domain';

function describe(event:Event){
  const d=event.details;
  switch(event.kind){
    case 'queued':return 'Experiment submitted. Independent parent state preserved.';
    case 'running':return 'Candidate generation started. Deterministic planning policy.';
    case 'planned':return `${d.followup?'Additional planning':'Planning'} complete: ${d.candidate_count} validation candidates; ${format(d.planning_wall_seconds,2)} s.`;
    case 'progress':return String(d.message??`${d.stage}: generated ${d.generated??0}, screened ${d.screened??0}, rejected ${d.rejected??0}.`);
    case 'branch_completed':{
      const e=d.evaluation as Branch['evaluation'];
      if(e.milestone==='constrained_single_fold')return `Flex validation: ${e.status.replaceAll('_',' ')}; alignment ${format((e.alignment_error_m??0)*1000,2)} mm; vertex coverage ${format((e.vertex_coverage??0)*100,1)}%; clamp constraints ${e.grasp_valid?'valid':'failed'}.`;
      return `Physics validation: ${e.status.replaceAll('_',' ')}; goal ${format(typeof e.goal_error_m==='number'?e.goal_error_m*1000:undefined,1)} mm; ${e.contact_violations?.length??0} prohibited contacts.`;
    }
    case 'completed':return d.selected_branch_id?'Ranking completed. Best measured candidate selected.':'Evaluation completed. No supported candidate; failures retained.';
    case 'failed':return `Experiment error: ${String(d.error??'See recorded evaluation')}.`;
    case 'cancelled':return 'Experiment stopped safely. Completed measured evidence is retained.';
  }
}
function failureLabel(branch:Branch){
  const status=branch.evaluation.status.replaceAll('_',' '),contacts=branch.evaluation.contact_violations??[];
  const pairs=[...new Set(contacts.map(c=>[...c.bodies].sort().join(' ↔ ')))];
  return contacts.length?`${status} · ${contacts.length} contacts · ${pairs.slice(0,3).join(', ')}${pairs.length>3?` (+${pairs.length-3} pairs)`:''}`:status;
}
export default function TechnicalInspector({events,initialized,playing,branches,select,history,initialMessage}:{events:Event[];initialized:boolean;playing:boolean;branches:Branch[];select:(id:string)=>void;history:{ids:string[];open:(id:string)=>void;disabled:boolean};initialMessage?:string}){
  const log=useRef<HTMLDivElement>(null),follow=useRef(true);
  const origin=Number(events[0]?.details.timestamp_unix_s??0);
  useEffect(()=>{if(log.current&&follow.current)log.current.scrollTop=log.current.scrollHeight;},[events,playing,initialized]);
  return <details className="inspector"><summary>Execution log & recorded evidence</summary>
    <div ref={log} className="event-log" role="log" aria-label="Measured execution events" aria-live="polite" aria-relevant="additions" tabIndex={0} onScroll={()=>{const el=log.current;if(el)follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<30;}}>
      <p>{initialMessage??(initialized?'World initialized. Actual state restored.':'Initializing world…')}</p>
      {events.map(event=>{const elapsed=origin?Number(event.details.timestamp_unix_s??origin)-origin:Number(event.details.elapsed_seconds??0);return <p key={event.seq} className={event.kind==='failed'?'negative':''}><time>[{Math.floor(elapsed/60).toString().padStart(2,'0')}:{(elapsed%60).toFixed(2).padStart(5,'0')}]</time> {describe(event)}</p>;})}
    </div>
    <details className="recorded-evidence"><summary>Recorded failures & history</summary><div className="evidence-links">{branches.filter(b=>!b.evaluation.success).map(b=><button key={b.id} onClick={()=>select(b.id)} data-status={b.evaluation.status}>{failureLabel(b)}</button>)}{history.ids.map((id,i)=><button key={id} disabled={history.disabled} onClick={()=>history.open(id)}>Experiment {i+1}</button>)}</div></details>
  </details>;
}
