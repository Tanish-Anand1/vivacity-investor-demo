/** Inspect determinism and cube continuity in the authored film source.
 * Run with the Vite authoring server on port 5181.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';

const browser=await chromium.launch({headless:true,channel:process.platform==='win32'?'chrome':undefined,
 args:process.platform==='win32'?[]:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:810},deviceScaleFactor:1});
 await page.goto('http://127.0.0.1:5181/cinematic/',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__cinemaReady===true,null,{timeout:120_000});
 await page.evaluate(()=>document.fonts.ready);
 const samples=await page.evaluate(()=>{
  const positions=[];
  for(let i=0;i<=450;i++){
   window.__setCinemaTime(i/60);
   positions.push(window.__cinemaCube);
  }
  window.__setCinemaTime(3.5);
  const first=window.__cinemaCanvas.toDataURL('image/png');
  window.__setCinemaTime(6.5);
  window.__setCinemaTime(3.5);
  const second=window.__cinemaCanvas.toDataURL('image/png');
  const transferDiagnostics=[];
  for(const t of [2.06,2.1,2.13,2.17,2.2,2.27]){
   window.__setCinemaTime(t);
   transferDiagnostics.push({t,cube:window.__cinemaCube,points:window.__cinemaPoints});
  }
  return {positions,repeatable:first===second,transferDiagnostics};
 });
 assert.equal(samples.positions.length,451);
 assert.equal(samples.repeatable,true,'Seeking to the same time must reproduce the exact frame');
 let largestStep=0,largestAt=0;
 for(let i=1;i<samples.positions.length;i++){
  const a=samples.positions[i-1],b=samples.positions[i];
  assert.equal(a.length,3);assert.equal(b.length,3);
  const step=Math.hypot(b[0]-a[0],b[1]-a[1],b[2]-a[2]);
  if(step>largestStep){largestStep=step;largestAt=i/60;}
 }
 if(largestStep>=.22)console.error(JSON.stringify(samples.transferDiagnostics));
 assert.ok(largestStep<.22,`Cube jumps ${largestStep.toFixed(3)} m in one film frame at ${largestAt.toFixed(3)} s`);
 const report={duration_s:7.5,frames:451,repeatable:samples.repeatable,max_cube_step_m:largestStep,max_cube_step_at_s:largestAt};
 const output=path.resolve('../artifacts/isabella-cinema-source-check.json');
 fs.writeFileSync(output,JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
}finally{await browser.close();}
