import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {changeSelection} from '../frontend/src/templateSelection.ts';

const catalog = JSON.parse(readFileSync(new URL('../frontend/src/generated/templates.json', import.meta.url), 'utf8'));
const initial = {arm:'panda', world:'manufacturing', task:'pick_place'};
const worlds = ['manufacturing', 'warehouse', 'inspection', 'cluttered'];
const combinations = catalog.arms.filter(a=>a.status!=='reference').flatMap(arm=>worlds.flatMap(world => ['pick_place', 'obstacle_transfer','assembly','machine_tending'].map(task => ({arm:arm.id,world,task}))));
combinations.push({arm:'panda',world:'textile',task:'cloth_fold'});
const key = s => `${s.arm}:${s.world}:${s.task}`;
const supported = new Set(combinations.map(key));

test('all catalog interactions preserve executable robot/world/task combinations', () => {
  let count = 0;
  for (const current of combinations) {
    for (const [field, options] of [['arm',catalog.arms], ['world',catalog.worlds], ['task',catalog.tasks]]) {
      for (const option of options) {
        const before = {...current};
        const next = changeSelection(current, field, option.id, catalog);
        assert.ok(supported.has(key(next)), `${key(current)} -> ${field}=${option.id}: ${key(next)}`);
        assert.deepEqual(current, before, 'existing loaded selection must not be mutated');
        count++;
      }
    }
  }
  assert.equal(count, combinations.length*15);
});

test('unimplemented and unknown choices cannot replace a working selection', () => {
  for (const [field, options] of [['arm',catalog.arms], ['task',catalog.tasks]]) {
    for (const option of options.filter(o => o.status === 'reference')) {
      assert.equal(changeSelection(initial, field, option.id, catalog), initial);
    }
  }
  assert.equal(changeSelection(initial, 'world', 'unknown', catalog), initial);
});

test('choosing textile or folding pairs both selections immediately', () => {
  const expected = {arm:'panda',world:'textile',task:'cloth_fold'};
  assert.deepEqual(changeSelection(initial, 'world', 'textile', catalog), expected);
  assert.deepEqual(changeSelection(initial, 'task', 'cloth_fold', catalog), expected);
});

test('leaving textile selects a compatible rigid handling configuration', () => {
  const cloth = combinations.at(-1);
  assert.deepEqual(changeSelection(cloth, 'world', 'warehouse', catalog), {...initial,world:'warehouse'});
  assert.deepEqual(changeSelection(cloth, 'task', 'obstacle_transfer', catalog), {...initial,task:'obstacle_transfer'});
});

test('compatible customization preserves the chosen rigid world and task', () => {
  const obstacle = {...initial,task:'obstacle_transfer'};
  assert.deepEqual(changeSelection(obstacle, 'world', 'inspection', catalog), {...obstacle,world:'inspection'});
  const warehouse = {...initial,world:'warehouse'};
  assert.deepEqual(changeSelection(warehouse, 'task', 'obstacle_transfer', catalog), {...warehouse,task:'obstacle_transfer'});
});
