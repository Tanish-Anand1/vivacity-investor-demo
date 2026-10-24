import {useEffect,useRef,useState} from 'react';
import {api,errorMessage,type EditorEntity,type EditorProperty,type WorldEditor,type WorldVersion} from './api';
import type {World} from './domain';
import Settings from './Settings';

type Action='add'|'duplicate'|'delete';
type Props={world:World;selected:string;select:(id:string)=>void;disabled:boolean;
  editProperty:(entity:string,key:string,value:number|boolean|string)=>Promise<boolean>;
  editGeometry:(action:Action,entity?:string,kind?:'box'|'cylinder')=>Promise<boolean>;
  restoreVersion:(revision:number)=>Promise<boolean>;
  apply:(config:Record<string,unknown>)=>Promise<boolean|void>;close:()=>void};

function PropertyField({entity,property,disabled,commit}:{entity:EditorEntity;property:EditorProperty;disabled:boolean;commit:(entity:string,key:string,value:number|boolean|string)=>Promise<boolean>}){
  const display=(value:EditorProperty['value'])=>property.data_type==='boolean'?Boolean(value):
    typeof value==='number'?String(Number(value.toPrecision(6))):String(value??'');
  const [draft,setDraft]=useState<string|boolean>(()=>display(property.value));
  const [saving,setSaving]=useState(false),[error,setError]=useState('');
  useEffect(()=>{setDraft(display(property.value));setError('');},[property.value]);
  const changed=property.data_type==='boolean'?draft!==property.value:property.data_type==='number'?
    property.value===null?String(draft).trim()!=='':Math.abs(Number(draft)-Number(property.value))>1e-6:
    String(draft)!==String(property.value??'');
  const number=Number(draft);
  const invalid=property.data_type==='number'&&(String(draft).trim()===''||!Number.isFinite(number)||
    (property.minimum!==null&&number<property.minimum)||(property.maximum!==null&&number>property.maximum));
  const save=async()=>{
    if(invalid||!changed||disabled)return;
    setSaving(true);setError('');
    const value=property.data_type==='number'?Number(draft):draft;
    const okay=await commit(entity.id,property.key,value);
    if(!okay)setError('The physical change was rejected. Check the range or reload the latest world version.');
    setSaving(false);
  };
  const id=`physical-${entity.id.replaceAll(':','-')}-${property.key}`;
  return <div className="physical-property">
    <label htmlFor={id}>{property.label}{property.unit&&<span>{property.unit}</span>}</label>
    <div className="physical-property-input">
      {property.data_type==='boolean'?<input id={id} type="checkbox" checked={Boolean(draft)} disabled={disabled||!property.editable} onChange={event=>setDraft(event.target.checked)}/>:
        property.data_type==='choice'?<select id={id} value={String(draft)} disabled={disabled||!property.editable} onChange={event=>setDraft(event.target.value)}>{property.choices.map(choice=><option key={choice} value={choice}>{choice.replaceAll('_',' ')}</option>)}</select>:
          <input id={id} type="number" inputMode="decimal" min={property.minimum??undefined} max={property.maximum??undefined} step="any" value={draft as string} placeholder={property.value===null?'Not set':undefined} disabled={disabled||!property.editable} onChange={event=>setDraft(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();void save();}}}/>}
      {property.editable&&<button type="button" disabled={disabled||saving||!changed||invalid} onClick={()=>void save()}>{saving?'Applying…':'Apply'}</button>}
    </div>
    <p>{property.meaning}</p>
    {changed&&property.editable&&<small>Applying resets the simulation and creates a new world version.</small>}
    <details><summary>Physics dependency</summary><p>{property.dependency} {property.physics_effect}</p></details>
    {error&&<p role="alert" className="negative">{error}</p>}
  </div>;
}

