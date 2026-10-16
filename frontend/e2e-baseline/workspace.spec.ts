import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';
const evidence=path.resolve('../artifacts/frontend'); fs.mkdirSync(evidence,{recursive:true});
const base='http://127.0.0.1:8000';
const errors=new WeakMap<Page,string[]>();
test.beforeEach(async({page})=>{
  const problems:string[]=[]; errors.set(page,problems);
  page.on('pageerror',e=>problems.push(e.message));
  page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('ERR_FAILED')) problems.push(m.text());});
  await page.addInitScript(()=>{
    const native=window.WebSocket;
    (window as any).__testSockets=[];
    window.WebSocket=class extends native {constructor(url:string|URL,protocols?:string|string[]){super(url,protocols);(window as any).__testSockets.push(this);}};
  });
});
const id=(page:Page,lab?:string)=>page.evaluate(l=>localStorage.getItem(`vivacity:${l??localStorage.getItem('vivacity:lab')??'mujoco'}:experiment`),lab);
const worldId=(page:Page,lab='mujoco')=>page.evaluate(l=>localStorage.getItem(`vivacity:${l}:world`),lab);
async function ready(page:Page){await page.goto('/');await expect(page.getByRole('button',{name:/Run experiment/})).toBeEnabled();await expect.poll(()=>page.evaluate(()=>(window as any).__vivacityScene?.source)).toBe('measured_mujoco_frames');}
async function finished(page:Page){await expect(page.getByTestId('experiment-status')).toHaveText(/Result selected|No feasible result|Experiment failed/,{timeout:120_000});await expect(page.getByRole('button',{name:/Run experiment/})).toBeEnabled();}
async function run(page:Page){const previous=await id(page);await page.getByRole('button',{name:/Run experiment/}).click();await expect.poll(()=>id(page)).not.toBe(previous);await finished(page);return await id(page);}

test('real Panda branches, accurate replay, environment invalidation, commit/reset and all paths fail',async({page,request})=>{
  await ready(page); const start=performance.now(); const first=await run(page);
  const exp=await (await request.get(`${base}/v1/experiments/${first}`)).json();
  expect(exp.status).toBe('completed');expect(exp.selected_branch_id).toBeTruthy();
  const branches=await (await request.get(`${base}/v1/experiments/${first}/branches`)).json();
  expect(branches).toHaveLength(3);expect(branches.some((b:any)=>b.evaluation.status==='collision_failure')).toBeTruthy();
  expect(branches.some((b:any)=>b.evaluation.status==='execution_success')).toBeTruthy();
  await expect(page.getByTestId('branch-row')).toHaveCount(3);
  const success=branches.find((b:any)=>b.id===exp.selected_branch_id);
  const trace=success.trace;expect(trace.length).toBeGreaterThan(100);
  const slider=page.getByRole('slider',{name:'Replay timeline'});
  await expect(slider).toBeEnabled();await slider.focus();await slider.press('End');
  const final=trace.at(-1);
  await expect.poll(()=>page.evaluate(p=>Math.max(...p.map((v:number,i:number)=>Math.abs(v-((window as any).__vivacityScene?.endEffector?.[i]??Infinity)))),final.end_effector)).toBeLessThan(1e-9);
  for(const pose of final.body_transforms){const p=await page.evaluate(n=>({p:(window as any).__vivacityScene.bodies[n],q:(window as any).__vivacityScene.orientationsWXYZ[n]}),pose.name);p.p.forEach((v:number,i:number)=>expect(v).toBeCloseTo(pose.position[i],9));p.q.forEach((v:number,i:number)=>expect(v).toBeCloseTo(pose.quaternion_wxyz[i],9));}
  await page.screenshot({path:path.join(evidence,'robotics-success-desktop.png'),fullPage:true});
  await page.locator('[data-status="collision_failure"]').click();
  await expect(page.getByTestId('branch-evidence')).toContainText('obstacle ↔ hand');
  await page.getByRole('slider',{name:'Replay timeline'}).press('End');
  await page.screenshot({path:path.join(evidence,'robotics-collision-desktop.png'),fullPage:true});
  await page.locator('[data-status="execution_success"]').click();
  await page.getByRole('button',{name:'Play replay',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>(window as any).__vivacityScene?.time)).toBeGreaterThan(.1);
  await page.getByRole('button',{name:'Pause replay',exact:true}).click();
  await page.getByLabel('Playback speed').selectOption('2');
  await page.getByRole('button',{name:'Commit selected state'}).click();
  await expect(page.getByTestId('stale-warning')).toBeVisible();
  const w=await worldId(page);
  const state=await (await request.get(`${base}/v1/worlds/${w}/state`)).json();
  await expect.poll(()=>page.evaluate(()=>(window as any).__vivacityScene?.endEffector)).toEqual(state.observation.end_effector);
  await page.getByRole('button',{name:'Reset',exact:true}).click();
  await expect(page.getByRole('button',{name:/Run experiment/})).toBeEnabled();
  await page.getByRole('button',{name:'Change obstacle'}).click();await page.getByRole('button',{name:'Clear route',exact:true}).click();
  await page.getByRole('button',{name:'Apply & run new experiment'}).click();await finished(page);
  const second=await id(page);expect(second).not.toBe(first);
  const old=await (await request.get(`${base}/v1/experiments/${first}`)).json();expect(old.stale).toBe(true);
  const newer=await (await request.get(`${base}/v1/experiments/${second}/branches`)).json();expect(newer.every((b:any)=>b.evaluation.success)).toBe(true);
  expect(newer[0].initial_state.config.obstacle_position).toEqual([.75,-.4,.2]);
  await page.getByRole('button',{name:'Change obstacle'}).click();await page.getByRole('button',{name:'Blocked scene',exact:true}).click();await page.getByRole('button',{name:'Apply & run new experiment'}).click();await finished(page);
  await expect(page.getByTestId('experiment-status')).toHaveText('No feasible result');
  await expect(page.getByRole('button',{name:'Commit selected state'})).toHaveCount(0);
  await page.screenshot({path:path.join(evidence,'robotics-blocked.png'),fullPage:true});
  const blocked=await (await request.get(`${base}/v1/experiments/${await id(page)}`)).json();expect(blocked.selected_branch_id).toBeNull();
  fs.writeFileSync(path.join(evidence,'robotics-metrics.json'),JSON.stringify({firstExperiment:first,journeyWallMs:performance.now()-start,performance:exp.performance,frontend:await page.evaluate(()=>(window as any).__vivacityPerformance),navigation:await page.evaluate(()=>performance.getEntriesByType('navigation').map(e=>e.toJSON()))},null,2));
  expect(errors.get(page)).toEqual([]);
});

