// Real REST, WebSocket and browser physics. The first run verifies the configured
// deployed budget (5,000 locally, eight on Render Free); the second uses eight.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
process.chdir(path.resolve(import.meta.dirname,'..'));
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');
process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const {AxeBuilder}=await import('../frontend/node_modules/@axe-core/playwright/dist/index.mjs');
const url=process.env.UI_URL??'http://127.0.0.1:5175/';
const api=process.env.API_URL??'http://127.0.0.1:8002';
const prefix=process.env.PROOF_PREFIX??'pause-local';
const expectedTrials=Number(process.env.EXPECTED_PHYSICS_TRIALS??5000);
const labsOnly=process.env.VERIFY_LABS_ONLY==='1';
const verifyTimeout=Number(process.env.VERIFY_TIMEOUT_MS??360000);
assert(Number.isFinite(verifyTimeout)&&verifyTimeout>=360000&&verifyTimeout<=1800000);
const proof={url,api,checks:[],errors:[],requests:[],sessions:[],live_messages:0,event_messages:0,started_unix_s:Date.now()/1000,scope:labsOnly?'cloth_science_browser':'all_labs_browser'};
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
let page,current,token,sessionPosts=0,bounded=false;
async function get(route){
  for(let attempt=0;attempt<3;attempt++){
    try{
      const r=await fetch(api+route,{headers:{'X-Session-Token':token},signal:AbortSignal.timeout(120000)});
      assert.equal(r.status,200,route);return await r.json();
    }catch(error){
      // Retry only transport failures of idempotent reads. A failed assertion,
      // HTTP status or JSON contract must still fail the verification.
      if(!(error instanceof TypeError)||attempt===2)throw error;
      (proof.transport_retries??=[]).push({route,attempt:attempt+1,error:error.cause?.code??error.message});
      await new Promise(resolve=>setTimeout(resolve,500*(attempt+1)));
    }
  }
}
async function until(fn,timeout=verifyTimeout){const end=Date.now()+timeout;while(Date.now()<end){const v=await fn();if(v)return v;await page.waitForTimeout(200);}throw Error('Measured condition timed out');}
async function stored(backend){const value=await page.evaluate(b=>({id:localStorage.getItem(`vivacity:${b}:session`),token:localStorage.getItem(`vivacity:${b}:token`)}),backend);if(!value.id||!value.token)return null;current=value.id;token=value.token;return get(`/v1/sessions/${current}`);}
async function session(){return get(`/v1/sessions/${current}`);}
async function pause(){
  await page.getByRole('button',{name:'Pause simulation',exact:true}).click();
  const s=await until(async()=>{const v=await session();return v.paused&&v;});
  await page.getByTestId('experiment-status').getByText('Simulation paused',{exact:true}).waitFor({timeout:15000});
  return s;
}
async function resume(){await page.getByRole('button',{name:'Resume simulation',exact:true}).click();await until(async()=>!(await session()).pause_requested);}
async function frozen(eid,name){
  const a=await get(`/v1/experiments/${eid}/live`);
  await page.waitForTimeout(1000);
  assert.deepEqual(await get(`/v1/experiments/${eid}/live`),a);
  proof.checks.push(name);return a;
}
try{
  const context=await browser.newContext({viewport:{width:1440,height:960},reducedMotion:'reduce'});
  page=await context.newPage();page.on('pageerror',e=>proof.errors.push(e.message));
  page.on('websocket',socket=>socket.on('framereceived',({payload})=>{try{const m=JSON.parse(String(payload));if(m.schema_version==='vivacity.live/1.0')proof.live_messages++;else if(m.schema_version==='1.0')proof.event_messages++;}catch{}}));
  await page.route(`${api}/v1/sessions`,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    const body=route.request().postDataJSON();proof.requests.push(body);sessionPosts++;
    body.max_cycles=1;
    if(bounded&&body.backend==='mujoco'){body.physics_trials=8;body.search_candidates=8;}
    // Fast SciPy fits can finish before the UI receives session creation over
    // a public proxy. Pause immediately through the real endpoint, then let
    // the browser exercise Resume. Never wait for a completed fit to pause.
    if(body.backend==='scipy'){
      const response=await route.fetch({postData:JSON.stringify(body)});
      assert.equal(response.status(),201);
      const created=await response.json();
      const capability=route.request().headers()['x-session-token'];
      const pauseResponse=await fetch(`${api}/v1/sessions/${created.id}/pause`,{method:'POST',headers:{'X-Session-Token':capability}});
      assert.equal(pauseResponse.status,200);
      await route.fulfill({response});return;
    }
    await route.continue({postData:JSON.stringify(body)});
  });
  await page.goto(url,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__vivacityScene?.bodies?.target,{timeout:60000});
  await page.waitForTimeout(4000);assert.equal(sessionPosts,0);
  proof.checks.push('page_load_has_no_automatic_experiments');
  await page.screenshot({path:`artifacts/${prefix}-idle.png`,fullPage:true});
  if(!labsOnly){
  await page.getByRole('button',{name:'Start experiments',exact:true}).click();
  await until(()=>stored('mujoco').then(s=>s?.experiment_id&&s));
  const s=await session(),eid=s.experiment_id;
  assert.equal(proof.requests[0].physics_trials,expectedTrials);assert.equal(proof.requests[0].search_candidates,expectedTrials);
  // This journey tests worker control, not throughput. The independent audit
  // executes all 5,000 trials. Two measured trials are sufficient to establish
  // progress before pause on slow machines running the browser and API together.
  await until(async()=>{const e=await get(`/v1/experiments/${eid}`);return e.result.search?.fully_simulated>=2;});
  await pause();const pausedFrame=await frozen(eid,'pause_freezes_native_simulator_state');
  const pausedExperiment=await get(`/v1/experiments/${eid}`),count=pausedExperiment.result.search.fully_simulated;
  await page.waitForTimeout(700);assert.equal((await get(`/v1/experiments/${eid}`)).result.search.fully_simulated,count);
  await page.screenshot({path:`artifacts/${prefix}-paused.png`,fullPage:true});
  const poses=await page.evaluate(()=>window.__vivacityScene.bodies);
  await page.getByTestId('robot-viewport').focus();const camera=await page.evaluate(()=>window.__vivacityScene.cameraPosition);
  await page.keyboard.press('ArrowRight');await page.waitForFunction(before=>JSON.stringify(window.__vivacityScene.cameraPosition)!==JSON.stringify(before),camera);
  assert.deepEqual(await page.evaluate(()=>window.__vivacityScene.bodies),poses);
  await resume();await until(async()=>{const e=await get(`/v1/experiments/${eid}`);return e.result.search.fully_simulated>=count+2;});
  assert.equal((await session()).experiment_id,eid);assert.equal((await session()).world_id,s.world_id);
  const trials=await get(`/v1/experiments/${eid}/trials?limit=100`);
  assert(trials.completed>=count+2&&trials.items.every(t=>t.performance.simulation_steps>0));
  await page.getByRole('button',{name:'Stop experiments',exact:true}).click();
  await until(async()=>{const s=await session();return s.status==='stopped';});
  assert.equal((await get(`/v1/experiments/${eid}`)).status,'cancelled');
  proof.sessions.push({id:current,experiment_id:eid,default_trials_requested:expectedTrials,actual_trials_before_stop:trials.completed,paused_frame:pausedFrame});
  proof.checks.push('resume_continues_same_world_and_experiment','native_trials_record_real_states','stop_cancels_paused_or_running_work','camera_remains_interactive_while_paused');
  console.log(`Configured ${expectedTrials}-trial request: real pause, resume, measured trials and stop passed.`);
  bounded=true;
  await page.getByRole('button',{name:'Start experiments',exact:true}).click();
  await until(async()=>{const s=await stored('mujoco');return s?.experiment_id&&s.id!==proof.sessions[0].id&&s;});
  const executing=await session();
  await until(async()=>(await session()).status==='completed');
  const completed=await get(`/v1/experiments/${executing.experiment_id}`);
  proof.pickup_completed=completed;
  assert.equal(completed.performance.trial_count,8);assert(completed.result.execution_evaluation.success);
  const branches=await get(`/v1/experiments/${completed.id}/branches`);
  assert(branches.some(b=>b.id===completed.result.execution_branch_id&&b.performance.simulation_steps>1000));
  await page.getByTestId('branch-row').first().waitFor({timeout:30000});
  const downloadEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Download JSON for result 1',exact:true}).click();
  const download=await downloadEvent;await download.saveAs(`artifacts/${prefix}-branch.json`);
  const exported=JSON.parse(fs.readFileSync(`artifacts/${prefix}-branch.json`));assert(exported.success&&exported.recorded_frames.length>10);
  proof.checks.push('bounded_eight_trial_run_and_fresh_execution_complete','verified_branch_export_contains_actual_frames');
  proof.sessions.push({id:current,experiment_id:completed.id,actual_trials:8,execution:completed.result.execution_evaluation});
  console.log('Eight full trials, successful fresh physics execution and actual replay export passed.');
  // Settings remain idle until the next explicit click.
  await page.getByRole('button',{name:'Change conditions',exact:true}).click();
  await page.getByRole('button',{name:'Clear route',exact:true}).click();await page.getByRole('button',{name:'Apply settings',exact:true}).click();
  const posts=sessionPosts;await page.waitForTimeout(1500);assert.equal(sessionPosts,posts);
  proof.checks.push('changing_conditions_does_not_start_work');
  }
  const labPosts=sessionPosts;
  await page.getByRole('button',{name:'Cloth Folding',exact:true}).click();
  await page.getByRole('button',{name:'Start experiments',exact:true}).waitFor();await page.waitForTimeout(1500);assert.equal(sessionPosts,labPosts);
  await page.getByRole('button',{name:'Start experiments',exact:true}).click({timeout:120000});
  await until(async()=>{const s=await stored('cloth');if(!s?.experiment_id)return false;const l=await get(`/v1/experiments/${s.experiment_id}/live`);return l?.stage==='executing'&&s;},verifyTimeout);
  const cloth=await session();console.log('Cloth validation finished; testing real worker Pause/Resume and fresh fold.');await pause();await frozen(cloth.experiment_id,'pause_freezes_actual_cloth_vertices_and_robot');await resume();
  await until(async()=>(await session()).status==='completed');
  const clothExperiment=await get(`/v1/experiments/${cloth.experiment_id}`);assert(clothExperiment.result.execution_evaluation.success);
  assert.equal(clothExperiment.result.search.fully_simulated,3);
  proof.sessions.push({id:current,backend:'cloth',experiment_id:cloth.experiment_id,physics_validation_trials:3,execution:clothExperiment.result.execution_evaluation});
  console.log('Three real cloth validations and fresh physical fold passed.');
  await page.getByRole('button',{name:'Discovery',exact:true}).click();
  await page.getByRole('button',{name:'Start experiments',exact:true}).waitFor();await page.waitForTimeout(1500);
  const beforeScience=sessionPosts;
  await page.getByRole('button',{name:'Start experiments',exact:true}).click();await until(()=>stored('scipy'));
  await until(async()=>{const s=await session();return s.paused&&s;});
  await page.getByRole('button',{name:'Resume simulation',exact:true}).waitFor({timeout:15000});
  await page.waitForTimeout(500);assert((await session()).paused);
  await resume();await until(async()=>(await session()).status==='completed');
  const sciSession=await session(),scientific=await get(`/v1/experiments/${sciSession.experiment_id}`);
  const hypotheses=await get(`/v1/experiments/${scientific.id}/branches`);
  assert(hypotheses.every(b=>b.performance.integration_calls>0&&Number.isFinite(b.evaluation.heldout_rmse)));
  proof.sessions.push({id:current,backend:'scipy',experiment_id:scientific.id,hypotheses:hypotheses.map(b=>({evaluation:b.evaluation,performance:b.performance}))});
  assert.equal(sessionPosts,beforeScience+1);
  proof.checks.push('science_pause_resume_keeps_real_numerical_fits','lab_switches_remain_idle');
  await page.reload({waitUntil:'domcontentloaded'});await page.getByTestId('branch-row').first().waitFor({timeout:60000});
  await page.waitForTimeout(1500);assert.equal(sessionPosts,beforeScience+1);proof.checks.push('reload_does_not_restart');
  for(const width of [768,375]){await page.setViewportSize({width,height:960});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.equal(await page.getByRole('slider',{name:/Replay|Playback/}).count(),0);
  assert.equal(await page.getByRole('log').count(),1);
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();proof.axe_violations=axe.violations;assert.equal(axe.violations.length,0);
  assert(proof.live_messages>10&&proof.event_messages>5);assert.deepEqual(proof.errors,[]);
  proof.checks.push('desktop_mobile_and_accessibility_checks','live_websockets_deliver_actual_frames_and_events','no_video_timeline_or_speed_controls');proof.status='passed';
  console.log(JSON.stringify({status:proof.status,checks:proof.checks,live_messages:proof.live_messages,event_messages:proof.event_messages}));
}catch(e){proof.status='failed';proof.failure=e.message;
  if(page){proof.final_page=await page.locator('body').innerText().catch(()=>null);await page.screenshot({path:`artifacts/${prefix}-failure.png`,fullPage:true}).catch(()=>{});}
  throw e;}
finally{
  if(current&&token){try{await fetch(`${api}/v1/sessions/${current}/stop`,{method:'POST',headers:{'X-Session-Token':token}});}catch{}}
  proof.finished_unix_s=Date.now()/1000;fs.writeFileSync(`artifacts/${prefix}.json`,JSON.stringify(proof,null,2));await browser.close();
}
