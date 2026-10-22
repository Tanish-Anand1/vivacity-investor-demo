import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('G1 pickup runs measured physics, replays, and reports a heavy-parcel failure',async({page})=>{
  test.setTimeout(180_000);
  const errors:string[]=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('/works',{waitUntil:'domcontentloaded'});
  await expect(page.getByRole('heading',{name:'Unitree G1 with hands'})).toBeVisible({timeout:60_000});
  await expect(page.getByRole('combobox',{name:'Test mode'})).toHaveValue('pickup_place');
  await expect(page.getByRole('button',{name:'Run pickup experiment'})).toBeEnabled({timeout:60_000});

  const submission=page.waitForResponse(response=>response.url().includes('/v1/robotics/humanoids/experiments')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Run pickup experiment'}).click();
  expect((await submission).status()).toBe(202);
  await expect(page.getByText('Task completed in simulation')).toBeVisible({timeout:90_000});
  await expect(page.getByText(/The G1 lifted the parcel and released it onto the destination stand/)).toBeVisible();
  await expect(page.locator('.pickup-evidence')).toContainText('Destination support: yes');
  await expect(page.locator('.pickup-evidence')).toContainText('Grasp released: yes');
  const exportEvent=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export measured trial JSON'}).click();
  const download=await exportEvent;
  const output=path.resolve('../artifacts/humanoid-pickup-browser.json');
  await download.saveAs(output);
  const saved=JSON.parse(fs.readFileSync(output,'utf8'));
  expect(saved.task_success).toBe(true);
  expect(saved.measurements.final_support_contact).toBe(true);
  expect(saved.measurements.grasp_constraint_active_final).toBe(false);
  expect(saved.measurements.destination_error_m).toBeLessThan(.17);
  expect(saved.events.map((event:{phase:string})=>event.phase)).toEqual([
    'lift','transfer','lower','settle_before_release','released']);
  await page.getByRole('button',{name:'Pause replay'}).click();
  await page.getByRole('slider',{name:'Recorded simulation time'}).fill('4');
  await expect(page.getByText(/4\.00 \/ 8\.00 s/)).toBeVisible();
  await page.screenshot({path:path.resolve('../artifacts/humanoid-pickup-replay-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('button',{name:'Run pickup experiment'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  await page.screenshot({path:path.resolve('../artifacts/humanoid-pickup-replay-mobile.png'),fullPage:true});
  await page.getByRole('button',{name:'Reset view'}).click();
  await expect(page.getByText('Standing state')).toBeVisible();

  await page.locator('.humanoid-controls label').filter({hasText:'Parcel mass'}).locator('input').fill('2');
  await page.getByRole('button',{name:'Run pickup experiment'}).click();
  await expect(page.getByText('Task not completed')).toBeVisible({timeout:90_000});
  await expect(page.locator('.humanoid-result')).toContainText(/prohibited robot contact|unstable stance|placement not stable/);
  expect(errors).toEqual([]);
});
