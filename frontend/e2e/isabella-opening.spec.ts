import {expect,test,type Page} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const FILM='/vivacity/the-one-isabella';
const homeHeading=/Let robots.*fail here.*first/i;
const intro=(page:Page)=>page.getByRole('dialog',{name:'Isabella Labs introduction'});
const film=(page:Page)=>page.locator('.lab-opening-video');

// Serve the actual encoded deliverable from memory for decoder/lifecycle tests.
// Cold HTTP delivery is tested separately; no video, clock, or result is faked.
async function warmFilm(page:Page,format:'landscape'|'portrait'='landscape'){
 const src=`${FILM}-${format}-lite.mp4`;
 const body=fs.readFileSync(path.resolve(`public${src}`));
 await page.route(`**${src}`,route=>route.fulfill({body,contentType:'video/mp4'}));
}

async function useDataSaver(page:Page){
 await page.addInitScript(()=>Object.defineProperty(navigator,'connection',{configurable:true,value:{saveData:true,effectiveType:'4g'}}));
}

async function usableHome(page:Page,{focused=true}={}){
 await expect(intro(page)).toHaveCount(0);
 await expect(page.getByRole('heading',{name:homeHeading})).toBeVisible();
 await expect(page.locator('.isabella-home')).not.toHaveAttribute('inert');
 if(focused)await expect(page.locator('#isabella-main')).toBeFocused();
 expect(await page.evaluate(()=>document.body.style.overflow)).not.toBe('hidden');
}

test.beforeEach(async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
});

test('the actual film plays 7.5 seconds, hands off to the homepage, and starts no physics',async({page},testInfo)=>{
 await useDataSaver(page);await warmFilm(page);
 await page.addInitScript(()=>{
  const metrics=window as typeof window&{__openingStarted?:number;__openingMediaEnd?:number;__openingElapsed?:number};
  document.addEventListener('playing',event=>{
   if((event.target as Element)?.matches?.('.lab-opening-video')&&metrics.__openingStarted===undefined)metrics.__openingStarted=performance.now();
  },true);
  document.addEventListener('ended',event=>{
   if(!(event.target as Element)?.matches?.('.lab-opening-video'))return;
   metrics.__openingMediaEnd=(event.target as HTMLVideoElement).currentTime;
   metrics.__openingElapsed=performance.now()-(metrics.__openingStarted??performance.now());
  },true);
 });
 const errors:string[]=[];let physicsStarts=0;
 page.on('pageerror',error=>errors.push(error.message));
 page.on('request',request=>{
  if(request.method()!=='POST')return;
  const pathname=new URL(request.url()).pathname;
  if(/\/v1\/factory\/cells\/[^/]+\/(runs|benchmarks)$/.test(pathname)||/\/v1\/worlds\/[^/]+\/experiments$/.test(pathname)||pathname==='/v1/sessions')physicsStarts++;
 });
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(intro(page)).toBeVisible();
 await expect(film(page)).toHaveAttribute('src',`${FILM}-landscape-lite.mp4`);
 await expect.poll(()=>film(page).evaluate((element:HTMLVideoElement)=>element.readyState)).toBeGreaterThanOrEqual(3);
 const source=await film(page).evaluate((element:HTMLVideoElement)=>({duration:element.duration,muted:element.muted,rate:element.playbackRate,width:element.videoWidth,height:element.videoHeight}));
 expect(source.duration).toBeCloseTo(7.5,3);expect(source.muted).toBe(true);expect(source.rate).toBe(1);
 expect(source.width/source.height).toBeCloseTo(16/9,2);
 await expect(intro(page)).toHaveCount(0,{timeout:17_000});
 const playback=await page.evaluate(()=>{
  const metrics=window as typeof window&{__openingMediaEnd?:number;__openingElapsed?:number};
  return {mediaEnd:metrics.__openingMediaEnd,elapsedMs:metrics.__openingElapsed};
 });
 expect(playback.mediaEnd).toBeCloseTo(7.5,3);
 expect(playback.elapsedMs).toBeGreaterThanOrEqual(7_200);
 expect(playback.elapsedMs).toBeLessThan(15_000);
 await usableHome(page);
 expect(physicsStarts).toBe(0);expect(errors).toEqual([]);
 await testInfo.attach('playback-metrics',{body:JSON.stringify({...source,...playback,physicsStarts},null,2),contentType:'application/json'});
 await page.screenshot({path:testInfo.outputPath('homepage-after-opening.png')});
 await page.locator('.isabella-hero-actions').getByRole('button',{name:/Enter the lab/i}).click();
 await expect(page).toHaveURL(/\/laboratory$/);
});

