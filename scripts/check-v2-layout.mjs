import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');
process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const output=process.argv[3]??'artifacts/v2-layout';
try{
  const page=await browser.newPage({viewport:{width:1440,height:960}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]??'http://127.0.0.1:5173/',{waitUntil:'domcontentloaded'});
  await page.getByRole('button',{name:'Run experiment',exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('canvas'),null,{timeout:60000});
  assert.equal(await page.getByRole('heading',{level:1}).count(),1);
  assert.equal(await page.getByText('Technical Inspector',{exact:true}).count(),1);
  assert.equal(await page.getByText('AN EXECUTION RUNTIME FOR AGENTS',{exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Robotics',exact:true}).count(),1);
  await page.screenshot({path:`${output}-desktop.png`,fullPage:true});
  for(const width of [768,375]){await page.setViewportSize({width,height:960});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:`${output}-${width}.png`,fullPage:true});}
  assert.deepEqual(errors,[]);
  fs.writeFileSync(`${output}.json`,JSON.stringify({passed:true,errors,viewports:[1440,768,375],url:page.url()},null,2));
  console.log('Layout checks passed at 1440, 768, 375px.');
}finally{await browser.close();}
