/** Inspect the shared timeline, both camera formats, and deterministic seeking.
 * Run against the Vite authoring server on port 5181 after composition is locked.
 * `node cinematic/check.mjs --previz` checks the same transforms at lower cost;
 * omit --previz for final lighting/render determinism. This does not prove taste.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';

const previz=process.argv.includes('--previz');
const formatArg=process.argv.find(value=>value.startsWith('--format='))?.split('=')[1];
assert.ok(!formatArg||['landscape','portrait'].includes(formatArg),'--format must be landscape or portrait');
const formats=formatArg?[formatArg]:['landscape','portrait'];
const baseURL=process.env.VIVACITY_CINEMA_URL??'http://127.0.0.1:5181/cinematic/';
const sourceURL=new URL(baseURL);if(previz)sourceURL.searchParams.set('previz','1');
const output=path.resolve(`../artifacts/the-one-${previz?'previz':'source'}-check.json`);
const report={source:sourceURL.href,duration_s:7.5,fps:60,previz,formats:[],passed:false,errors:[]};
const browser=await chromium.launch({headless:true,channel:process.platform==='win32'?'chrome':undefined,
 args:process.platform==='win32'?[]:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});

function finitePoint(point,label){
 assert.equal(point.length,3,`${label} must contain three coordinates`);
 assert.ok(point.every(Number.isFinite),`${label} contains a non-finite coordinate`);
}

try{
 for(const format of formats){
  const portrait=format==='portrait';
  const width=portrait?(previz?540:720):(previz?960:1440);
  const height=portrait?(previz?960:1280):(previz?540:810);
  const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
  page.on('pageerror',error=>report.errors.push(`${format}: ${error.message}`));
  await page.goto(sourceURL.href,{waitUntil:'domcontentloaded',timeout:120_000});
  await page.waitForFunction(()=>window.__cinemaReady===true,null,{timeout:120_000});
  await page.evaluate(()=>document.fonts.ready);
  const samples=await page.evaluate(()=>{
   const frames=[];
   for(let i=0;i<=450;i++){
    window.__setCinemaTime(i/60);
    frames.push({t:window.__cinemaTime,cube:window.__cinemaCube,points:window.__cinemaPoints});
   }
   window.__setCinemaTime(3.65);const first=window.__cinemaCanvas.toDataURL('image/png');
   window.__setCinemaTime(6);window.__setCinemaTime(3.65);
   const repeatable=first===window.__cinemaCanvas.toDataURL('image/png');
   const boundaries=[];
   for(const t of [0,.8,2.2,3.05,4.65,5.55,6.5,7.5]){
    window.__setCinemaTime(t);boundaries.push({t:window.__cinemaTime,points:window.__cinemaPoints});
   }
   const focalSamples=[];
   for(const t of [.4,1.4,2.65,3.65,4.4,5.1,6,6.9,7.5]){
    window.__setCinemaTime(t);focalSamples.push({t,points:window.__cinemaPoints});
   }
   return {frames,repeatable,boundaries,focalSamples,metrics:window.__cinemaMetrics};
  });
  assert.equal(samples.frames.length,451);
  assert.equal(samples.repeatable,true,`${format}: seeking back must reproduce the exact rendered frame`);
  let largestStep=0,largestAt=0;
  const previous={split:0,join:0,entry:0};
  for(let i=0;i<samples.frames.length;i++){
   const sample=samples.frames[i];
   assert.ok(Math.abs(sample.t-i/60)<1e-9,`${format}: master clock differs at sample ${i}`);
   finitePoint(sample.cube,`${format}: cube at ${sample.t}`);
   assert.equal(sample.points.worlds.length,4,`${format}: original plus three alternate worlds`);
   sample.points.worlds.forEach((point,index)=>finitePoint(point,`${format}: world ${index} at ${sample.t}`));
   for(const phase of ['split','join','entry']){
    const progress=sample.points[phase];
    assert.ok(Number.isFinite(progress)&&progress>=0&&progress<=1,`${format}: invalid ${phase} progress`);
    assert.ok(progress>=previous[phase],`${format}: ${phase} reverses at ${sample.t}`);
    previous[phase]=progress;
   }
   // After 4.65 the architecture deliberately absorbs the original scene. Its
   // hidden cube transform is no longer the physical focal-point trajectory.
   if(i>0&&sample.t<=4.65){
    const a=samples.frames[i-1].cube,b=sample.cube;
    const step=Math.hypot(b[0]-a[0],b[1]-a[1],b[2]-a[2]);
    if(step>largestStep){largestStep=step;largestAt=sample.t;}
   }
  }
  assert.ok(largestStep<.35,`${format}: visible cube jumps ${largestStep.toFixed(3)}m in one frame at ${largestAt.toFixed(3)}s`);
  const expected=[[0,0,0],[0,0,0],[0,0,0],[0,0,0],[1,0,0],[1,1,0],[1,1,0],[1,1,1]];
  samples.boundaries.forEach((boundary,index)=>{
   assert.deepEqual([boundary.points.split,boundary.points.join,boundary.points.entry],expected[index],`${format}: locked beat at ${boundary.t}s`);
  });
  const alternatives=samples.focalSamples.find(sample=>sample.t===4.4).points.worlds;
  for(let i=0;i<alternatives.length;i++)for(let j=i+1;j<alternatives.length;j++){
   const a=alternatives[i],b=alternatives[j];
   assert.ok(Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2])>.5,`${format}: worlds ${i} and ${j} occupy the same origin during separation`);
  }
  const projections=samples.focalSamples.filter(sample=>sample.t<=4.4&&sample.points.hero_ndc);
  for(const sample of projections){
   const point=sample.points.hero_ndc;finitePoint(point,`${format}: projected hero at ${sample.t}`);
   assert.ok(Math.abs(point[0])<1&&Math.abs(point[1])<1&&point[2]>=-1&&point[2]<=1,`${format}: hero center outside frame at ${sample.t}s: ${point}`);
  }
  report.formats.push({format,width,height,frames:451,repeatable:samples.repeatable,
   cube_continuity_window_s:[0,4.65],max_cube_step_m:largestStep,max_cube_step_at_s:largestAt,
   locked_boundaries:samples.boundaries.map(({t,points})=>({t,split:points.split,join:points.join,entry:points.entry})),
   projection_checks:projections.length,visual_review_still_required:true,
   acceptance_frames:samples.focalSamples,metrics:samples.metrics});
  console.log(JSON.stringify({format,frames:451,repeatable:true,max_cube_step_m:largestStep,projection_checks:projections.length}));
  await page.close();
 }
 assert.deepEqual(report.errors,[],'Source page produced uncaught errors');
 report.passed=true;
}catch(error){
 report.errors.push(String(error));process.exitCode=1;
}finally{
 await browser.close();fs.writeFileSync(output,JSON.stringify(report,null,2));
 console.log(JSON.stringify({passed:report.passed,formats:report.formats.length,errors:report.errors,output}));
}
