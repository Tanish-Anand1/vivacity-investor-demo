import test from 'node:test';
import assert from 'node:assert/strict';
import {readAPIResponse,APIError} from '../frontend/src/apiResponse.ts';
import {incompatibleSnapshotReference} from '../frontend/src/runtimeRecovery.ts';
test('a restored experiment may have an explicitly null live frame',async()=>assert.equal(await readAPIResponse(new Response('null',{status:200})),null));
test('valid measured objects are preserved',async()=>assert.deepEqual(await readAPIResponse(new Response('{"steps":50}',{status:200})),{steps:50}));
test('invalid JSON is not treated as an empty live state',async()=>assert.rejects(()=>readAPIResponse(new Response('broken',{status:200})),e=>e instanceof APIError&&e.status===200&&e.message.includes('unreadable')));
test('HTTP validation errors retain their structured detail',async()=>assert.rejects(()=>readAPIResponse(new Response('{"detail":[{"msg":"bound failed"}]}',{status:422})),e=>e instanceof APIError&&e.status===422&&e.detail[0].msg==='bound failed'));
test('only a saved, incompatible physics snapshot triggers fresh-world recovery',()=>{
  assert.equal(incompatibleSnapshotReference(new APIError(422,'snapshot model/version mismatch')),true);
  assert.equal(incompatibleSnapshotReference(new APIError(422,'snapshot model/version mismatch'),false),false);
  assert.equal(incompatibleSnapshotReference(new APIError(422,'invalid gravity')),false);
});
