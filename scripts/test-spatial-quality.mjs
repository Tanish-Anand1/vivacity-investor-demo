import assert from 'node:assert/strict';
import test from 'node:test';
import {defaultQuality,visualStages,qualityProfiles} from '../frontend/src/renderQuality.ts';
test('device resources determine a bounded initial rendering budget',()=>{
 assert.equal(defaultQuality(4,8),'performance');assert.equal(defaultQuality(8,4),'performance');assert.equal(defaultQuality(8,8),'balanced');assert.equal(defaultQuality(),'balanced');
 assert.ok(qualityProfiles.high.splats<=500000);
});
test('progressive loading chooses supported representations without full-resolution downloads',()=>{
 assert.deepEqual(visualStages('performance',['100k','500k']),['100k']);
 assert.deepEqual(visualStages('balanced',['100k','500k']),['100k','500k']);
 assert.deepEqual(visualStages('high',['500k']),['500k']);
});