test('skip is immediate and a refreshed homepage starts the opening again',async({page})=>{
 await useDataSaver(page);await warmFilm(page);
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(intro(page)).toBeVisible();
 await page.getByRole('button',{name:/Skip intro/i}).click();await usableHome(page);
 let repeatFilmRequests=0;page.on('request',request=>{if(request.url().includes(FILM))repeatFilmRequests++;});
 await page.reload({waitUntil:'domcontentloaded'});await expect(intro(page)).toBeVisible();
 await expect.poll(()=>repeatFilmRequests).toBeGreaterThan(0);
 await page.keyboard.press('Escape');await usableHome(page);
 await page.goto('/?intro=replay',{waitUntil:'domcontentloaded'});await expect(intro(page)).toBeVisible();
 await page.keyboard.press('Escape');await usableHome(page);
});

test('sound needs a gesture and keyboard focus stays inside the opening until Escape',async({page})=>{
 await useDataSaver(page);await warmFilm(page);
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(intro(page)).toBeVisible();
 await expect(page.getByRole('button',{name:/Skip intro/i})).toBeFocused();
 expect(await film(page).evaluate((element:HTMLVideoElement)=>element.muted)).toBe(true);
 await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Sound off'})).toBeFocused();
 await page.keyboard.press('Enter');
 await expect(page.getByRole('button',{name:'Sound on'})).toHaveAttribute('aria-pressed','true');
 expect(await film(page).evaluate((element:HTMLVideoElement)=>element.muted)).toBe(false);
 await page.keyboard.press('Shift+Tab');await expect(page.getByRole('button',{name:/Skip intro/i})).toBeFocused();
 await page.keyboard.press('Escape');await usableHome(page);
});

test('unavailable browser storage cannot prevent skip or homepage use',async({page})=>{
 await page.addInitScript(()=>{
  const read=Storage.prototype.getItem,write=Storage.prototype.setItem;
  Storage.prototype.getItem=function(key:string){if(key.startsWith('vivacity:opening:'))throw new DOMException('Storage denied','SecurityError');return read.call(this,key);};
  Storage.prototype.setItem=function(key:string,value:string){if(key.startsWith('vivacity:opening:'))throw new DOMException('Storage denied','SecurityError');return write.call(this,key,value);};
 });
 await useDataSaver(page);await warmFilm(page);
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(intro(page)).toBeVisible();
 await page.keyboard.press('Escape');await usableHome(page);
 await page.locator('.isabella-hero-actions').getByRole('button',{name:/Enter the lab/i}).click();
 await expect(page).toHaveURL(/\/laboratory$/);expect(errors).toEqual([]);
});

test('reduced motion bypasses even explicit replay without downloading a film',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 let filmRequests=0;page.on('request',request=>{if(request.url().includes(FILM))filmRequests++;});
 await page.goto('/?intro=replay',{waitUntil:'domcontentloaded'});await usableHome(page,{focused:false});
 expect(filmRequests).toBe(0);
 await page.locator('.isabella-hero-actions').getByRole('button',{name:/Enter the lab/i}).click();
 await expect(page).toHaveURL(/\/laboratory$/);
});

test('changing the motion preference during playback exits safely',async({page})=>{
 await useDataSaver(page);await warmFilm(page);
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(intro(page)).toBeVisible();
 await page.emulateMedia({reducedMotion:'reduce'});await usableHome(page);
});

for(const width of [390,320])test(`portrait framing keeps the full film and controls at ${width}px`,async({page},testInfo)=>{
 await page.setViewportSize({width,height:844});await warmFilm(page,'portrait');
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(intro(page)).toBeVisible();
 await expect(film(page)).toHaveAttribute('src',`${FILM}-portrait-lite.mp4`);
 await expect.poll(()=>film(page).evaluate((element:HTMLVideoElement)=>element.currentTime)).toBeGreaterThan(.1);
 const display=await film(page).evaluate((element:HTMLVideoElement)=>({ratio:element.videoWidth/element.videoHeight,fit:getComputedStyle(element).objectFit,overflow:document.documentElement.scrollWidth>innerWidth}));
 expect(display.ratio).toBeCloseTo(9/16,2);expect(display.fit).toBe('contain');expect(display.overflow).toBe(false);
 const skip=page.getByRole('button',{name:/Skip intro/i});await expect(skip).toBeInViewport();
 const bounds=await skip.boundingBox();expect(bounds?.height).toBeGreaterThanOrEqual(44);
 await page.screenshot({path:testInfo.outputPath(`opening-${width}px.png`)});
 await skip.click();await usableHome(page);
});

test('resizing within the frame orientation preserves the film; rotation exits without a restart',async({page})=>{
 await useDataSaver(page);await warmFilm(page);
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(intro(page)).toBeVisible();
 await expect.poll(()=>film(page).evaluate((element:HTMLVideoElement)=>element.currentTime)).toBeGreaterThan(.2);
 const before=await film(page).evaluate((element:HTMLVideoElement)=>element.currentTime);
 await page.setViewportSize({width:1280,height:800});await expect(intro(page)).toBeVisible();
 expect(await film(page).evaluate((element:HTMLVideoElement)=>element.currentTime)).toBeGreaterThanOrEqual(before);
 await page.setViewportSize({width:390,height:844});await usableHome(page);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
});

