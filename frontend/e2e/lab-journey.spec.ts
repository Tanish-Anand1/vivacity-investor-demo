import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const apiBase=process.env.FACTORY_E2E_API_BASE_URL??'http://127.0.0.1:8000';

// Opening lifecycle and media contracts live in isabella-opening.spec.ts.

test('homepage starts a real failure and six matched MuJoCo trials, then Research replays a saved run',async({page,request})=>{
 test.setTimeout(process.env.FACTORY_E2E_EXTERNAL==='1'?1_800_000:900_000);
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 await page.locator('.isabella-primary').click();
 await expect(page).toHaveURL('/laboratory');
 await page.getByRole('button',{name:/Open robotics lab/i}).click();
 await expect(page).toHaveURL('/lab');
 await expect(page.getByRole('button',{name:'Run baseline',exact:true})).toBeEnabled({timeout:90_000});
 await page.goBack();
 await expect(page).toHaveURL('/laboratory');
 await page.goBack();
 await expect(page).toHaveURL('/');
 await page.getByRole('button',{name:'OPEN ROBOTICS EXPERIMENT'}).click();
 await expect(page).toHaveURL('/lab');
 await expect(page.getByRole('heading',{name:'A package loses its grip.'})).toBeVisible({timeout:90_000});
 await page.getByRole('button',{name:'Run baseline',exact:true}).click();
 // This contract test keeps the physics identical while using the lightweight
 // viewport; the high-fidelity scene is inspected separately in visual QA.
 await page.getByRole('button',{name:'Research',exact:true}).click();
 await page.getByRole('combobox',{name:'View',exact:true}).selectOption('performance');
 await page.getByRole('button',{name:'Explore',exact:true}).click();
 await expect(page.locator('.lab-guide .lab-outcome').first()).toContainText('failed',{timeout:300_000});
 const cellId=await page.evaluate(()=>localStorage.getItem('vivacity:factory-cell'));
 const token=await page.evaluate(()=>localStorage.getItem('vivacity:workspace-capability'));
 expect(cellId).toBeTruthy();expect(token).toBeTruthy();
 await expect(page.locator('.lab-guide .lab-outcome').first()).toContainText('0 of 1 delivered');
 const baselineResponse=await request.get(`${apiBase}/v1/factory/cells/${cellId}`,{headers:{'X-Workspace-Token':token!}});
 expect(baselineResponse.ok()).toBeTruthy();
 const cell=await baselineResponse.json();
 const baselineRun=await(await request.get(`${apiBase}/v1/factory/runs/${cell.last_run_id}`,{headers:{'X-Workspace-Token':token!}})).json();
 expect(baselineRun.status).toBe('failed');
 expect(baselineRun.metrics.simulation_steps).toBeGreaterThan(1000);
 expect(baselineRun.metrics.cartons_sorted).toBe(0);
 expect(baselineRun.phase).toBe('dropped_object');

 await page.getByRole('button',{name:'Test both conditions · 6 trials'}).click();
 await expect(page.getByRole('button',{name:'Inspect completed trials while testing continues'})).toBeVisible({timeout:120_000});
 await page.getByRole('button',{name:'Inspect completed trials while testing continues'}).click();
 await expect(page.getByRole('button',{name:'Research',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.locator('.factory-benchmark > summary').click();
 await page.locator('.factory-benchmark-result .factory-trial-list li').first().getByRole('button',{name:'Inspect trial'}).click();
 await expect(page.getByRole('slider',{name:'Recorded sample'})).toBeVisible({timeout:90_000});
 expect(await page.evaluate(()=>localStorage.getItem('vivacity:factory-cell'))).toBe(cellId);
 await page.getByRole('button',{name:'Return to latest'}).click();
 await page.getByRole('button',{name:'Explore',exact:true}).click();
 await expect(page.getByRole('button',{name:'Inspect trials and replay'})).toBeVisible({timeout:process.env.FACTORY_E2E_EXTERNAL==='1'?1_500_000:300_000});
 const recordsResponse=await request.get(`${apiBase}/v1/factory/benchmarks`,{headers:{'X-Workspace-Token':token!}});
 expect(recordsResponse.ok()).toBeTruthy();
 const records=await recordsResponse.json();
 const benchmark=records.find((record:{cell_id:string})=>record.cell_id===cellId);
 expect(benchmark?.status).toBe('completed');
 expect(benchmark.trials).toHaveLength(6);
 expect(benchmark.trials.every((trial:{metrics:{simulation_steps:number}})=>trial.metrics.simulation_steps>1000)).toBe(true);
 expect(benchmark.comparison.partitions.training.baseline.successes).toBe(0);
 expect(benchmark.comparison.partitions.training.candidate.successes).toBeGreaterThan(0);
 expect(benchmark.comparison.partitions.held_out.baseline.trials).toBe(1);
 expect(benchmark.comparison.partitions.held_out.candidate.trials).toBe(1);
 expect(benchmark.comparison.selected_condition).toBe('candidate');
 console.log('LAB_E2E_BENCHMARK',JSON.stringify({id:benchmark.id,wall_time_s:benchmark.wall_time_s,training:benchmark.comparison.partitions.training,held_out:benchmark.comparison.partitions.held_out,steps:benchmark.trials.map((trial:{metrics:{simulation_steps:number}})=>trial.metrics.simulation_steps)}));
 await page.getByRole('button',{name:'Inspect trials and replay'}).click();
 await expect(page.getByRole('button',{name:'Research',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.locator('.factory-benchmark > summary').click();
 const candidate=page.locator('.factory-benchmark-result .factory-trial-list li').filter({hasText:'training / candidate'}).first();
 await candidate.getByRole('button',{name:'Inspect trial'}).click();
 const slider=page.getByRole('slider',{name:'Recorded sample'});
 await expect(slider).toBeVisible({timeout:90_000});
 await slider.focus();await slider.press('Home');
 await expect(page.getByText(/Viewport: recorded sample/)).toBeVisible();
 const csvPromise=page.waitForEvent('download');
 await page.getByRole('button',{name:'Export CSV'}).click();
 const csv=await csvPromise;
 expect(csv.suggestedFilename()).toMatch(/\.csv$/);
 const csvPath=await csv.path();
 expect(csvPath).toBeTruthy();
 expect(fs.readFileSync(csvPath!,'utf8')).toContain('time_s');
 const exportResponse=await request.get(`${apiBase}/v1/factory/benchmarks/${benchmark.id}/export`,{headers:{'X-Workspace-Token':token!}});
 expect(exportResponse.ok()).toBeTruthy();
 const exported=await exportResponse.json();
 expect(exported.schema_version).toBe('vivacity.factory-exchange/1.0');
 expect(exported.kind).toBe('benchmark');
});

test('reduced motion enters directly and the narrow layout has no horizontal overflow',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.setViewportSize({width:390,height:844});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('dialog',{name:'Isabella Labs introduction'})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 const mobileShots=path.resolve('test-results/isabella-home');fs.mkdirSync(mobileShots,{recursive:true});
 await page.screenshot({path:path.join(mobileShots,'mobile.png')});
 await page.locator('.isabella-primary').click();
 await page.getByRole('button',{name:/Open robotics lab/i}).click();
 await expect(page.getByRole('button',{name:'Run baseline'})).toBeEnabled({timeout:90_000});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)).toBe(false);
 await page.getByRole('button',{name:'Research',exact:true}).click();
 await expect(page.getByRole('button',{name:'Start production'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)).toBe(false);
});
