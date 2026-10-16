import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});const evidence={};
try{
 const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5173/');await page.getByRole('button',{name:'Discovery',exact:true}).click();
 const ready=()=>page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(e=>e.textContent==='Run experiment');return b&&!b.disabled;},null,{timeout:60000});
 const finished=()=>page.waitForFunction(()=>document.querySelector('[data-testid="experiment-status"]')?.textContent==='Result selected',null,{timeout:120000});
 await ready();await page.getByRole('button',{name:'Run experiment',exact:true}).click();await finished();
 await page.getByRole('button',{name:'Pause motion',exact:true}).waitFor();await page.getByRole('button',{name:'Pause motion',exact:true}).click();
 const eid=await page.evaluate(()=>localStorage.getItem('vivacity:scipy:experiment'));
 const exp=await(await fetch(`http://127.0.0.1:8000/v1/experiments/${eid}`)).json();const branches=await(await fetch(`http://127.0.0.1:8000/v1/experiments/${eid}/branches`)).json();
 const chosen=branches.find(b=>b.id===exp.selected_branch_id);assert.equal(chosen.evaluation.hypothesis,'central_plus_fixed_perturber');
 const slider=page.getByRole('slider',{name:'Replay timeline'});await slider.focus();await slider.press('End');
 const target=chosen.trace.at(-1).predicted_position;
 await page.waitForFunction(p=>Math.max(...p.map((v,i)=>Math.abs(v-(window.__vivacityScience?.predictedPosition[i]??Infinity))))<1e-8,target,{timeout:30000});
 assert.equal(await page.evaluate(()=>window.__vivacityScience.predictedPosition[2]),0);
 await page.getByLabel('Show fitted influence').check();await page.screenshot({path:'artifacts/v2-discovery-3d.png',fullPage:true});
 await page.getByRole('button',{name:'Observation settings',exact:true}).click();await page.getByLabel('Observation scenario').selectOption('control');await page.getByRole('button',{name:'Apply & run new experiment',exact:true}).click();await finished();await ready();
 const controlId=await page.evaluate(()=>localStorage.getItem('vivacity:scipy:experiment'));
 const control=await(await fetch(`http://127.0.0.1:8000/v1/experiments/${controlId}`)).json();const controls=await(await fetch(`http://127.0.0.1:8000/v1/experiments/${controlId}/branches`)).json();
 assert.equal(controls.find(b=>b.id===control.selected_branch_id).evaluation.hypothesis,'central_only');
 const world=await(await fetch(`http://127.0.0.1:8000/v1/worlds/${control.world_id}`)).json();assert(!JSON.stringify(world).includes('hidden_mass'));
 evidence.experiment=exp;evidence.fits=branches.map(b=>b.evaluation);evidence.control=control;evidence.computedPlaneVerified=true;evidence.errors=errors;
 assert.deepEqual(errors,[]);console.log('Real SciPy 3D and no-influence control passed.');
}finally{await browser.close();fs.writeFileSync('artifacts/v2-science-journey.json',JSON.stringify(evidence,null,2));}
