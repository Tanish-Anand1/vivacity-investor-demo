import {test,expect} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const backend=process.env.VIVACITY_CONTACT_API??'http://127.0.0.1:8192';
const prefix=backend+'/v1/robotics/contact';
const route='/v1/robotics/contact';

test('real contact task: live state, pause, fork, compare, replay, changed geometry and reload',async({page,request,browserName},testInfo)=>{
  const errors:string[]=[];
  page.on('pageerror',error=>errors.push(error.message));
  const writes:string[]=[];
  page.on('request',r=>{if(r.method()==='POST'&&/\/v1\/(sessions|worlds|robotics\/contact\/experiments)$/.test(r.url()))writes.push(r.url());});
  await page.goto('/contact-lab');
  const start=page.getByRole('button',{name:'Run physical trial',exact:true});
  await expect(start).toBeEnabled();
  await expect(page.locator('[data-model-hash]')).toHaveAttribute('data-model-hash',/^[a-f0-9]{64}$/);
  await expect(page.getByTestId('contact-result')).toContainText('No experiment has started');
  expect(writes).toEqual([]);
  const folder=path.resolve('../artifacts/physical-truth-runtime');
  await page.screenshot({path:path.join(folder,`contact-${browserName}-initial.png`),fullPage:true});
  const capability=await page.evaluate(()=>localStorage.getItem('vivacity:workspace-capability'));
  expect(capability).toBeTruthy();
  const headers={'X-Workspace-Token':capability!};
  const read=async(id:string,suffix='')=>{
    const response=await request.get(`${prefix}/experiments/${id}${suffix}`,{headers});
    expect(response.ok(),await response.text()).toBeTruthy();return response.json();
  };
  const submitted=page.waitForResponse(r=>r.url().endsWith(route+'/experiments')&&r.request().method()==='POST');
  await start.click();
  const firstResponse=await submitted;expect(firstResponse.status()).toBe(202);
  const first=await firstResponse.json();
  await expect.poll(async()=>{const d=await read(first.id,'/frames');return d.frames.length>=2&&d.status==='running';}).toBeTruthy();
  await page.getByRole('button',{name:'Pause physics',exact:true}).click();
  await expect(page.getByRole('button',{name:'Resume physics',exact:true})).toBeEnabled();
  const frozen=await read(first.id,'/checkpoint');
  await page.waitForTimeout(250);
  expect(await read(first.id,'/checkpoint')).toEqual(frozen);
  await page.screenshot({path:path.join(folder,`contact-${browserName}-paused.png`),fullPage:true});
  const forked=page.waitForResponse(r=>r.url().endsWith(`${route}/experiments/${first.id}/fork`));
  await page.getByRole('button',{name:'Fork paused snapshot'}).click();
  const branchResponse=await forked;expect(branchResponse.status()).toBe(202);
  const branch=await branchResponse.json();
  await page.getByRole('button',{name:'Resume physics',exact:true}).click();
  await expect(page.getByTestId('contact-result')).toContainText('Placement completed in simulation',{timeout:240_000});
  await expect.poll(async()=>(await read(branch.id)).status,{timeout:240_000}).toBe('completed');
  const original=await read(first.id),fork=await read(branch.id);
  expect(original.result.task_success).toBe(true);
  expect(original.result.measurements.last_measurement).toEqual(fork.result.measurements.last_measurement);
  expect(original.result.measurements.minimum_hold_share).toBeGreaterThanOrEqual(.15);
  expect(original.result.measurements.maximum_actuator_torque_fraction).toBeLessThanOrEqual(1.00001);
  const finalTime=await page.getByTestId('contact-time').innerText();
  await page.waitForTimeout(250);
  expect(await page.getByTestId('contact-time').innerText()).toBe(finalTime);
  await page.getByRole('button',{name:'Refresh history'}).click();
  await page.getByLabel(`Compare ${first.id.slice(0,8)}`).check();
  await page.getByLabel(`Compare ${branch.id.slice(0,8)}`).check();
  await page.getByRole('button',{name:'Compare selected trials'}).click();
  await expect(page.getByText('Same immutable world version.')).toBeVisible();
  await page.getByRole('button',{name:'Replay',exact:true}).click();
  await expect(page.getByRole('button',{name:'Pause replay',exact:true})).toBeVisible();
  expect(parseFloat(await page.getByTestId('contact-time').innerText())).toBeLessThan(parseFloat(finalTime));
  await page.getByRole('button',{name:'Pause replay',exact:true}).click();
  const downloadEvent=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export JSON'}).click();
  const download=await downloadEvent;
  const output=testInfo.outputPath('measured-contact-export.json');await download.saveAs(output);
  const report=JSON.parse(await fs.readFile(output,'utf8'));
  expect(report.trial.result.task_success).toBe(true);
  expect(report.frames.length).toBe(report.checkpoint.next_frame_seq);
  expect(report.frames.at(-1).frame.qpos).not.toEqual(report.frames[0].frame.qpos);
  expect(report.frames.every((entry:{frame:{grasp_constraint_active:boolean}})=>!entry.frame.grasp_constraint_active)).toBe(true);
  await page.getByLabel('Parcel mass (kg)').fill('0.6');
  await page.getByLabel('Sliding friction',{exact:true}).fill('0.001');
  await page.getByText('Carton dimensions',{exact:true}).click();
  await page.getByLabel('Dimension X (m)').fill('0.20');
  const changedRequest=page.waitForResponse(r=>r.url().endsWith(route+'/experiments')&&r.request().method()==='POST');
  await start.click();const changedResponse=await changedRequest;expect(changedResponse.status()).toBe(202);
  const changed=await changedResponse.json();
  await expect(page.getByTestId('contact-result')).toContainText('Trial failed:',{timeout:240_000});
  const failed=await read(changed.id);
  expect(failed.result.task_success).toBe(false);
  expect(failed.world_version).not.toBe(original.world_version);
  const scene=await read(changed.id,'/scene');
  expect(scene.geoms.find((g:{name:string})=>g.name==='parcel_box').size[0]).toBe(.1);
  await expect(page.locator('[data-model-hash]')).toHaveAttribute('data-model-hash',scene.model_hash);
  const beforeReload=writes.length;await page.reload();
  await expect(page.getByTestId('contact-result')).toContainText('Trial failed:');
  expect(writes.length).toBe(beforeReload);
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.setViewportSize({width:390,height:844});
  await expect(start).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.keyboard.press('Tab');
  expect(await page.evaluate(()=>document.activeElement?.tagName)).not.toBe('BODY');
  await page.screenshot({path:path.join(folder,`contact-${browserName}-mobile.png`),fullPage:true});
  expect(errors).toEqual([]);
  await fs.writeFile(path.join(folder,`contact-${browserName}-journey.json`),JSON.stringify({
    first_id:first.id,fork_id:branch.id,failure_id:changed.id,controller:original.result.controller,
    model_sha256:original.result.model_sha256,steps:original.steps_completed,
    minimum_hand_share:original.result.measurements.minimum_hold_share,
    placement_error_m:original.result.measurements.last_measurement.destination_error_m,
    failure_reason:failed.result.failure_reason,initial_load_started_experiments:false,
    reload_started_experiments:false,checks:['live_before_terminal','complete_pause_snapshot','independent_fork',
      'matching_final_measurement','explicit_replay','export_matches_cursor','changed_geometry','genuine_failure',
      'reload_recovery','mobile_reflow','keyboard_focus','reduced_motion','no_page_errors']},null,2));
});
