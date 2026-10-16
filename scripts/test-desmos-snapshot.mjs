import test from 'node:test';
import assert from 'node:assert/strict';
import {parseDesmosSnapshot} from '../frontend/src/desmosSnapshot.ts';

const snapshot=JSON.stringify({
 schema_version:'vivacity.desmos-ready/1.0',run_id:'measured-run',quantity:'z',
 desmos_state:{expressions:{list:[{id:'fitted_model',latex:'y=x'}]}}
});

test('reopens an opaque calculator state for the same measured run',()=>{
 assert.deepEqual(parseDesmosSnapshot(snapshot,'measured-run','z'),{expressions:{list:[{id:'fitted_model',latex:'y=x'}]}});
});

test('rejects mismatched provenance, empty state and oversized input',()=>{
 assert.throws(()=>parseDesmosSnapshot(snapshot,'other-run','z'),/Select the saved experiment/);
 assert.throws(()=>parseDesmosSnapshot(snapshot,'measured-run','x'),/Select the measured relationship/);
 assert.throws(()=>parseDesmosSnapshot('{}','measured-run','z'),/Unsupported/);
 assert.throws(()=>parseDesmosSnapshot('{','measured-run','z'),/valid JSON/);
 assert.throws(()=>parseDesmosSnapshot(JSON.stringify({schema_version:'vivacity.desmos-ready/1.0',run_id:'measured-run',quantity:'z',desmos_state:null}),'measured-run','z'),/no editable/);
 assert.throws(()=>parseDesmosSnapshot(' '.repeat(1_048_577),'measured-run','z'),/1 MiB/);
});
