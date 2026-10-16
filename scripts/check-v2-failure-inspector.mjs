/** Inspect persisted real failed branches after the concise-label UI refinement. */
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const base=process.env.API_URL??'http://127.0.0.1:8000',ui=process.env.UI_URL??'http://127.0.0.1:5173/',id=process.env.EXPERIMENT_ID;
assert(id,'Set EXPERIMENT_ID to an actual completed robotics experiment with a recorded collision.');
const read=async route=>{const r=await fetch(base+route);assert(r.ok);return r.json();};
const experiment=await read(`/v1/experiments/${id}`),branches=await read(`/v1/experiments/${id}/branches`),failure=branches.find(b=>b.evaluation.contact_violations?.length);
assert(failure,'A real contact failure is required; no mock data is supplied.');
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(e=>{localStorage.setItem('vivacity:lab','mujoco');localStorage.setItem('vivacity:mujoco:world',e.world_id);localStorage.setItem('vivacity:mujoco:experiment',e.id);},experiment);
 await page.goto(ui);await page.getByRole('button',{name:'Run experiment',exact:true}).waitFor({timeout:60000});
 await page.getByText('Recorded failures & history',{exact:true}).click();const button=page.locator('button[data-status="collision_failure"]').first();await button.waitFor();
 const label=await button.innerText();assert(label.includes(`${failure.evaluation.contact_violations.length} contacts`));assert(label.length<200,'Failure summary must remain concise.');await button.click();
 assert.equal(await page.getByRole('log').count(),1);await page.setViewportSize({width:375,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
 const suffix=ui.startsWith('http://127.')?'local':'public';await page.screenshot({path:`artifacts/v2-failure-inspector-${suffix}.png`,fullPage:true});
 fs.writeFileSync(`artifacts/v2-failure-inspector-${suffix}.json`,JSON.stringify({status:'passed',ui,experiment_id:id,branch_id:failure.id,label,actual_contacts:failure.evaluation.contact_violations.length,one_inspector:true,mobile_overflow:false,errors},null,2));
 console.log('Actual failed-branch selection, bounded contact summary and mobile inspector passed.');
}finally{await browser.close();}