test('SciPy predictions, numerical metrics, uncertainty, timeline and rejection of unnecessary mass',async({page,request})=>{
  await ready(page);await page.getByRole('button',{name:/Discovery Lab/}).click();await expect(page.getByTestId('science-viewport')).toBeVisible();await expect(page.getByRole('button',{name:/Run experiment/})).toBeEnabled();
  const first=await run(page); const exp=await (await request.get(`${base}/v1/experiments/${await id(page,'scipy')}`)).json();
  const branches=await (await request.get(`${base}/v1/experiments/${exp.id}/branches`)).json();
  const baseline=branches.find((b:any)=>b.evaluation.hypothesis==='central_only'),extra=branches.find((b:any)=>b.evaluation.hypothesis==='central_plus_fixed_perturber');
  expect(extra.evaluation.heldout_rmse).toBeLessThan(baseline.evaluation.heldout_rmse);expect(extra.evaluation.parameters.perturbing_mass).toBeCloseTo(.12,2);expect(exp.selected_branch_id).toBe(extra.id);
  await expect(page.getByTestId('branch-evidence')).toContainText(extra.evaluation.heldout_rmse.toFixed(5));
  const w=await worldId(page,'scipy');const state=await (await request.get(`${base}/v1/worlds/${w}/state`)).json();
  expect(state.observation.config.hidden_mass).toBeUndefined();expect(state.observation.config.central_mu).toBeUndefined();
  const paths=await page.locator('.orbit-chart>path').evaluateAll(elements=>elements.map(el=>el.getAttribute('d')));
  expect(paths).toHaveLength(2);expect(paths[0]).not.toBe(paths[1]);expect(extra.trace).toHaveLength(state.observation.times.length);
  const all=[...state.observation.observations,...branches.flatMap((b:any)=>b.trace.map((f:any)=>f.predicted_position))];const scale=175/Math.max(1.25,...all.flat().map(Math.abs));
  branches.forEach((b:any,i:number)=>expect(paths[i]).toBe(b.trace.map((f:any,k:number)=>`${k?'L':'M'}${350+f.predicted_position[0]*scale},${230-f.predicted_position[1]*scale}`).join(' ')));
  await page.getByRole('slider',{name:'Replay timeline'}).focus();await page.getByRole('slider',{name:'Replay timeline'}).press('End');await expect(page.getByTestId('scientific-time-marker')).toBeVisible();
  await page.getByLabel('Show fitted influence').check();await page.screenshot({path:path.join(evidence,'discovery-supported-desktop.png'),fullPage:true});
  await page.getByText('Fitted parameters & uncertainty',{exact:true}).click();await expect(page.getByTestId('branch-evidence')).toContainText(extra.evaluation.parameters.perturbing_mass.toFixed(5));
  await page.getByRole('button',{name:'Observation settings',exact:true}).click();await page.getByLabel('Observation scenario').selectOption('control');await page.getByRole('button',{name:'Apply & run new experiment'}).click();await finished(page);
  const control=await (await request.get(`${base}/v1/experiments/${await id(page,'scipy')}`)).json();
  const nullBranches=await (await request.get(`${base}/v1/experiments/${control.id}/branches`)).json();expect(nullBranches.find((b:any)=>b.id===control.selected_branch_id).evaluation.hypothesis).toBe('central_only');
  await page.screenshot({path:path.join(evidence,'discovery-control.png'),fullPage:true});
  await page.reload();await expect(page.getByTestId('experiment-status')).toHaveText('Result selected');expect(await id(page,'scipy')).toBe(control.id);
  await page.getByText('Technical inspector',{exact:true}).click();await page.getByRole('button',{name:/Experiment 1/}).click();await expect.poll(()=>id(page,'scipy')).toBe(exp.id);
  await expect(page.getByTestId('stale-warning')).toBeVisible();
  await page.getByLabel('Show fitted influence').uncheck();
  await expect.poll(()=>page.locator('.orbit-chart>path').first().getAttribute('d')).toBe(paths[0]);
  const observed=await page.locator('.orbit-chart>circle').nth(state.observation.observations.length+1).evaluate(el=>[Number(el.getAttribute('cx')),Number(el.getAttribute('cy'))]);
  const archivedLast=state.observation.observations.at(-1);expect(observed[0]).toBeCloseTo(350+archivedLast[0]*scale,9);expect(observed[1]).toBeCloseTo(230-archivedLast[1]*scale,9);
  fs.writeFileSync(path.join(evidence,'science-metrics.json'),JSON.stringify({perturbed:exp,control,branches:branches.map((b:any)=>({id:b.id,evaluation:b.evaluation,performance:b.performance}))},null,2));
  expect(errors.get(page)).toEqual([]);
});

