import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
process.chdir(path.resolve(import.meta.dirname,'..'));
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');
process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const {AxeBuilder}=await import('../frontend/node_modules/@axe-core/playwright/dist/index.mjs');
const ui=process.env.UI_URL??'http://127.0.0.1:5173/';
const base=process.env.API_URL??'http://127.0.0.1:8000';
const prefix=process.env.PROOF_PREFIX??'master-live';
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const proof={url:ui,api:base,started_unix_s:Date.now()/1000,checks:[],errors:[],sessions:[],state_messages:0,event_messages:0};
let page,capability,latestSession,conditionCheck=false;const liveFrames=[];
async function request(route){const response=await fetch(base+route,{headers:{'X-Session-Token':capability}});assert.equal(response.status,200,route);return response.json();}
async function complete(backend,expectRows=true){
  const key=`robotics-v2:${backend}:panda:${backend==='cloth'?'textile:cloth_fold':'manufacturing:pick_place'}`;
  await page.waitForFunction(key=>localStorage.getItem(`vivacity:${key}:session`),key,{timeout:60000});
  const stored=await page.evaluate(key=>({id:localStorage.getItem(`vivacity:${key}:session`),token:localStorage.getItem(`vivacity:${key}:token`)}),key);
  capability=stored.token;
  const deadline=Date.now()+600000;
  while(Date.now()<deadline){latestSession=await request(`/v1/sessions/${stored.id}`);if(!['active','stopping'].includes(latestSession.status))break;await new Promise(resolve=>setTimeout(resolve,1000));}
  assert.equal(latestSession.status,'completed',JSON.stringify(latestSession));
  if(expectRows)await page.getByTestId('branch-row').first().waitFor({timeout:60000});
  proof.sessions.push(latestSession);
  const experiments=[];
  for(const eid of latestSession.experiments){const experiment=await request(`/v1/experiments/${eid}`),branches=await request(`/v1/experiments/${eid}/branches`);experiments.push({experiment,branches});}
  return experiments;
}
try{
  const context=await browser.newContext({viewport:{width:1440,height:960},reducedMotion:'reduce'});
  page=await context.newPage();
  page.on('pageerror',e=>proof.errors.push(e.message));
  page.on('websocket',socket=>socket.on('framereceived',({payload})=>{try{const message=JSON.parse(String(payload));if(message.schema_version==='vivacity.live/1.0'){proof.state_messages++;if(message.stage==='executing')proof.live_message_example??=message;liveFrames.push(message);if(liveFrames.length>1500)liveFrames.shift();}else if(message.schema_version==='1.0'){proof.event_messages++;proof.event_message_examples??={};proof.event_message_examples[message.kind]??=message;}}catch{/* Ignore protocol control frames. */}}));
  // Exercise two actual cycles per lab, with bounded presentation wait. This
  // changes only requested cycle count; every result still comes from the server.
  await page.route(`${base}/v1/sessions`,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    const body=route.request().postDataJSON();body.max_cycles=body.backend==='cloth'||conditionCheck?1:2;
    if(body.backend==='mujoco'&&body.physics_trials){body.physics_trials=8;body.search_candidates=8;}
    await route.continue({postData:JSON.stringify(body)});
  });
  await page.goto(ui,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__vivacityScene?.bodies?.target,{timeout:60000});
  assert.equal(await page.getByRole('slider',{name:/Replay|Playback/}).count(),0);
  assert.equal(await page.getByRole('button',{name:/Play video|Pause video|Resume motion/}).count(),0);
  assert.equal(await page.getByRole('log').count(),1);
  assert.equal(await page.getByRole('radio').count(),15);
  assert.equal(await page.getByRole('button',{name:'Discovery',exact:true}).count(),0);
  await page.getByRole('radio',{name:/UR5e collaborative arm/}).check();
  assert(await page.getByRole('button',{name:'Adapter required',exact:true}).isDisabled());
  await page.getByRole('radio',{name:/Franka Panda 7 joint/}).check();
  proof.checks.push('five_choices_in_each_category','unsupported_arm_cannot_launch','discovery_removed');
  await page.getByRole('button',{name:'Start experiments',exact:true}).click();
  const robot=await complete('mujoco');
  assert.equal(robot.length,2);assert.notEqual(robot[0].experiment.world_id,robot[1].experiment.world_id);
  for(const {experiment,branches} of robot){
    assert.equal(experiment.result.search.distinct_generated,256);
    assert(experiment.result.search.fully_simulated>0&&experiment.result.search.fully_simulated<=8);
    assert(experiment.result.execution_evaluation.success);
    assert.equal(branches.length,4);
    const execution=branches.find(b=>b.id===experiment.result.execution_branch_id);
    assert.equal(execution.action.execution_role,'authoritative_execution');
    assert(execution.performance.simulation_steps>1000);
  }
  assert.notDeepEqual(robot[0].branches[0].initial_state.config.cube_position,robot[1].branches[0].initial_state.config.cube_position);
  const final=robot.at(-1),executed=final.branches.find(b=>b.id===final.experiment.result.execution_branch_id);
  await page.waitForFunction(poses=>poses.every(p=>window.__vivacityScene?.bodies[p.name]&&Math.max(...p.position.map((v,i)=>Math.abs(v-window.__vivacityScene.bodies[p.name][i])))<1e-8),executed.trace.at(-1).body_transforms,{timeout:60000});
  assert.equal(await page.getByTestId('branch-row').count(),3);
  const before=await page.evaluate(()=>window.__vivacityScene.bodies.target);
  await page.getByTestId('branch-row').nth(1).click();
  assert.deepEqual(await page.evaluate(()=>window.__vivacityScene.bodies.target),before);
  for(let i=0;i<3;i++){
    const event=page.waitForEvent('download');await page.getByRole('button',{name:`Download JSON for result ${i+1}`,exact:true}).click();
    const download=await event,file=`artifacts/${prefix}-pickup-${i+1}.json`;await download.saveAs(file);
    const data=JSON.parse(fs.readFileSync(file));assert(data.success&&data.evaluation.grasp_established&&data.evaluation.released);
    assert.equal(data.world_type,'physical_pick_and_place');assert(Array.isArray(data.recorded_frames));
    assert(!JSON.stringify(data).includes(capability));
  }
  const cameraBefore=await page.evaluate(()=>window.__vivacityScene.cameraPosition);
  await page.getByTestId('robot-viewport').focus();await page.keyboard.press('ArrowRight');
  await page.waitForFunction(before=>JSON.stringify(window.__vivacityScene.cameraPosition)!==JSON.stringify(before),cameraBefore);
  proof.checks.push('two_fresh_pickup_cycles','actual_adaptive_physics_trials_per_cycle','full_validation_rollouts_plus_fresh_execution','exact_live_body_poses','selection_does_not_replay','three_parsed_exports','keyboard_camera','no_video_controls','one_inspector');
  console.log('Two real pickup cycles, live poses, downloads, camera and no-video UI passed.');
  await page.screenshot({path:`artifacts/${prefix}-robotics.png`,fullPage:true});
  for(const width of [768,375]){await page.setViewportSize({width,height:960});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.screenshot({path:`artifacts/${prefix}-mobile.png`,fullPage:true});
  await page.setViewportSize({width:1440,height:960});
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();proof.axe_violations=axe.violations;assert.equal(axe.violations.length,0);
  if(process.env.CHECK_CONDITIONS==='1'){
    conditionCheck=true;
    const oldSession=latestSession.id,oldCapability=capability;
    await page.getByRole('button',{name:'Change conditions',exact:true}).click();
    await page.getByRole('button',{name:'Blocked scene',exact:true}).click();
    await page.getByRole('button',{name:'Apply settings',exact:true}).click();
    await page.getByRole('button',{name:'Start experiments',exact:true}).click();
    await page.waitForFunction(id=>localStorage.getItem('vivacity:robotics-v2:mujoco:panda:manufacturing:pick_place:session')!==id,oldSession,{timeout:60000});
    const blocked=await complete('mujoco',false);
    assert.equal(blocked.length,1);assert.equal(blocked[0].experiment.selected_branch_id,null);
    assert(!blocked[0].branches.some(b=>b.evaluation.success));
    await page.getByText('No feasible candidate. Measured failures are retained below.',{exact:true}).waitFor();
    const staleResponse=await fetch(`${base}/v1/experiments/${final.experiment.id}`,{headers:{'X-Session-Token':oldCapability}});
    assert.equal(staleResponse.status,200);assert((await staleResponse.json()).stale);
    const staleReplay=await fetch(`${base}/v1/experiments/${final.experiment.id}/replay`,{headers:{'X-Session-Token':oldCapability}});
    assert.equal(staleReplay.status,200);assert((await staleReplay.json()).stale);
    await page.screenshot({path:`artifacts/${prefix}-blocked.png`,fullPage:true});
    const blockedSession=latestSession.id;
    await page.getByRole('button',{name:'Change conditions',exact:true}).click();
    await page.getByRole('button',{name:'Clear route',exact:true}).click();
    await page.getByRole('button',{name:'Apply settings',exact:true}).click();
    await page.getByRole('button',{name:'Start experiments',exact:true}).click();
    await page.waitForFunction(id=>localStorage.getItem('vivacity:robotics-v2:mujoco:panda:manufacturing:pick_place:session')!==id,blockedSession,{timeout:60000});
    const cleared=await complete('mujoco');assert(cleared[0].experiment.result.execution_evaluation.success);
    assert.notEqual(cleared[0].branches[0].initial_state.model_hash,blocked[0].branches[0].initial_state.model_hash);
    proof.checks.push('obstacle_change_invalidates_results_and_replay','honest_all_paths_fail_ui','clear_route_computes_new_success');
    conditionCheck=false;console.log('Blocked obstacle, stale records and fresh clear-route execution passed.');
  }
  if(process.env.SKIP_CLOTH!=='1'){
    await page.getByRole('button',{name:'Robotics',exact:true}).click();
    if(await page.getByRole('button',{name:'Choose templates',exact:true}).isVisible())await page.getByRole('button',{name:'Choose templates',exact:true}).click();
    await page.getByRole('radio',{name:/Textile folding station/}).check();
    await page.getByRole('radio',{name:/Cloth folding Joint-actuated/}).check();
    await page.getByRole('button',{name:'Load this template',exact:true}).click();
    await page.getByRole('button',{name:'Start experiments',exact:true}).waitFor();
    await page.getByRole('button',{name:'Start experiments',exact:true}).click();
    const cloth=await complete('cloth'),e=cloth[0].experiment,b=cloth[0].branches.find(b=>b.id===e.result.execution_branch_id);
    assert(e.result.execution_evaluation.success);assert(b.evaluation.robot_joint_displacement_rad>.1);
    await page.waitForFunction(last=>window.__vivacityCloth?.vertices&&Math.max(...last.vertices.flat().map((v,i)=>Math.abs(v-window.__vivacityCloth.vertices[i])))<1e-6,b.trace.at(-1),{timeout:60000});
    assert(!b.trace.at(-1).grasp_active.some(Boolean));proof.checks.push('fresh_actuated_cloth_execution_and_exact_vertices');
    await page.screenshot({path:`artifacts/${prefix}-cloth.png`,fullPage:true});
  }
  await page.getByRole('button',{name:'Import World',exact:true}).click();
  await page.getByLabel('Choose a world file').setInputFiles('fixtures/imports/triangle.glb');
  await page.getByRole('button',{name:'Inspect file',exact:true}).click();
  await page.getByRole('heading',{name:'Visual scene',exact:true}).waitFor();await page.waitForFunction(()=>window.__vivacityImport?.vertices===3);
  assert.equal(await page.getByRole('log').count(),1);proof.checks.push('bounded_real_visual_import');
  assert(proof.state_messages>100&&proof.event_messages>10);assert(liveFrames.some(f=>f.stage==='executing'&&f.frame.phase==='lift'));
  assert.deepEqual(proof.errors,[]);proof.status='passed';console.log('Robotics templates, fresh pickup/cloth physics, live transforms, exports and UI checks passed.');
}catch(e){proof.status='failed';proof.failure=e.message;throw e;}
finally{
  proof.finished_unix_s=Date.now()/1000;fs.writeFileSync(`artifacts/${prefix}-verification.json`,JSON.stringify(proof,null,2));
  if(capability&&latestSession?.status==='active')await fetch(`${base}/v1/sessions/${latestSession.id}/stop`,{method:'POST',headers:{'X-Session-Token':capability}}).catch(()=>{});
  await browser.close();
}
