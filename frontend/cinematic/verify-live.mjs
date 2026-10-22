/** Exercise the delivered opening without intercepting or substituting media.
 * node cinematic/verify-live.mjs http://127.0.0.1:5178/
 * Omit the URL to verify the production host after an intentional deployment.
 */
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';

const url=process.argv[2]??'https://demo.tryvivacity.com/';
const output=path.resolve('../artifacts/the-one-live-verification.json');
const prefix='/vivacity/the-one-isabella';
const browser=await chromium.launch({headless:true,channel:process.platform==='win32'?'chrome':undefined});
const report={url,firstVisit:{},repeatVisit:{},mobile:{},reducedMotion:{},errors:[]};
const heading={name:/Let robots.*fail here.*first/i};
try{
 const context=await browser.newContext({viewport:{width:1440,height:900},reducedMotion:'no-preference'});
 const page=await context.newPage();
 page.on('pageerror',error=>report.errors.push(error.message));
 page.on('response',response=>{if(response.url().includes(prefix))report.firstVisit.videoResponse=response.status();});
 await page.addInitScript(()=>document.addEventListener('ended',event=>{
  if((event.target instanceof HTMLVideoElement)&&event.target.matches('.lab-opening-video'))window.__vivacityFilmEnd=event.target.currentTime;
 },true));
 const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30_000});
 report.firstVisit.documentStatus=response?.status();
 try{
  await page.waitForSelector('.lab-opening-video',{timeout:5_000});
  report.firstVisit.videoSource=await page.locator('.lab-opening-video').getAttribute('src');
  await page.waitForSelector('.lab-opening',{state:'detached',timeout:20_000});
 }catch(error){report.firstVisit.introError=String(error).slice(0,180);}
 report.firstVisit.mediaEnd=await page.evaluate(()=>window.__vivacityFilmEnd??null);
 await page.getByRole('heading',heading).waitFor({state:'visible',timeout:10_000});
 report.firstVisit.homeVisible=await page.getByRole('heading',heading).isVisible();
 report.firstVisit.homeInert=await page.locator('.isabella-home').getAttribute('inert');
 await page.screenshot({path:path.resolve('../artifacts/the-one-live-homepage.png')});

 let repeatMediaRequests=0;
 const countRepeat=request=>{if(request.url().includes(prefix))repeatMediaRequests++;};
 page.on('request',countRepeat);
 await page.reload({waitUntil:'domcontentloaded'});
 await page.getByRole('heading',heading).waitFor({state:'visible',timeout:10_000});
 report.repeatVisit.introCount=await page.locator('.lab-opening').count();
 report.repeatVisit.mediaRequests=repeatMediaRequests;
 page.off('request',countRepeat);
 await page.locator('.isabella-hero-actions').getByRole('button',{name:/Enter the lab/i}).click();
 await page.waitForURL('**/laboratory',{timeout:10_000});
 report.labRoute=page.url();
 await context.close();

 const mobileContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,reducedMotion:'no-preference'});
 const mobile=await mobileContext.newPage();
 mobile.on('pageerror',error=>report.errors.push(error.message));
 const mobileResponse=await mobile.goto(url,{waitUntil:'domcontentloaded',timeout:30_000});
 report.mobile.documentStatus=mobileResponse?.status();
 try{
  await mobile.waitForSelector('.lab-opening-video',{timeout:5_000});
  report.mobile.videoSource=await mobile.locator('.lab-opening-video').getAttribute('src');
  report.mobile.fit=await mobile.locator('.lab-opening-video').evaluate(video=>getComputedStyle(video).objectFit);
  await mobile.screenshot({path:path.resolve('../artifacts/the-one-live-mobile-film.png')});
  await mobile.getByRole('button',{name:/Skip intro/i}).click();
 }catch(error){report.mobile.introError=String(error).slice(0,180);}
 await mobile.getByRole('heading',heading).waitFor({state:'visible',timeout:10_000});
 report.mobile.homeVisible=await mobile.getByRole('heading',heading).isVisible();
 report.mobile.horizontalOverflow=await mobile.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 await mobile.screenshot({path:path.resolve('../artifacts/the-one-live-mobile-homepage.png')});
 await mobileContext.close();

 const reducedContext=await browser.newContext({reducedMotion:'reduce'});
 const reduced=await reducedContext.newPage();
 const reducedResponse=await reduced.goto(new URL('?intro=replay',url).href,{waitUntil:'domcontentloaded',timeout:30_000});
 report.reducedMotion.documentStatus=reducedResponse?.status();
 await reduced.getByRole('heading',heading).waitFor({state:'visible',timeout:10_000});
 report.reducedMotion.introCount=await reduced.locator('.lab-opening').count();
 report.reducedMotion.homeVisible=await reduced.getByRole('heading',heading).isVisible();
 await reducedContext.close();
}catch(error){
 report.errors.push(String(error));
}finally{
 await browser.close();
 report.passed=report.firstVisit.mediaEnd===7.5&&report.firstVisit.homeVisible&&report.firstVisit.homeInert===null
  &&[200,206].includes(report.firstVisit.videoResponse)
  &&report.labRoute===new URL('laboratory',url).href
  &&report.repeatVisit.introCount===0&&report.repeatVisit.mediaRequests===0
  &&report.mobile.documentStatus===200&&report.mobile.videoSource===`${prefix}-portrait-lite.mp4`
  &&report.mobile.fit==='contain'&&report.mobile.homeVisible&&!report.mobile.horizontalOverflow
  &&report.reducedMotion.documentStatus===200&&report.reducedMotion.introCount===0&&report.reducedMotion.homeVisible
  &&report.errors.length===0;
 fs.writeFileSync(output,JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
 if(!report.passed)process.exitCode=1;
}
