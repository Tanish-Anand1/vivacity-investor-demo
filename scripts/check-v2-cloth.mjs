import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});const evidence={};
const base=process.env.API_URL??'http://127.0.0.1:8000',reuse=process.env.REUSE_EXPERIMENT;
try{
 const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 if(reuse){const previous=await(await fetch(`${base}/v1/experiments/${reuse}`)).json();await page.addInitScript(({w,e})=>{localStorage.setItem('vivacity:cloth:world',w);localStorage.setItem('vivacity:cloth:experiment',e);},{w:previous.world_id,e:reuse});}
 await page.goto(process.env.UI_URL??'http://127.0.0.1:5173/');await page.getByRole('button',{name:'Cloth Folding',exact:true}).click();
 await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(e=>e.textContent==='Run experiment');return b&&!b.disabled&&window.__vivacityCloth;},null,{timeout:60000});
 if(!reuse)await page.getByRole('button',{name:'Run experiment',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('[data-testid="experiment-status"]')?.textContent==='Result selected',null,{timeout:600000});
 await page.getByRole('button',{name:'Pause motion',exact:true}).waitFor();await page.getByRole('button',{name:'Pause motion',exact:true}).click();
 const eid=await page.evaluate(()=>localStorage.getItem('vivacity:cloth:experiment'));
 const exp=await(await fetch(`${base}/v1/experiments/${eid}`)).json(),branches=await(await fetch(`${base}/v1/experiments/${eid}/branches`)).json();
 assert.equal(exp.result.search.generated,5000);assert.equal(exp.result.search.distinct_generated,5000);assert.equal(exp.result.search.fully_simulated,8);assert(exp.result.search.verified_feasible>=3);
 assert.equal(await page.getByTestId('branch-row').count(),3);
 const chosen=branches.find(b=>b.id===exp.selected_branch_id),target=chosen.trace.at(-1).vertices.flat();const slider=page.getByRole('slider',{name:'Replay timeline'});await slider.focus();await slider.press('End');
 await page.waitForFunction(p=>Math.max(...p.map((v,i)=>Math.abs(v-(window.__vivacityCloth?.vertices[i]??Infinity))))<1e-6,target,{timeout:30000});
 assert(!await page.evaluate(()=>window.__vivacityCloth.graspActive.some(Boolean)));
 assert.equal(chosen.initial_state.config.robot_model,'panda');assert(chosen.evaluation.robot_joint_displacement_rad>.1);assert.equal(chosen.action.joint_waypoints.length,71);
 const finalBodies=chosen.trace.at(-1).body_transforms.filter(p=>p.name!=='clamp');
 await page.waitForFunction(poses=>poses.every(p=>window.__vivacityClothRobot?.bodies[p.name]&&Math.max(...p.position.map((v,i)=>Math.abs(v-window.__vivacityClothRobot.bodies[p.name][i])))<1e-8),finalBodies,{timeout:60000});
 await page.waitForFunction(poses=>poses.every(p=>window.__vivacityClothRobot?.orientationsWXYZ[p.name]&&Math.min(Math.max(...p.quaternion_wxyz.map((v,i)=>Math.abs(v-window.__vivacityClothRobot.orientationsWXYZ[p.name][i]))),Math.max(...p.quaternion_wxyz.map((v,i)=>Math.abs(v+window.__vivacityClothRobot.orientationsWXYZ[p.name][i]))))<1e-8),finalBodies,{timeout:60000});
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download JSON for result 1',exact:true}).click();const file=await download;await file.saveAs('artifacts/v2-cloth-branch.json');const data=JSON.parse(fs.readFileSync('artifacts/v2-cloth-branch.json'));assert.equal(data.simulation_backend,'mujoco');assert.deepEqual(data.recorded_frames,chosen.trace);
 await page.screenshot({path:'artifacts/v2-cloth-desktop.png',fullPage:true});await page.setViewportSize({width:375,height:900});await page.screenshot({path:'artifacts/v2-cloth-mobile.png',fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
 Object.assign(evidence,{experiment:exp,evaluations:branches.map(b=>b.evaluation),exactVertices:true,releaseVerified:true,errors});console.log('Real flex search, three winners, export and exact vertex replay passed.');
}finally{await browser.close();fs.writeFileSync('artifacts/v2-cloth-journey.json',JSON.stringify(evidence,null,2));}
