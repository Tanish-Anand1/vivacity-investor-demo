// Real requests prove page loads/settings never submit experiments. No mocked results.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
process.chdir(path.resolve(import.meta.dirname,'..'));
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');
process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const ui=process.env.UI_URL??'http://127.0.0.1:5173/';
const api=process.env.API_URL??'http://127.0.0.1:8000';
const prefix=process.env.PROOF_PREFIX??'manual-start-local';
const proof={url:ui,api,checks:[],errors:[],sessions:[],started_unix_s:Date.now()/1000};
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
let sessionPosts=0,experimentPosts=0;
try{
  const context=await browser.newContext({viewport:{width:1440,height:960},reducedMotion:'reduce'});
  const page=await context.newPage();
  page.on('pageerror',e=>proof.errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST'&&r.url()===`${api}/v1/sessions`)sessionPosts++;
    if(r.method()==='POST'&&/\/worlds\/[^/]+\/experiments$/.test(r.url()))experimentPosts++;});
  // Bound cycle count and the new exhaustive pickup mode for this smoke test.
  // The dedicated physics-5000 audit executes all 5,000 real trials.
  await page.route(`${api}/v1/sessions`,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    const body=route.request().postDataJSON();body.max_cycles=1;
    if(body.backend==='mujoco'&&body.physics_trials){body.physics_trials=8;body.search_candidates=8;}
    await route.continue({postData:JSON.stringify(body)});
  });
  const ready=()=>page.getByRole('button',{name:'Start experiments',exact:true}).waitFor({timeout:60000});
  const enabled=()=>page.waitForFunction(()=>{const b=document.querySelector('.run-button');return b&&!b.disabled&&b.textContent.includes('Start experiments');},null,{timeout:60000});
  const idle=async(name,delay=2200)=>{
    await ready();await enabled();const before=sessionPosts;
    await page.waitForTimeout(delay);assert.equal(sessionPosts,before,`${name} auto-started`);assert.equal(experimentPosts,0);
    proof.checks.push(name);console.log(`${name}: passed`);
  };
  async function stored(backend){return page.evaluate(b=>({id:localStorage.getItem(`vivacity:${b}:session`),token:localStorage.getItem(`vivacity:${b}:token`)}),backend);}
  async function get(route,token){const r=await fetch(api+route,{headers:{'X-Session-Token':token}});assert.equal(r.status,200,route);return r.json();}
  async function complete(backend){
    await page.waitForFunction(b=>localStorage.getItem(`vivacity:${b}:session`),backend,{timeout:60000});
    const {id,token}=await stored(backend);let session;
    const until=Date.now()+360000;
    do{session=await get(`/v1/sessions/${id}`,token);if(!['active','stopping'].includes(session.status))break;await page.waitForTimeout(750);}while(Date.now()<until);
    assert.equal(session.status,'completed',JSON.stringify(session));assert.equal(session.experiments.length,1);
    const experiment=await get(`/v1/experiments/${session.experiments[0]}`,token);
    assert.equal(experiment.status,'completed');
    const branches=await get(`/v1/experiments/${experiment.id}/branches`,token);
    await page.getByTestId('branch-row').first().waitFor({timeout:60000});await enabled();
    proof.sessions.push({id,backend,experiment_id:experiment.id,result:experiment.result,
      branches:branches.map(b=>({id:b.id,evaluation:b.evaluation,performance:b.performance}))});
    return {session,experiment,branches};
  }
  await page.goto(ui,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__vivacityScene?.bodies?.target,{timeout:60000});
  await idle('robotics_load_waits_for_click',10000);assert.equal(sessionPosts,0);
  await page.screenshot({path:`artifacts/${prefix}-idle.png`,fullPage:true});
  await page.getByRole('button',{name:'Change conditions',exact:true}).click();
  await page.getByRole('button',{name:'Clear route',exact:true}).click();
  await page.getByRole('button',{name:'Apply settings',exact:true}).click();
  await idle('robotics_apply_does_not_run');
  await page.reload({waitUntil:'domcontentloaded'});await idle('idle_reload_does_not_run');
  await page.getByRole('button',{name:'Cloth Folding',exact:true}).click();await idle('cloth_switch_does_not_run');
  await page.getByRole('button',{name:'Cloth settings',exact:true}).click();
  await page.getByRole('button',{name:'Apply settings',exact:true}).click();await idle('cloth_apply_does_not_run');
  await page.getByRole('button',{name:'Discovery',exact:true}).click();await idle('discovery_switch_does_not_run');
  await page.getByRole('button',{name:'Observation settings',exact:true}).click();
  await page.getByLabel('Observation scenario',{exact:true}).selectOption('control');
  await page.getByRole('button',{name:'Apply settings',exact:true}).click();await idle('discovery_apply_does_not_run');
  await page.reload({waitUntil:'domcontentloaded'});await idle('staged_science_settings_survive_idle_reload');
  assert.equal(sessionPosts,0);
  await page.getByRole('button',{name:'Start experiments',exact:true}).click();
  const science=await complete('scipy');assert.equal(sessionPosts,1);
  assert(science.branches.every(b=>b.performance.integration_calls>0));
  assert.equal(science.branches.find(b=>b.id===science.experiment.selected_branch_id).evaluation.hypothesis,'central_only');
  proof.checks.push('explicit_click_computes_real_scipy_control');
  await page.reload({waitUntil:'domcontentloaded'});await idle('completed_reload_does_not_run');assert.equal(sessionPosts,1);
  await page.getByRole('button',{name:'Robotics',exact:true}).click();await idle('return_to_robotics_does_not_run');
  await page.setViewportSize({width:768,height:960});
  await page.getByRole('button',{name:'Start experiments',exact:true}).click();
  const robot=await complete('mujoco');assert.equal(sessionPosts,2);
  assert.equal(robot.experiment.result.search.distinct_generated,8);
  assert.equal(robot.experiment.result.search.fully_simulated,8);
  assert(robot.experiment.result.execution_evaluation.success);
  assert.equal(robot.branches.length,4);
  proof.checks.push('explicit_click_computes_real_pickup_and_fresh_execution');
  await page.getByRole('button',{name:'Start experiments',exact:true}).click();
  await page.waitForFunction(old=>localStorage.getItem('vivacity:mujoco:session')!==old,robot.session.id,{timeout:60000});
  const active=await stored('mujoco');
  await page.reload({waitUntil:'domcontentloaded'});await idle('active_reload_stops_instead_of_resuming');
  let stopped;const stopDeadline=Date.now()+60000;
  do{stopped=await get(`/v1/sessions/${active.id}`,active.token);if(stopped.status==='stopped')break;await page.waitForTimeout(250);}while(Date.now()<stopDeadline);
  assert.equal(stopped.status,'stopped');assert.equal(sessionPosts,3);
  proof.checks.push('active_session_is_actually_stopped_on_reload');
  await page.setViewportSize({width:375,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  proof.checks.push('mobile_layout_preserved');assert.deepEqual(proof.errors,[]);
  proof.session_posts=sessionPosts;proof.experiment_posts=experimentPosts;proof.status='passed';
  console.log(JSON.stringify({status:proof.status,checks:proof.checks,session_posts:sessionPosts,page_errors:proof.errors}));
}catch(error){proof.status='failed';proof.failure=error.message;throw error;}
finally{proof.finished_unix_s=Date.now()/1000;fs.writeFileSync(`artifacts/${prefix}.json`,JSON.stringify(proof,null,2));await browser.close();}
