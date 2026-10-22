/** Verify natural browser decoding of both delivered 60 fps main encodes.
 * Usage: node cinematic/check-high-renditions.mjs http://127.0.0.1:5178/
 * This performs real HTTP requests and does not replace video or its clock.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';

const url=process.argv[2]??'http://127.0.0.1:5178/';
const report={url,kind:'real_http_high_rendition_playback',formats:[],passed:false,errors:[]};
const browser=await chromium.launch({headless:true,channel:process.platform==='win32'?'chrome':undefined});
try{
 for(const format of ['landscape','portrait']){
  const viewport=format==='portrait'?{width:720,height:1280}:{width:1440,height:900};
  const context=await browser.newContext({viewport,reducedMotion:'no-preference'});
  const page=await context.newPage();
  const entry={format,viewport,responses:[],errors:[]};report.formats.push(entry);
  await page.addInitScript(()=>{
   Object.defineProperty(navigator,'connection',{configurable:true,value:{saveData:false,effectiveType:'4g'}});
   document.addEventListener('playing',event=>{
    if(event.target instanceof HTMLVideoElement&&event.target.matches('.lab-opening-video')&&window.__highStarted===undefined)window.__highStarted=performance.now();
   },true);
   document.addEventListener('ended',event=>{
    if(!(event.target instanceof HTMLVideoElement)||!event.target.matches('.lab-opening-video'))return;
    const quality=event.target.getVideoPlaybackQuality();
    window.__highPlayback={mediaEnd:event.target.currentTime,duration:event.target.duration,
     wallMs:performance.now()-window.__highStarted,width:event.target.videoWidth,height:event.target.videoHeight,
     totalVideoFrames:quality.totalVideoFrames,droppedVideoFrames:quality.droppedVideoFrames};
   },true);
  });
  page.on('pageerror',error=>entry.errors.push(error.message));
  page.on('response',response=>{if(response.url().includes('/vivacity/the-one-isabella-'))entry.responses.push({url:response.url(),status:response.status()});});
  const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30_000});entry.documentStatus=response?.status();
  entry.clientBundle=await page.locator('script[type="module"][src]').first().getAttribute('src');
  await page.locator('.lab-opening-video').waitFor({state:'visible',timeout:5_000});
  entry.source=await page.locator('.lab-opening-video').getAttribute('src');
  assert.equal(entry.source,`/vivacity/the-one-isabella-${format}.mp4`);
  await page.locator('.lab-opening').waitFor({state:'detached',timeout:20_000});
  entry.playback=await page.evaluate(()=>window.__highPlayback??null);
  assert.equal(entry.playback?.mediaEnd,7.5,`${format}: actual high-quality media did not reach its natural end`);
  assert.equal(entry.playback.duration,7.5);
  assert.deepEqual([entry.playback.width,entry.playback.height],format==='portrait'?[720,1280]:[1440,810]);
  await page.getByRole('heading',{name:/Let robots.*fail here.*first/i}).waitFor({state:'visible'});
  entry.home=await page.evaluate(()=>({inert:document.querySelector('.isabella-home')?.hasAttribute('inert'),focused:document.activeElement?.id}));
  assert.equal(entry.home.inert,false);assert.equal(entry.home.focused,'isabella-main');
  assert.ok(entry.responses.some(item=>item.status===200||item.status===206));
  assert.deepEqual(entry.errors,[]);
  console.log(JSON.stringify(entry));
  await context.close();
 }
 report.passed=true;
}catch(error){report.errors.push(String(error));process.exitCode=1;}
finally{
 await browser.close();
 const output=path.resolve('../artifacts/the-one-high-rendition-check.json');
 fs.writeFileSync(output,JSON.stringify(report,null,2));
 console.log(JSON.stringify({passed:report.passed,errors:report.errors,output}));
}