export default function PhysicalWorldEditor({world,selected,select,disabled,editProperty,editGeometry,restoreVersion,apply,close}:Props){
  const [editor,setEditor]=useState<WorldEditor|null>(null),[versions,setVersions]=useState<WorldVersion[]>([]);
  const [loading,setLoading]=useState(true),[error,setError]=useState('');
  const [undo,setUndo]=useState<number[]>([]),[redo,setRedo]=useState<number[]>([]);
  const previousRevision=useRef(world.revision),skipRevision=useRef(false);
  const [busy,setBusy]=useState(false);
  useEffect(()=>{
    const prior=previousRevision.current;
    if(prior===world.revision)return;
    previousRevision.current=world.revision;
    if(skipRevision.current){skipRevision.current=false;return;}
    setUndo(stack=>[...stack,prior]);setRedo([]);
  },[world.revision]);
  useEffect(()=>{
    let active=true;setLoading(true);setError('');
    Promise.all([api.editor(world.id),api.worldVersions(world.id)]).then(([schema,history])=>{
      if(!active)return;setEditor(schema);setVersions(history);setLoading(false);
      if(!schema.entities.some(entity=>entity.id===selected))select(schema.entities[0]?.id??'object');
    }).catch(cause=>{if(active){setError(errorMessage(cause));setLoading(false);}});
    return()=>{active=false;};
  },[world.id,world.revision]);
  const entity=editor?.entities.find(item=>item.id===selected)??editor?.entities[0];
  const record=()=>{setUndo(stack=>[...stack,world.revision]);setRedo([]);};
  const change=async(entityId:string,key:string,value:number|boolean|string)=>{
    skipRevision.current=true;
    const okay=await editProperty(entityId,key,value);
    if(okay)record();else skipRevision.current=false;
    return okay;
  };
  const geometry=async(action:Action,kind:'box'|'cylinder'='box')=>{
    setBusy(true);setError('');
    skipRevision.current=true;
    const okay=await editGeometry(action,action==='add'?undefined:selected,kind);
    if(okay){record();if(action==='delete')select('object');}
    else {skipRevision.current=false;setError('The geometry edit was rejected by the runtime. Check the world state and try again.');}
    setBusy(false);
  };
  const restore=async(target:number,direction:'undo'|'redo'|'history')=>{
    setBusy(true);setError('');skipRevision.current=true;const okay=await restoreVersion(target);
    if(okay){
      if(direction==='undo'){setUndo(stack=>stack.slice(0,-1));setRedo(stack=>[...stack,world.revision]);}
      else if(direction==='redo'){setRedo(stack=>stack.slice(0,-1));setUndo(stack=>[...stack,world.revision]);}
      else record();
    }else {skipRevision.current=false;setError('The saved version could not be restored. Reload the world and try again.');}
    setBusy(false);
  };
  const exportWorld=()=>{
    const definition={schema_version:'vivacity.world_definition/1.0',id:world.id,revision:world.revision,
      backend:world.backend,simulator_version:world.simulator_version,seed:world.seed,config:world.config,
      initial_state:world.initial_state};
    const url=URL.createObjectURL(new Blob([JSON.stringify(definition,null,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download=`vivacity-world-${world.id}-v${world.revision}.json`;link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  return <section className="physical-world-editor" aria-labelledby="physical-editor-heading">
    <div className="section-heading"><h2 id="physical-editor-heading">Physical world editor</h2><button type="button" className="icon-button" onClick={close} aria-label="Close world editor">×</button></div>
    <p className="small">World version {world.revision}. Each applied edit rebuilds the physical scene and makes prior experiment results stale.</p>
    {loading&&<p role="status">Loading supported physical properties…</p>}
    {error&&<p className="negative" role="alert">{error}</p>}
    {editor&&<>
      <label className="physical-select">Inspect
        <select value={entity?.id??''} onChange={event=>select(event.target.value)}>
          {editor.entities.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      {entity&&<div className="physical-fields" key={world.revision+'-'+entity.id}>
        <h3>{entity.name}</h3>
        {entity.properties.map(property=><PropertyField key={property.key} entity={entity} property={property} disabled={disabled||busy} commit={change}/>)}
        {entity.id.startsWith('geometry:')&&<div className="physical-actions"><button type="button" disabled={disabled||busy} onClick={()=>void geometry('duplicate')}>Duplicate</button><button type="button" disabled={disabled||busy} onClick={()=>void geometry('delete')}>Delete primitive</button></div>}
      </div>}
      <div className="physical-actions"><button type="button" disabled={disabled||busy||editor.entities.length>=29} onClick={()=>void geometry('add','box')}>Add box</button><button type="button" disabled={disabled||busy||editor.entities.length>=29} onClick={()=>void geometry('add','cylinder')}>Add cylinder</button></div>
      <div className="physical-actions"><button type="button" disabled={disabled||busy||!undo.length} onClick={()=>void restore(undo.at(-1)!,'undo')}>Undo</button><button type="button" disabled={disabled||busy||!redo.length} onClick={()=>void restore(redo.at(-1)!,'redo')}>Redo</button><button type="button" onClick={exportWorld}>Export world</button></div>
      <details className="physical-history"><summary>Saved physical versions ({versions.length})</summary><ol>{versions.slice(0,16).map(version=><li key={version.revision}><span>v{version.revision} · {version.reason.replaceAll('_',' ')}</span><button type="button" disabled={disabled||busy||version.revision===world.revision} onClick={()=>void restore(version.revision,'history')}>Restore</button></li>)}</ol></details>
      <details className="physical-advanced"><summary>Task coordinates and advanced conditions</summary><Settings key={world.id+'-'+world.revision} config={world.config} disabled={disabled||busy} apply={apply} close={close}/></details>
      <p className="small">{editor.scope}</p>
    </>}
  </section>;
}
