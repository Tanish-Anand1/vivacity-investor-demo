/** Record the actual browser journey using delivered files and real navigation.
 * No media interception, clock substitution, or timeline seeking occurs here.
 * Usage: node cinematic/record.mjs http://127.0.0.1:5178/
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';

const baseURL=process.argv[2]??'http://127.0.0.1:5178/';
const output=path.resolve('../artifacts');
const recordingDir=path.join(output,'the-one-browser-recordings');
fs.mkdirSync(recordingDir,{recursive:true});
const report={url:baseURL,kind:'actual_browser_recording',formats:[],passed:false,errors:[]};
const browser=await chromium.launch({headless:true,channel:process.platform==='win32'?'chrome':undefined});
try{
 for(const format of ['landscape','portrait']){
  const portrait=format==='portrait';
  const viewport=portrait?{width:390,height:844}:{width:1440,height:900};
  const context=await browser.newContext({viewport,isMobile:portrait,hasTouch:portrait,
   reducedMotion:'no-preference',recordVideo:{dir:recordingDir,size:viewport}});
  const page=await context.newPage();
  const video=page.video();
  const entry={format,viewport,mediaResponses:[],uncaughtErrors:[],physicsStarts:0};
  report.formats.push(entry);
  await page.addInitScript(()=>{
   // Exercise the actual data-saver delivery rendition used on mobile/slow links.
   Object.defineProperty(navigator,'connection',{configurable:true,value:{saveData:true,effectiveType:'4g'}});
   document.addEventListener('playing',event=>{
    if(event.target instanceof HTMLVideoElement&&event.target.matches('.lab-opening-video')&&window.__filmStarted===undefined)window.__filmStarted=performance.now();
   },true);
   document.addEventListener('ended',event=>{
    if(event.target instanceof HTMLVideoElement&&event.target.matches('.lab-opening-video')){
     window.__filmEnd=event.target.currentTime;window.__filmWallMs=performance.now()-window.__filmStarted;
    }
   },true);
  });
  page.on('pageerror',error=>entry.uncaughtErrors.push(error.message));
  page.on('response',response=>{if(response.url().includes('/vivacity/the-one-isabella-'))entry.mediaResponses.push({status:response.status(),url:response.url()});});
  page.on('request',request=>{
   if(request.method()!=='POST')return;
   const pathname=new URL(request.url()).pathname;
   if(/\/v1\/factory\/cells\/[^/]+\/(runs|benchmarks)$/.test(pathname)||/\/v1\/worlds\/[^/]+\/experiments$/.test(pathname)||pathname==='/v1/sessions')entry.physicsStarts++;
  });
  const response=await page.goto(baseURL,{waitUntil:'domcontentloaded',timeout:30_000});
  entry.documentStatus=response?.status();
  entry.clientBundle=await page.locator('script[type="module"][src]').first().getAttribute('src');
  await page.locator('.lab-opening-video').waitFor({state:'visible',timeout:5_000});
  entry.mediaSource=await page.locator('.lab-opening-video').getAttribute('src');
  await page.locator('.lab-opening').waitFor({state:'detached',timeout:20_000});
  entry.playback=await page.evaluate(()=>({mediaEnd:window.__filmEnd??null,wallMs:window.__filmWallMs??null,
   homeInert:document.querySelector('.isabella-home')?.hasAttribute('inert'),
   focused:document.activeElement?.id,overflow:document.documentElement.scrollWidth>innerWidth}));
  assert.equal(entry.playback.mediaEnd,7.5,`${format}: recording did not reach the natural media ending`);
  assert.equal(entry.playback.homeInert,false,`${format}: homepage remains inert`);
  assert.equal(entry.playback.overflow,false,`${format}: horizontal overflow`);
  await page.getByRole('heading',{name:/Let robots.*fail here.*first/i}).waitFor({state:'visible'});
  entry.homepageScreenshot=path.join(output,`the-one-browser-home-${format}.png`);
  await page.screenshot({path:entry.homepageScreenshot});
  await page.locator('.isabella-hero-actions').getByRole('button',{name:/Enter the lab/i}).click();
  await page.waitForURL('**/laboratory',{timeout:10_000});
  entry.labRoute=page.url();
  assert.equal(entry.labRoute,new URL('laboratory',baseURL).href);
  assert.equal(entry.physicsStarts,0,'Opening must not execute experiments');
  assert.deepEqual(entry.uncaughtErrors,[]);
  assert.ok(entry.mediaResponses.some(response=>response.status===200||response.status===206));
  await page.screenshot({path:path.join(output,`the-one-browser-laboratory-${format}.png`)});
  await context.close();
  entry.recording=path.join(recordingDir,`the-one-${format}-journey.webm`);
  await video.saveAs(entry.recording);
  console.log(JSON.stringify(entry));
 }
 report.passed=true;
}catch(error){
 report.errors.push(String(error));process.exitCode=1;
}finally{
 await browser.close();
 fs.writeFileSync(path.join(output,'the-one-browser-recordings.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({passed:report.passed,errors:report.errors}));
}
