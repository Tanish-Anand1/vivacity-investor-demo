import test from 'node:test';
import assert from 'node:assert/strict';
import {desmosNumber} from '../frontend/src/desmosNumber.ts';

test('Desmos parameters retain tiny finite values without exponent notation',()=>{
 assert.equal(desmosNumber(9.5970419e-7),'0.00000095970419');
 assert.equal(desmosNumber(-6.1660221e-5),'-0.000061660221');
 assert.equal(desmosNumber(2.5e8),'250000000');
 assert.equal(desmosNumber(0.025),'0.025');
 assert.throws(()=>desmosNumber(NaN),RangeError);
});