test('a failed media request leaves an interactive homepage',async({page})=>{
 await page.route(`**${FILM}-*.mp4`,route=>route.abort());
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(intro(page)).toHaveCount(0,{timeout:5_000});await usableHome(page);
 await page.locator('.isabella-hero-actions').getByRole('button',{name:/Enter the lab/i}).click();
 await expect(page).toHaveURL(/\/laboratory$/);
});

test('a stalled download falls through promptly without input or scroll traps',async({page})=>{
 await page.route(`**${FILM}-*.mp4`,async route=>{
  await new Promise(resolve=>setTimeout(resolve,3_500));await route.abort().catch(()=>{});
 });
 await page.goto('/',{waitUntil:'commit'});
 await expect(intro(page)).toHaveCount(0,{timeout:4_500});await usableHome(page);
});

test('autoplay rejection reveals the usable homepage',async({page})=>{
 await page.addInitScript(()=>{
  const play=HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play=function(){return this.matches('.lab-opening-video')?Promise.reject(new DOMException('Autoplay denied','NotAllowedError')):play.call(this);};
 });
 await useDataSaver(page);await warmFilm(page);
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(intro(page)).toHaveCount(0,{timeout:5_000});await usableHome(page);
});

test('cold HTTP delivery serves a playable portrait film or a clean network fallback',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 const statuses:number[]=[];
 page.on('response',response=>{if(response.url().includes(`${FILM}-portrait-lite.mp4`))statuses.push(response.status());});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect.poll(()=>page.evaluate(()=>{
  const element=document.querySelector<HTMLVideoElement>('.lab-opening-video');
  return !element?'fallback':element.currentTime>0?'playing':'pending';
 }),{timeout:5_500}).not.toBe('pending');
 if(await film(page).count()){
  expect(statuses.some(status=>status===200||status===206)).toBe(true);
  await page.getByRole('button',{name:/Skip intro/i}).click();
 }
 await usableHome(page);
});

test('a data-saver desktop selects the smaller landscape rendition',async({page})=>{
 await useDataSaver(page);await warmFilm(page);
 await page.goto('/',{waitUntil:'domcontentloaded'});await expect(film(page)).toHaveAttribute('src',`${FILM}-landscape-lite.mp4`);
 await page.getByRole('button',{name:/Skip intro/i}).click();await usableHome(page);
});

test('metadata initiates real playback even when a canplay notification is delayed',async({page})=>{
 await page.addInitScript(()=>{
  // Withhold only this notification. The browser still downloads, decodes, and
  // plays the actual delivered film; no media frames or clock are substituted.
  document.addEventListener('canplay',event=>{
   if((event.target as Element)?.matches?.('.lab-opening-video'))event.stopImmediatePropagation();
  },true);
  document.addEventListener('ended',event=>{
   if((event.target as Element)?.matches?.('.lab-opening-video'))(window as typeof window&{__metadataFilmEnd?:number}).__metadataFilmEnd=(event.target as HTMLVideoElement).currentTime;
  },true);
 });
 await useDataSaver(page);await warmFilm(page);
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(intro(page)).toBeVisible();
 await expect.poll(()=>film(page).evaluate((element:HTMLVideoElement)=>element.currentTime)).toBeGreaterThan(.1);
 await expect(intro(page)).toHaveCount(0,{timeout:15_000});
 expect(await page.evaluate(()=>(window as typeof window&{__metadataFilmEnd?:number}).__metadataFilmEnd)).toBeCloseTo(7.5,3);
 await usableHome(page);
});

test('a decoder with metadata gets bounded startup time and cannot trap the homepage',async({page})=>{
 await page.addInitScript(()=>{
  const play=HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play=function(){
   if(!this.matches('.lab-opening-video'))return play.call(this);
   const state=window as typeof window&{__decoderAttemptAt?:number;__decoderAttempts?:number};
   state.__decoderAttemptAt??=performance.now();state.__decoderAttempts=(state.__decoderAttempts??0)+1;
   // Model an unresponsive decoder promise after real metadata arrives. This
   // is a failure-recovery test and never represents successful film playback.
   return new Promise<void>(()=>{});
  };
 });
 await useDataSaver(page);await warmFilm(page);
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect.poll(()=>film(page).evaluate((element:HTMLVideoElement)=>element.readyState)).toBeGreaterThanOrEqual(1);
 await page.waitForFunction(()=>{
  const started=(window as typeof window&{__decoderAttemptAt?:number}).__decoderAttemptAt;
  return started!==undefined&&performance.now()-started>2_600;
 });
 await expect(intro(page)).toBeVisible();
 expect(await page.evaluate(()=>(window as typeof window&{__decoderAttempts?:number}).__decoderAttempts)).toBe(1);
 await expect(intro(page)).toHaveCount(0,{timeout:4_000});
 await usableHome(page);
});
