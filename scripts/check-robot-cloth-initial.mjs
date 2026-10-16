/** Inspect the actual deployed arm/cloth scene before submitting physics work. */
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const evidence={ui:process.env.UI_URL??'https://demo.tryvivacity.com/',errors:[]};
try{
 const page=await browser.newPage({viewport:{width:1440,height:960},reducedMotion:'reduce'});
 page.on('pageerror',e=>evidence.errors.push(e.message));page.on('console',m=>{if(m.type()==='error')evidence.errors.push(m.text());});
 await page.goto(evidence.ui,{timeout:60000});await page.getByRole('button',{name:'Cloth Folding',exact:true}).click();
 await page.waitForFunction(()=>window.__vivacityClothRobot?.bodies.hand&&window.__vivacityCloth?.vertices.length===147,null,{timeout:60000});
 evidence.scene=await page.evaluate(()=>({robot:window.__vivacityClothRobot,cloth:window.__vivacityCloth}));
 assert.equal(evidence.scene.robot.source,'measured_mujoco_robot_cloth_trace');
 assert(Object.keys(evidence.scene.robot.bodies).length>=11);assert.deepEqual(evidence.errors,[]);
 await page.screenshot({path:'artifacts/robot-cloth-initial-desktop.png',fullPage:true});
 await page.setViewportSize({width:375,height:900});await page.screenshot({path:'artifacts/robot-cloth-initial-mobile.png',fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 evidence.status='passed';console.log('Deployed Panda and measured cloth render; desktop/mobile, reduced motion and console checks passed.');
}catch(e){evidence.status='failed';evidence.failure=e.message;throw e;}finally{fs.writeFileSync('artifacts/robot-cloth-initial-verification.json',JSON.stringify(evidence,null,2));await browser.close();}
