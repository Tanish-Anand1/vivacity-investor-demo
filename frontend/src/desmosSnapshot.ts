/** Validate the Vivacity envelope; Desmos calculator state itself stays opaque. */
export function parseDesmosSnapshot(text:string,runId:string,quantity:string):unknown{
 if(text.length>1_048_576)throw new Error('Snapshot exceeds the 1 MiB import limit.');
 let value:unknown;
 try{value=JSON.parse(text);}catch{throw new Error('Snapshot is not valid JSON.');}
 if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Snapshot must be a Vivacity analysis object.');
 const record=value as Record<string,unknown>;
 if(record.schema_version!=='vivacity.desmos-ready/1.0')throw new Error('Unsupported analysis snapshot version.');
 if(record.run_id!==runId)throw new Error('Select the saved experiment named in this snapshot before reopening it.');
 if(record.quantity!==quantity)throw new Error('Select the measured relationship named in this snapshot before reopening it.');
 if(!record.desmos_state||typeof record.desmos_state!=='object'||Array.isArray(record.desmos_state))throw new Error('This snapshot has no editable Desmos state.');
 return record.desmos_state;
}
