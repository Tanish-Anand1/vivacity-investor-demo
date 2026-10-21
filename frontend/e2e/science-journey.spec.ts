import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import path from 'node:path';
import fs from 'node:fs';

const apiBase=process.env.FACTORY_E2E_API_BASE_URL??'http://127.0.0.1:8002';
const shots=path.resolve('test-results/science-journey');
fs.mkdirSync(shots,{recursive:true});

test('Isabella homepage leads with robotics and opens both working disciplines',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 expect(await page.locator('body').innerText()).not.toMatch(/\bMuJoCo\b/i);
 await expect(page.getByText('ISABELLA LABS / BY VIVACITY')).toBeVisible();
 await expect(page.getByText('RECORDED SIMULATION').first()).toBeVisible();
 await page.screenshot({path:path.join(shots,'science-home-desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'ENTER THE LAB',exact:true}).click();
 await expect(page).toHaveURL('/laboratory');
 await expect(page.getByRole('heading',{name:/Choose a world/i})).toBeVisible();
 await page.getByRole('button',{name:/Open scientific lab/i}).click();
 await expect(page).toHaveURL('/discovery');
 await expect(page.getByRole('heading',{name:/The Invisible Planet/i})).toBeVisible();
 expect(await page.locator('body').innerText()).not.toMatch(/\bMuJoCo\b/i);
 await page.getByRole('link',{name:'Lab',exact:true}).click();
 await expect(page).toHaveURL('/laboratory');
 await page.getByRole('button',{name:/Open robotics lab/i}).click();
 await expect(page).toHaveURL('/lab');
 await expect(page.getByRole('heading',{name:/Build a world/i})).toBeVisible();
 expect(await page.locator('body').innerText()).not.toMatch(/\bMuJoCo\b/i);
});

test('real SciPy observations, independent fits, stale results, replay, export and control rejection',async({page,request})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/discovery',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('button',{name:/Create observation world/i})).toBeEnabled();
 await page.getByRole('button',{name:/Create observation world/i}).click();
 await expect(page.getByRole('status').filter({hasText:/World [0-9a-f]{8}/i})).toBeVisible();
 const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('vivacity:science-lab/1')||'{}'));
 const firstWorld=await(await request.get(`${apiBase}/v1/worlds/${saved.worldId}`)).json();
 expect(firstWorld.backend).toBe('scipy');
 expect(JSON.stringify(firstWorld)).not.toContain('hidden_mass');
 await page.getByRole('button',{name:'Run model comparison'}).click();
 await expect(page.getByText(/Last job: completed/i)).toBeVisible({timeout:60_000});
 let session=await page.evaluate(()=>JSON.parse(localStorage.getItem('vivacity:science-lab/1')||'{}'));
 const first=await(await request.get(`${apiBase}/v1/experiments/${session.history[0]}`)).json();
 const fitted=await(await request.get(`${apiBase}/v1/experiments/${first.id}/branches`)).json();
 expect(fitted).toHaveLength(2);
 expect(fitted.every((branch:any)=>branch.performance.integration_calls>0&&branch.trace.length===70)).toBeTruthy();
 expect(fitted[1].evaluation.heldout_rmse).toBeLessThan(fitted[0].evaluation.heldout_rmse);
 expect(first.selected_branch_id).toBe(fitted[1].id);
 await page.getByRole('slider',{name:'Replay numerical samples'}).focus();
 await page.keyboard.press('End');
 await expect(page.getByRole('status').filter({hasText:/heldout · observed/i})).toBeVisible();
 const download=page.waitForEvent('download');
 await page.getByRole('button',{name:'Export branch JSON'}).click();
 expect((await download).suggestedFilename()).toContain(first.selected_branch_id);
 await page.screenshot({path:path.join(shots,'science-fit-desktop.png'),fullPage:true});
 await page.getByLabel('Observation scenario').selectOption('control');
 await page.getByLabel('Noise standard deviation').fill('0.004');
 await page.getByRole('button',{name:'Apply changed conditions'}).click();
 await expect(page.getByTestId('science-stale-warning')).toBeVisible();
 expect((await(await request.get(`${apiBase}/v1/experiments/${first.id}`)).json()).stale).toBe(true);
 await page.getByRole('button',{name:'Run model comparison'}).click();
 await expect.poll(()=>page.evaluate(()=>JSON.parse(localStorage.getItem('vivacity:science-lab/1')||'{}').history?.length??0)).toBe(2);
 await expect(page.getByText(/Last job: completed/i)).toBeVisible({timeout:60_000});
 session=await page.evaluate(()=>JSON.parse(localStorage.getItem('vivacity:science-lab/1')||'{}'));
 expect(session.history).toHaveLength(2);
 const control=await(await request.get(`${apiBase}/v1/experiments/${session.history[0]}`)).json();
 const controlBranches=await(await request.get(`${apiBase}/v1/experiments/${control.id}/branches`)).json();
 expect(control.selected_branch_id).toBe(controlBranches[0].id);
 const replay=await(await request.get(`${apiBase}/v1/experiments/${control.id}/replay`)).json();
 expect(replay.branches[0].frames).toEqual(controlBranches[0].trace);
 await page.getByRole('button',{name:'Commit fitted model'}).click();
 await expect(page.getByText(/selected fitted model was committed/i)).toBeVisible();
 await expect(page.getByTestId('science-stale-warning')).toBeVisible();
 let committed=await(await request.get(`${apiBase}/v1/worlds/${saved.worldId}`)).json();
 expect(committed.state.selected_model.hypothesis).toBe('central_only');
 await page.getByRole('button',{name:'Reset world'}).click();
 await expect(page.getByText(/World reset to its initial observation state/i)).toBeVisible();
 committed=await(await request.get(`${apiBase}/v1/worlds/${saved.worldId}`)).json();
 expect(committed.state.selected_model).toBeNull();
 await page.reload();
 await expect(page.getByText(/Last job: completed/i)).toBeVisible({timeout:60_000});
 await page.getByText(/Experiment history/).click();
 await page.getByRole('button',{name:/Experiment 1 ·/}).click();
 await expect(page.getByTestId('science-stale-warning')).toBeVisible();
});

test('homepage and discovery controls remain usable on a narrow screen',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 await page.screenshot({path:path.join(shots,'science-home-mobile.png'),fullPage:true});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
 const audit=await new AxeBuilder({page}).include('.isabella-home').withTags(['wcag2a','wcag2aa','wcag22aa']).analyze();
 expect(audit.violations.filter(issue=>issue.impact==='serious'||issue.impact==='critical').map(issue=>issue.id)).toEqual([]);
 await page.getByRole('button',{name:/Explore scientific experiments/i}).click();
 await expect(page).toHaveURL('/discovery');
 await expect(page.getByRole('button',{name:/Create observation world/i})).toBeEnabled();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});

test('expired saved observation world explains recovery and allows a fresh start',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.addInitScript(()=>localStorage.setItem('vivacity:science-lab/1',JSON.stringify({
  worldId:'00000000-0000-4000-8000-000000000000',
  draft:{scenario:'signal',seed:7,noise:.001,samples:70,horizon:5,speed:1,trainFraction:.7},
  history:[]
 })));
 await page.goto('/discovery',{waitUntil:'domcontentloaded'});
 await expect(page.getByText(/saved observation world expired on this host/i)).toBeVisible();
 await expect(page.getByRole('button',{name:/Create observation world/i})).toBeEnabled();
 expect(await page.evaluate(()=>localStorage.getItem('vivacity:science-lab/1'))).toBeNull();
});
