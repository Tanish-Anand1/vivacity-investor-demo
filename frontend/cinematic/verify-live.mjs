import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';

const url='https://demo.tryvivacity.com/';
const output=path.resolve('../artifacts/isabella-live-verification.json');
const browser=await chromium.launch({headless:true,channel:'chrome'});
const report={url,attempts:[],mobile:{},reducedMotion:{},errors:[]};
try{
 const context=await browser.newContext({viewport:{width:1440,height:900}});
 const page=await context.newPage();
 page.on('pageerror',error=>report.errors.push(error.message));
 page.on('response',response=>{if(response.url().includes('isabella-impossible-'))report.attempts.at(-1).videoResponse=response.status();});
 await page.addInitScript(()=>document.addEventListener('ended',event=>{
  if((event.target instanceof HTMLVideoElement)&&event.target.matches('.lab-opening-video'))window.__isabellaFilmEnd=event.target.currentTime;
 },true));
 for(let i=0;i<2;i++){
  const attempt={number:i+1};report.attempts.push(attempt);
  const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30_000});
  attempt.documentStatus=response?.status();
  try{
   await page.waitForSelector('.lab-opening-video',{timeout:5_000});
   attempt.videoSource=await page.locator('.lab-opening-video').getAttribute('src');
   await page.waitForSelector('.lab-opening',{state:'detached',timeout:20_000});
  }catch(error){attempt.introError=String(error).slice(0,180);}
  attempt.mediaEnd=await page.evaluate(()=>window.__isabellaFilmEnd??null);
  await page.getByRole('heading',{name:/Let robots fail here first/i}).waitFor({state:'visible',timeout:10_000});
  attempt.homeVisible=await page.getByRole('heading',{name:/Let robots fail here first/i}).isVisible();
  if(attempt.mediaEnd===7.5)break;
 }
 await page.screenshot({path:path.resolve('../artifacts/isabella-live-homepage.png')});
 await page.locator('.isabella-hero-actions').getByRole('button',{name:/Enter the lab/i}).click();
 await page.waitForURL('**/laboratory',{timeout:10_000});
 report.labRoute=page.url();
 await context.close();

 const mobileContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const mobile=await mobileContext.newPage();
 mobile.on('pageerror',error=>report.errors.push(error.message));
 const mobileResponse=await mobile.goto(url,{waitUntil:'domcontentloaded',timeout:30_000});
 report.mobile.documentStatus=mobileResponse?.status();
 try{
  await mobile.waitForSelector('.lab-opening-video',{timeout:5_000});
  report.mobile.videoSource=await mobile.locator('.lab-opening-video').getAttribute('src');
  await mobile.getByRole('button',{name:/Skip intro/i}).click();
 }catch(error){report.mobile.introError=String(error).slice(0,180);}
 await mobile.getByRole('heading',{name:/Let robots fail here first/i}).waitFor({state:'visible',timeout:10_000});
 report.mobile.homeVisible=await mobile.getByRole('heading',{name:/Let robots fail here first/i}).isVisible();
 report.mobile.horizontalOverflow=await mobile.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 await mobile.screenshot({path:path.resolve('../artifacts/isabella-live-mobile.png')});
 await mobileContext.close();

 const reducedContext=await browser.newContext({reducedMotion:'reduce'});
 const reduced=await reducedContext.newPage();
 const reducedResponse=await reduced.goto(url,{waitUntil:'domcontentloaded',timeout:30_000});
 report.reducedMotion.documentStatus=reducedResponse?.status();
 await reduced.getByRole('heading',{name:/Let robots fail here first/i}).waitFor({state:'visible',timeout:10_000});
 report.reducedMotion.introCount=await reduced.locator('.lab-opening').count();
 report.reducedMotion.homeVisible=await reduced.getByRole('heading',{name:/Let robots fail here first/i}).isVisible();
 await reducedContext.close();
}finally{
 await browser.close();
 report.passed=report.attempts.some(attempt=>attempt.mediaEnd===7.5&&attempt.homeVisible&&[200,206].includes(attempt.videoResponse))
  &&report.labRoute==='https://demo.tryvivacity.com/laboratory'
  &&report.mobile.documentStatus===200&&report.mobile.videoSource==='/vivacity/isabella-impossible-portrait-lite.mp4'
  &&report.mobile.homeVisible&&!report.mobile.horizontalOverflow
  &&report.reducedMotion.documentStatus===200&&report.reducedMotion.introCount===0&&report.reducedMotion.homeVisible
  &&report.errors.length===0;
 fs.writeFileSync(output,JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 if(!report.passed)process.exitCode=1;
}
