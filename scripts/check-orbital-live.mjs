import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
process.chdir(path.resolve(import.meta.dirname,'..'));
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');
process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const {AxeBuilder}=await import('../frontend/node_modules/@axe-core/playwright/dist/index.mjs');
const base=process.env.API_URL??'http://127.0.0.1:8002',url=process.env.UI_URL??'http://127.0.0.1:5174/';
const prefix=process.env.PROOF_PREFIX??'orbital-local';
const proof={url,api:base,checks:[],errors:[],frames:0,events:0,started_unix_s:Date.now()/1000};
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const context=await browser.newContext({viewport:{width:1440,height:960},acceptDownloads:true});
const page=await context.newPage();let experimentId,record;
async function request(p){const r=await fetch(base+p);assert.equal(r.status,200,p);return r.json();}
page.on('pageerror',e=>proof.errors.push(e.message));
page.on('websocket',socket=>socket.on('framereceived',e=>{try{const v=JSON.parse(String(e.payload));if(v.schema_version==='vivacity.live/1.0')proof.frames++;else if(v.seq)proof.events++;}catch{}}));
let submissions=0;page.on('request',r=>{if(r.method()==='POST'&&/\/worlds\/[^/]+\/experiments$/.test(r.url()))submissions++;});
try{
 await page.goto(url,{waitUntil:'domcontentloaded'});
 await page.getByRole('button',{name:'Import World',exact:true}).click();
 await page.locator('#world-file').setInputFiles(path.resolve('fixtures/imports/orbital_salvage_lab.zip'));
 await page.getByRole('button',{name:'Inspect file',exact:true}).click();await page.waitForFunction(()=>localStorage.getItem('vivacity:import'));const importId=await page.evaluate(()=>localStorage.getItem('vivacity:import'));record=await request(`/v1/imports/${importId}`);
 assert.equal(record.physics_ready,false);proof.checks.push('original_upload_not_task_ready');
 await page.getByRole('button',{name:'Verify physics',exact:true}).click();
 await page.getByRole('button',{name:'Configure adapted Panda salvage task',exact:true}).waitFor({timeout:150000});
 record=await request(`/v1/imports/${record.id}`);assert(record.capabilities.robot_actuation_verified);assert.equal(record.capabilities.task_execution_verified,false);assert(record.capabilities.simulation_steps>0);proof.native_probe=record.capabilities;proof.checks.push('native_original_compiled_and_actuated');
 await page.getByRole('button',{name:'Configure adapted Panda salvage task',exact:true}).click();
 const start=page.getByRole('button',{name:'Start salvage experiment',exact:true});await start.waitFor({timeout:90000});
 record=await request(`/v1/imports/${record.id}`);const world=await request(`/v1/worlds/${record.configured_world_id}`);
 assert.equal(world.history.length,0);assert.equal(experimentId,undefined);proof.checks.push('configuration_does_not_auto_start');
 const initial=(await request(`/v1/worlds/${world.id}/state`)).observation;
 await start.click();const deadline=Date.now()+900000;
 while(!experimentId&&Date.now()<deadline){const current=await request(`/v1/worlds/${world.id}`);experimentId=current.history.at(-1);if(!experimentId)await page.waitForTimeout(200);}
 assert(experimentId);let experiment;
 while(Date.now()<deadline){experiment=await request(`/v1/experiments/${experimentId}`);if(!['queued','running'].includes(experiment.status))break;await page.waitForTimeout(1500);}
 assert.equal(experiment.status,'completed',JSON.stringify(experiment));assert(experiment.result.execution_evaluation.success,JSON.stringify(experiment.result));
 const branches=await request(`/v1/experiments/${experimentId}/branches`),good=branches.filter(b=>b.evaluation.success&&b.action.execution_role!=='authoritative_execution');assert(good.length>0&&good.length<=3);proof.experiment=experiment;proof.branches=branches.map(b=>({id:b.id,evaluation:b.evaluation,performance:b.performance}));
 assert(branches.every(b=>b.initial_state.config.source_import_id===record.id));proof.checks.push('independent_real_trials_and_fresh_delivery');
 await page.getByTestId('branch-row').first().waitFor({timeout:20000});assert.equal(await page.getByTestId('branch-row').count(),good.length);
 const downloading=page.waitForEvent('download');await page.getByRole('button',{name:'Download JSON for result 1',exact:true}).click();const file=await downloading;await file.saveAs(path.resolve(`artifacts/${prefix}-branch.json`));const exported=JSON.parse(fs.readFileSync(`artifacts/${prefix}-branch.json`));assert(exported.success&&exported.evaluation.grasp_established&&exported.evaluation.released);assert.equal(exported.initial_configuration.source_import_id,record.id);assert(exported.recorded_frames.length>10);assert.equal(exported.recorded_frames.at(-1).import_provenance.source_sha256,record.sha256);proof.checks.push('download_contains_native_states_contacts_and_provenance');
 await page.waitForFunction(()=>window.__vivacityScene?.bodies?.target);const scene=await page.evaluate(()=>window.__vivacityScene);const live=await request(`/v1/experiments/${experimentId}/live`);const target=live.frame.body_transforms.find(b=>b.name==='target').position;assert(Math.hypot(...target.map((x,i)=>x-scene.bodies.target[i]))<.00001);assert(Math.hypot(...target.map((x,i)=>x-initial.cube_position[i]))>.1);proof.checks.push('rendered_cargo_matches_computed_live_state');
 assert.equal(await page.locator('details.inspector').count(),1);assert.equal(await page.getByRole('button',{name:/^(Play|Pause|Resume)/i}).count(),0);proof.checks.push('one_inspector_no_video_controls');
 const viewport=page.getByTestId('robot-viewport');await viewport.focus();const before=scene.cameraPosition;await page.keyboard.press('ArrowLeft');await page.waitForTimeout(400);assert.notDeepEqual(await page.evaluate(()=>window.__vivacityScene.cameraPosition),before);proof.checks.push('keyboard_camera_independent_of_physics');
 await page.screenshot({path:`artifacts/${prefix}-verified.png`});
 // Intervene through the real UI: old evidence must become stale, no job may
 // auto-start, and the obstructed cargo must produce an honest failure.
 const oldId=experimentId,oldSubmissions=submissions;
 await page.getByRole('button',{name:'Change conditions',exact:true}).click();
 await page.getByRole('button',{name:'Blocked scene',exact:true}).click();
 await page.getByRole('button',{name:'Apply settings',exact:true}).click();
 await page.getByText('Conditions changed. Previous results are stale; start a new experiment.',{exact:true}).waitFor({timeout:90000});
 assert((await request(`/v1/experiments/${oldId}`)).stale);assert.equal(submissions,oldSubmissions);proof.checks.push('geometry_change_invalidates_without_auto_start');
 await start.click();const failureDeadline=Date.now()+300000;let failedId;
 while(Date.now()<failureDeadline){failedId=(await request(`/v1/worlds/${world.id}`)).history.at(-1);if(failedId&&failedId!==oldId)break;await page.waitForTimeout(250);}
 assert(failedId&&failedId!==oldId);experimentId=failedId;let failed;
 while(Date.now()<failureDeadline){failed=await request(`/v1/experiments/${failedId}`);if(!['queued','running'].includes(failed.status))break;await page.waitForTimeout(1500);}
 assert.equal(failed.status,'completed',JSON.stringify(failed));assert.equal(failed.selected_branch_id,null);const rejected=await request(`/v1/experiments/${failedId}/branches`);assert(rejected.length>0&&rejected.every(b=>!b.evaluation.success));proof.replanned_failure={experiment:failed,branches:rejected.map(b=>({id:b.id,evaluation:b.evaluation,performance:b.performance}))};proof.checks.push('blocked_reactor_recomputes_real_failed_alternatives');
 await page.setViewportSize({width:375,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));const axe=await new AxeBuilder({page}).include('#workspace').analyze();assert.equal(axe.violations.length,0,JSON.stringify(axe.violations));proof.checks.push('mobile_reflow_and_axe_scope');
 const prior=submissions;await page.reload({waitUntil:'domcontentloaded'});await page.getByRole('button',{name:'Import World',exact:true}).click();await start.waitFor({timeout:90000});assert.equal(submissions,prior);proof.checks.push('reload_remains_idle');
 assert(proof.frames>5&&proof.events>3);assert.deepEqual(proof.errors,[]);proof.status='passed';
}catch(e){proof.status='failed';proof.failure=e.stack;await page.screenshot({path:`artifacts/${prefix}-failure.png`}).catch(()=>{});process.exitCode=1;}
finally{proof.finished_unix_s=Date.now()/1000;if(experimentId)await fetch(`${base}/v1/experiments/${experimentId}/cancel`,{method:'POST'}).catch(()=>{});fs.writeFileSync(`artifacts/${prefix}.json`,JSON.stringify(proof,null,2));await browser.close();console.log(JSON.stringify({status:proof.status,checks:proof.checks,frames:proof.frames,events:proof.events,failure:proof.failure}));}