test('lost HTTP submission response retries the same real job and preserves one history entry',async({page,request})=>{
  await ready(page);let lost=false;const keys:string[]=[];
  await page.route('http://127.0.0.1:8000/v1/worlds/*/experiments',async route=>{
    keys.push(route.request().headers()['idempotency-key']);
    if(!lost){lost=true;const response=await route.fetch();expect(response.status()).toBe(202);await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('button',{name:/Run experiment/}).click();await expect(page.getByRole('alert')).toContainText('Failed to fetch');
  await page.getByRole('button',{name:'Retry submission',exact:true}).click();await finished(page);
  expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);
  const w=await worldId(page);const world=await (await request.get(`${base}/v1/worlds/${w}`)).json();expect(world.history).toHaveLength(1);expect(world.history[0]).toBe(await id(page));
  fs.writeFileSync(path.join(evidence,'lost-response-retry.json'),JSON.stringify({world:w,experiment:await id(page),submissionKeys:keys,history:world.history},null,2));
  expect(errors.get(page)).toEqual([]);
});

test('duplicate-click guard, live WebSocket reconnect, refresh/history and repeated experiments',async({page,request})=>{
  await ready(page);let submissions=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/experiments'))submissions++;});
  await page.getByRole('button',{name:/Run experiment/}).evaluate((button:HTMLButtonElement)=>{button.click();button.click();});
  await expect.poll(()=>page.evaluate(()=>(window as any).__testSockets.length)).toBeGreaterThan(0);
  await expect.poll(()=>page.evaluate(()=>{const job=localStorage.getItem('vivacity:mujoco:experiment');return Number(localStorage.getItem(`vivacity:cursor:${job}`)??0);})).toBeGreaterThan(0);
  await page.evaluate(()=>(window as any).__testSockets.at(-1).close());
  await expect.poll(()=>page.evaluate(()=>(window as any).__testSockets.length)).toBeGreaterThan(1);
  await finished(page);expect(submissions).toBe(1);const first=await id(page);
  await page.reload();await expect(page.getByTestId('branch-row')).toHaveCount(3);expect(await id(page)).toBe(first);
  const next=await run(page);expect(next).not.toBe(first);
  const w=await worldId(page);const world=await (await request.get(`${base}/v1/worlds/${w}`)).json();expect(world.history).toHaveLength(2);
  await page.getByText('Technical inspector',{exact:true}).click();await page.getByRole('button',{name:/Experiment 1/}).click();await expect.poll(()=>id(page)).toBe(first);await expect(page.getByTestId('branch-row')).toHaveCount(3);
  fs.writeFileSync(path.join(evidence,'reconnection.json'),JSON.stringify({submissions,world:w,history:world.history,reloadedExperiment:first,websocketMessages:await page.evaluate(()=>(window as any).__testSockets.map((s:WebSocket)=>({url:s.url,state:s.readyState})))},null,2));
  expect(errors.get(page)).toEqual([]);
});

test('measures load, scene readiness and sustained measured replay frame timing',async({page,request})=>{
  await ready(page);await run(page);await expect(page.getByRole('slider',{name:'Replay timeline'})).toBeEnabled();
  await page.getByRole('button',{name:'Play replay',exact:true}).click();
  await expect(page.getByRole('button',{name:'Play replay',exact:true})).toBeVisible({timeout:30_000});
  const frontend=await page.evaluate(()=>({renderer:(window as any).__vivacityPerformance,navigation:performance.getEntriesByType('navigation').map(e=>e.toJSON()),paint:performance.getEntriesByType('paint').map(e=>e.toJSON()),marks:performance.getEntriesByType('mark').filter(e=>e.name.startsWith('vivacity:')).map(e=>e.toJSON()),userAgent:navigator.userAgent}));
  expect(frontend.renderer.playbackFrameSamples).toBeGreaterThan(30);
  const experiment=await (await request.get(`${base}/v1/experiments/${await id(page)}`)).json();
  fs.writeFileSync(path.join(evidence,'performance.json'),JSON.stringify({frontend,experiment:experiment.id,backend:experiment.performance,scope:'Local Chromium software rendering; rolling last 180 playback intervals. Navigation load excludes later asynchronous model/mesh fetches. Not a production capacity benchmark.'},null,2));
  expect(errors.get(page)).toEqual([]);
});

test('responsive layout, keyboard controls, reduced motion, offline state and accessibility scan',async({page})=>{
  await ready(page);await page.emulateMedia({reducedMotion:'reduce'});
  const camera=await page.evaluate(()=>(window as any).__vivacityScene.cameraPosition);
  await page.getByTestId('robot-viewport').focus();await page.keyboard.press('ArrowRight');
  await expect.poll(()=>page.evaluate(()=>(window as any).__vivacityScene.cameraPosition)).not.toEqual(camera);
  await page.keyboard.press('+');await page.getByRole('button',{name:'Reset camera',exact:true}).click();
  await expect.poll(()=>page.evaluate(p=>Math.max(...p.map((v:number,i:number)=>Math.abs(v-(window as any).__vivacityScene.cameraPosition[i]))),camera)).toBeLessThan(1e-9);
  const scans=[];
  for(const width of [1440,768,375]){
    await page.setViewportSize({width,height:width===375?900:1080});
    await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:path.join(evidence,`workspace-${width}.png`),fullPage:true});
    const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
    scans.push({width,violations:results.violations});expect(results.violations).toEqual([]);
  }
  await page.keyboard.press('Tab');await expect(page.locator(':focus')).toBeVisible();
  await page.getByRole('button',{name:'Change obstacle'}).focus();await page.keyboard.press('Enter');await expect(page.getByRole('slider',{name:'X obstacle position'})).toBeVisible();
  await page.getByRole('slider',{name:'X obstacle position'}).focus();const before=await page.getByRole('slider',{name:'X obstacle position'}).inputValue();await page.keyboard.press('ArrowRight');expect(await page.getByRole('slider',{name:'X obstacle position'}).inputValue()).not.toBe(before);
  await page.getByRole('button',{name:'Close settings'}).click();
  await page.route('http://127.0.0.1:8000/**',route=>route.abort());
  await expect(page.getByText('Runtime offline',{exact:true})).toBeVisible({timeout:15_000});await expect(page.getByRole('button',{name:/Run experiment/})).toBeDisabled();
  await page.screenshot({path:path.join(evidence,'offline-mobile.png'),fullPage:true});
  await page.unroute('http://127.0.0.1:8000/**');await page.getByRole('button',{name:'Reconnect',exact:true}).click();await expect(page.getByRole('button',{name:/Run experiment/})).toBeEnabled();
  fs.writeFileSync(path.join(evidence,'accessibility.json'),JSON.stringify(scans,null,2));expect(errors.get(page)).toEqual([]);
});
