import {test,expect,type Page} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const report=path.resolve('test-results/factory-configurator-proof');
const apiBase=process.env.FACTORY_E2E_API_BASE_URL??'http://127.0.0.1:8002';
fs.mkdirSync(report,{recursive:true});

async function ready(page:Page){
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/lab',{waitUntil:'domcontentloaded',timeout:60_000});
 await expect(page.getByRole('heading',{name:'Build a world. Test what could happen.'})).toBeVisible();
 await page.getByRole('button',{name:'Research',exact:true}).click();
 const start=page.getByRole('button',{name:'Start production'});
 const reconnect=page.getByRole('button',{name:'Reconnect'});
 for(let attempt=0;attempt<3;attempt++){
  await expect.poll(async()=>await start.isEnabled()||await reconnect.isVisible(),{timeout:90_000}).toBe(true);
  if(await start.isEnabled())break;
  await reconnect.click();
 }
 await expect(start).toBeEnabled({timeout:90_000});
 await page.getByText('Production conditions',{exact:true}).click();
}

test('configuration changes replace historical frames and high-fidelity view stays clear',async({page,request})=>{
 const consoleErrors:string[]=[];
 const unexpectedWorldRequests:string[]=[];
 page.on('pageerror',error=>consoleErrors.push(error.message));
 page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text());});
 page.on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname.endsWith('/v1/worlds'))unexpectedWorldRequests.push(request.url());});
 await ready(page);
 expect(unexpectedWorldRequests).toEqual([]);
 const name=page.getByLabel('Configuration name');
 const mass=page.getByLabel('Reference mass (kg)');
 const friction=page.getByLabel('Contact friction',{exact:true});
 const count=page.getByLabel('Cartons');
 const initialY=page.getByLabel('Initial carton Y (m)');
 const speed=page.getByLabel('Simulation speed');
 const grip=page.getByLabel('Gripper force scale',{exact:true});

 await name.fill('Configurator regression');
 await count.fill('1');
 await initialY.fill('-0.4');
 await speed.fill('8');
 await mass.fill('0.09');
 await friction.fill('1.2');
 await grip.fill('1');
 const apply=page.getByRole('button',{name:'Apply conditions'});
 await expect(apply).toBeEnabled();
 await apply.click();
 await expect(page.getByText('0.0900',{exact:true})).toBeVisible();
 await expect(page.getByText('1.200',{exact:true})).toBeVisible();
 const firstCell=await page.evaluate(()=>localStorage.getItem('vivacity:factory-cell'));
 expect(firstCell).toBeTruthy();
 const workspaceToken=await page.evaluate(()=>localStorage.getItem('vivacity:workspace-capability'));
 const firstResponse=await request.get(`${apiBase}/v1/factory/cells/${firstCell}`,{headers:{'X-Workspace-Token':workspaceToken??''}});
 expect(firstResponse.ok()).toBeTruthy();
 const first=await firstResponse.json();
 expect(first.config).toMatchObject({carton_count:1,carton_start_y_m:-.4,realtime_speed:8,carton_mass_kg:.09,carton_friction:1.2});

 await page.getByRole('combobox',{name:'View',exact:true}).selectOption('performance');
 await page.getByRole('button',{name:'Start production'}).click();
 await expect(page.locator('.factory-control-bar strong[role="status"]')).toContainText('completed',{timeout:120_000});
 await expect(page.getByRole('slider',{name:'Recorded sample'})).toBeVisible({timeout:60_000});
 const timeline=page.getByRole('slider',{name:'Recorded sample'});
 await timeline.focus();
 await timeline.press('Home');
 await expect(page.getByText(/Viewport: recorded sample/)).toBeVisible();

 await mass.fill('0.10');
 await apply.click();
 await expect(page.getByText('Live state')).toBeVisible();
 await expect(page.getByText('0.1000',{exact:true})).toBeVisible();
 await expect(page.getByText(/Viewport: recorded sample/)).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'Physics over time'})).toHaveCount(0);
 const secondCell=await page.evaluate(()=>localStorage.getItem('vivacity:factory-cell'));
 expect(secondCell).not.toBe(firstCell);
 const second=await(await request.get(`${apiBase}/v1/factory/cells/${secondCell}`,{headers:{'X-Workspace-Token':workspaceToken??''}})).json();
 expect(second.config.carton_mass_kg).toBe(.1);

 await mass.fill('');
 await expect(page.getByRole('status').filter({hasText:'Enter a valid value for Reference mass'})).toBeVisible();
 await expect(apply).toBeDisabled();
 await page.screenshot({path:path.join(report,'configurator-ready.png'),fullPage:true});

 await page.getByRole('combobox',{name:'View',exact:true}).selectOption('fidelity');
 const fidelityScreenshot=path.join(report,'high-fidelity-clean.png');
 await page.screenshot({path:fidelityScreenshot,fullPage:false});
 expect(consoleErrors).toEqual([]);
});

test('production condition inputs reject out-of-range values and recover cleanly',async({page})=>{
 await ready(page);
 const speed=page.getByLabel('Conveyor speed (m/s)');
 const apply=page.getByRole('button',{name:'Apply conditions'});
 await speed.fill('0.5');
 await expect(page.getByRole('status').filter({hasText:'Conveyor speed (m/s) must be between 0.02 and 0.18'})).toBeVisible();
 await expect(apply).toBeDisabled();
 await speed.fill('0.12');
 await expect(apply).toBeEnabled();
 await page.setViewportSize({width:390,height:844});
 await expect(page.getByRole('button',{name:'Apply conditions'})).toBeVisible();
 const horizontalOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
 expect(horizontalOverflow).toBe(false);
});
