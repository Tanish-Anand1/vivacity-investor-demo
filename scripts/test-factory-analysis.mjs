import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {nearestSample,sampleValue,samplesCSV} from '../frontend/src/factoryAnalysisData.ts';
test('deployed frontend layout exactly matches the native factory layout',()=>{
 assert.equal(readFileSync(new URL('../frontend/src/generated/factory_layout.json',import.meta.url),'utf8'),readFileSync(new URL('../vivacity/factory_layout.json',import.meta.url),'utf8'));
});
const frame=time=>({time,cartons:[{id:'target',position_m:[.5,-.4,.025],linear_velocity_m_s:[.03,.04,0]}],conveyors:{infeed:{surface_speed_m_s:.09}},measurements:{objects:[{id:'target',linear_acceleration_m_s2:[0,0,-9.81],kinetic_energy_j:.000075,potential_energy_j:.485}],robot:{joint_torque_nm:[1,2,3,4,5,6,7],gripper_contact_normal_force_n:12},actuator_power_w:8,mechanical_work_j:4,positive_actuator_work_j:5}});
test('nearest cursor resolves the same recorded sample for charts and replay',()=>{const frames=[frame(0),frame(.05),frame(.1)];assert.equal(nearestSample(frames,.061),1);assert.equal(nearestSample(frames,-1),0);assert.equal(nearestSample(frames,3),2);assert.equal(nearestSample([],3),-1);});
test('engineering quantities preserve units, selected joint and missing data',()=>{const f=frame(2);assert.equal(sampleValue(f,'speed'),.05);assert.equal(sampleValue(f,'acceleration'),9.81);assert.equal(sampleValue(f,'torque','target',3),4);assert.equal(sampleValue(f,'force'),12);assert.equal(sampleValue({...f,measurements:undefined},'force'),null);});
test('throughput only counts recorded destination arrivals at selected time',()=>{const events=[{kind:'destination_arrival',time_s:10},{kind:'destination_arrival',time_s:30},{kind:'station_arrival',time_s:4}];assert.equal(sampleValue(frame(20),'completed','target',0,events),1);assert.equal(sampleValue(frame(20),'throughput','target',0,events),3);});
test('CSV preserves all samples, units, null semantics and measured values',()=>{const csv=samplesCSV([frame(0),frame(.05)],'target',0,[]);const lines=csv.split('\r\n');assert.equal(lines.length,3);assert.match(lines[0],/power \[W\]/);assert.match(lines[1],/^0,0.5,-0.4,0.025,0.05,9.81,1,12,8,4,5/);});
