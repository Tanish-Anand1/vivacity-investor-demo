import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const apiBase=process.env.FACTORY_E2E_API_BASE_URL??'http://127.0.0.1:8002';

test('warmed opening media plays the complete 7.5-second film',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.addInitScript(()=>Object.defineProperty(navigator,'connection',{configurable:true,value:{saveData:true,effectiveType:'4g'}}));
 const media=fs.readFileSync(path.resolve('public/vivacity/isabella-impossible-landscape-lite.mp4'));
 await page.route('**/vivacity/isabella-impossible-landscape-lite.mp4',route=>route.fulfill({body:media,contentType:'video/mp4'}));
 await page.addInitScript(()=>{
  let started:number|undefined;
  const result=window as typeof window&{__uncapturedOpeningMs?:number};
  const observer=new MutationObserver(()=>{
   const present=Boolean(document.querySelector('.lab-opening'));
   if(present&&started===undefined)started=performance.now();
   if(!present&&started!==undefined){result.__uncapturedOpeningMs=performance.now()-started;observer.disconnect();}
  });
  observer.observe(document,{childList:true,subtree:true});
 });
 await page.goto('/',{waitUntil:'commit'});
 const opening=page.getByRole('dialog',{name:'Isabella Labs introduction'});
 await expect(opening).toBeVisible();
 await expect(opening).toHaveCount(0,{timeout:10_000});
 const elapsed=await page.evaluate(()=>(window as typeof window&{__uncapturedOpeningMs?:number}).__uncapturedOpeningMs);
 console.log('ISABELLA_UNCAPTURED_DURATION_MS',elapsed);
 expect(elapsed).toBeGreaterThanOrEqual(7300);
 expect(elapsed).toBeLessThan(8500);
 await expect(page.locator('#isabella-main')).toBeFocused();
});

test('the 7.5-second robotics opening reveals the homepage without starting physics',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.addInitScript(()=>{
  let started:number|undefined;
  const lifecycle=window as typeof window&{__openingDurationMs?:number};
  const observer=new MutationObserver(()=>{
   const present=Boolean(document.querySelector('.lab-opening'));
   if(present&&started===undefined)started=performance.now();
   if(!present&&started!==undefined&&lifecycle.__openingDurationMs===undefined){lifecycle.__openingDurationMs=performance.now()-started;observer.disconnect();}
  });
  observer.observe(document,{childList:true,subtree:true});
 });
 let starts=0;
 page.on('request',request=>{if(request.method()!=='POST')return;const path=new URL(request.url()).pathname;if(/\/v1\/factory\/cells\/[^/]+\/(runs|benchmarks)$/.test(path)||/\/v1\/worlds\/[^/]+\/experiments$/.test(path)||path==='/v1/sessions')starts++;});
 await page.goto('/',{waitUntil:'commit'});
 const opening=page.getByRole('dialog',{name:'Isabella Labs introduction'});
 await expect(opening).toBeVisible();
 const film=page.locator('.lab-opening-video');
 await expect(film).toHaveAttribute('src',/\/vivacity\/isabella-impossible-landscape(?:-lite)?\.mp4/,{timeout:5000});
 await expect.poll(()=>film.evaluate((element:HTMLVideoElement)=>element.readyState)).toBeGreaterThanOrEqual(3);
 expect(await film.evaluate((element:HTMLVideoElement)=>element.duration)).toBeCloseTo(7.5,2);
 expect(await film.evaluate((element:HTMLVideoElement)=>element.muted)).toBe(true);
 const shots=path.resolve('test-results/isabella-opening');fs.mkdirSync(shots,{recursive:true});
 for(const [time,label] of [[1.5,'arms'],[3.5,'humanoids']] as const){
  await expect.poll(()=>film.evaluate((element:HTMLVideoElement)=>element.currentTime)).toBeGreaterThan(time);
  await page.screenshot({path:path.join(shots,`desktop-${label}.png`)});
 }
 const playback=await film.evaluate((element:HTMLVideoElement)=>{
  const quality=element.getVideoPlaybackQuality();
  return {time:element.currentTime,totalVideoFrames:quality.totalVideoFrames,droppedVideoFrames:quality.droppedVideoFrames};
 });
 expect(playback.totalVideoFrames).toBeGreaterThan(90);
 console.log('ISABELLA_FILM_PLAYBACK',JSON.stringify(playback));
 await expect(opening).toHaveCount(0,{timeout:9000});
 const elapsed=await page.evaluate(()=>(window as typeof window&{__openingDurationMs?:number}).__openingDurationMs);
 console.log('ISABELLA_OPENING_DURATION_MS',elapsed);
 expect(elapsed).toBeDefined();
 expect(elapsed).toBeGreaterThanOrEqual(7300);
 expect(elapsed).toBeLessThan(9000);
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 await expect(page.locator('#isabella-main')).toBeFocused({timeout:5_000});
 await expect(page).toHaveURL('/');
 expect(starts).toBe(0);
 expect(await page.evaluate(()=>document.body.style.overflow)).not.toBe('hidden');
 await page.evaluate(()=>localStorage.setItem('vivacity:isabella-intro-complete','1'));
 await page.reload({waitUntil:'commit'});
 await expect(opening).toBeVisible();
 await expect(page.getByRole('button',{name:'Sound off'})).toBeVisible();
 await page.getByRole('button',{name:'Sound off'}).click();
 await expect(page.getByRole('button',{name:'Sound on'})).toHaveAttribute('aria-pressed','true');
 await expect.poll(()=>film.evaluate((element:HTMLVideoElement)=>element.muted)).toBe(false);
 await page.keyboard.press('Tab');
 await expect(page.getByRole('button',{name:/Skip intro/i})).toBeFocused();
 await page.keyboard.press('Tab');
 await expect(page.getByRole('button',{name:'Sound on'})).toBeFocused();
 await page.keyboard.press('Escape');
 await expect(opening).toHaveCount(0);
 await expect(page.locator('#isabella-main')).toBeFocused();
 expect(starts).toBe(0);
});

test('the opening plays on narrow screens and can be skipped',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.setViewportSize({width:390,height:844});
 const media=fs.readFileSync(path.resolve('public/vivacity/isabella-impossible-portrait-lite.mp4'));
 await page.route('**/vivacity/isabella-impossible-portrait-lite.mp4',route=>route.fulfill({body:media,contentType:'video/mp4'}));
 await page.goto('/',{waitUntil:'commit'});
 const opening=page.getByRole('dialog',{name:'Isabella Labs introduction'});
 await expect(opening).toBeVisible();
 const film=page.locator('.lab-opening-video');
 await expect(film).toHaveAttribute('src','/vivacity/isabella-impossible-portrait-lite.mp4',{timeout:5000});
 await expect.poll(()=>film.evaluate((element:HTMLVideoElement)=>element.readyState)).toBeGreaterThanOrEqual(3);
 const shots=path.resolve('test-results/isabella-opening');fs.mkdirSync(shots,{recursive:true});
 await expect.poll(()=>film.evaluate((element:HTMLVideoElement)=>element.currentTime)).toBeGreaterThan(2);
 await page.screenshot({path:path.join(shots,'mobile-film.png')});
 await expect(page.getByRole('button',{name:/Skip intro/i})).toBeVisible();
 await page.getByRole('button',{name:/Skip intro/i}).click();
 await expect(opening).toHaveCount(0);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
 await page.setViewportSize({width:320,height:740});
 await page.reload({waitUntil:'commit'});
 await expect(opening).toBeVisible();
 await expect(film).toHaveAttribute('src','/vivacity/isabella-impossible-portrait-lite.mp4',{timeout:5000});
 await expect.poll(()=>film.evaluate((element:HTMLVideoElement)=>element.currentTime)).toBeGreaterThan(2);
 await page.screenshot({path:path.join(shots,'mobile-small-film.png')});
 await page.getByRole('button',{name:/Skip intro/i}).click();
});

test('cold portrait delivery plays or exits cleanly on a slow connection',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.setViewportSize({width:390,height:844});
 await page.goto('/',{waitUntil:'commit'});
 await expect(page.locator('.lab-opening-video')).toHaveAttribute('src','/vivacity/isabella-impossible-portrait-lite.mp4',{timeout:5000});
 await expect.poll(()=>page.evaluate(()=>{
  const video=document.querySelector<HTMLVideoElement>('.lab-opening-video');
  if(!video)return 'fallback';
  return video.readyState>=HTMLMediaElement.HAVE_FUTURE_DATA?'playing':'pending';
 }),{timeout:5500}).not.toBe('pending');
 const outcome=await page.evaluate(()=>document.querySelector<HTMLVideoElement>('.lab-opening-video')?'playing':'fallback');
 console.log('ISABELLA_COLD_PORTRAIT',outcome);
 if(await page.locator('.lab-opening-video').count()){
  await expect.poll(()=>page.locator('.lab-opening-video').evaluate((element:HTMLVideoElement)=>element.currentTime)).toBeGreaterThan(0);
  await page.getByRole('button',{name:/Skip intro/i}).click();
 }
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
});

test('intro media failure falls through to the usable homepage',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.route('**/vivacity/isabella-impossible-*.mp4',route=>route.abort());
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('dialog',{name:'Isabella Labs introduction'})).toHaveCount(0,{timeout:5000});
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 await expect(page.locator('#isabella-main')).toBeFocused();
});

test('a stalled intro download reveals the homepage promptly',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.route('**/vivacity/isabella-impossible-*.mp4',async route=>{
  await new Promise(resolve=>setTimeout(resolve,3500));
  await route.abort().catch(()=>{});
 });
 await page.goto('/',{waitUntil:'commit'});
 await expect(page.getByRole('dialog',{name:'Isabella Labs introduction'})).toHaveCount(0,{timeout:4500});
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
});

test('data saver receives the smaller rendition',async({page})=>{
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.addInitScript(()=>Object.defineProperty(navigator,'connection',{configurable:true,value:{saveData:true,effectiveType:'4g'}}));
 await page.goto('/',{waitUntil:'commit'});
 const film=page.locator('.lab-opening-video');
 await expect(film).toHaveAttribute('src','/vivacity/isabella-impossible-landscape-lite.mp4',{timeout:5000});
 await expect.poll(()=>film.evaluate((element:HTMLVideoElement)=>element.currentTime),{timeout:6000}).toBeGreaterThan(0);
 await page.getByRole('button',{name:/Skip intro/i}).click();
 await expect(page.locator('#isabella-main')).toBeFocused();
});

test('homepage starts a real failure and six matched MuJoCo trials, then Research replays a saved run',async({page,request})=>{
 test.setTimeout(process.env.FACTORY_E2E_EXTERNAL==='1'?1_800_000:900_000);
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 await page.locator('.isabella-primary').click();
 await expect(page).toHaveURL('/laboratory');
 await page.getByRole('button',{name:/Open robotics lab/i}).click();
 await expect(page).toHaveURL('/lab');
 await expect(page.getByRole('button',{name:'Run baseline',exact:true})).toBeEnabled({timeout:90_000});
 await page.goBack();
 await expect(page).toHaveURL('/laboratory');
 await page.goBack();
 await expect(page).toHaveURL('/');
 await page.getByRole('button',{name:'OPEN ROBOTICS EXPERIMENT'}).click();
 await expect(page).toHaveURL('/lab');
 await expect(page.getByRole('heading',{name:'A package loses its grip.'})).toBeVisible({timeout:90_000});
 await page.getByRole('button',{name:'Run baseline',exact:true}).click();
 // This contract test keeps the physics identical while using the lightweight
 // viewport; the high-fidelity scene is inspected separately in visual QA.
 await page.getByRole('button',{name:'Research',exact:true}).click();
 await page.getByRole('combobox',{name:'View',exact:true}).selectOption('performance');
 await page.getByRole('button',{name:'Explore',exact:true}).click();
 await expect(page.locator('.lab-guide .lab-outcome').first()).toContainText('failed',{timeout:300_000});
 const cellId=await page.evaluate(()=>localStorage.getItem('vivacity:factory-cell'));
 const token=await page.evaluate(()=>localStorage.getItem('vivacity:workspace-capability'));
 expect(cellId).toBeTruthy();expect(token).toBeTruthy();
 await expect(page.locator('.lab-guide .lab-outcome').first()).toContainText('0 of 1 delivered');
 const baselineResponse=await request.get(`${apiBase}/v1/factory/cells/${cellId}`,{headers:{'X-Workspace-Token':token!}});
 expect(baselineResponse.ok()).toBeTruthy();
 const cell=await baselineResponse.json();
 const baselineRun=await(await request.get(`${apiBase}/v1/factory/runs/${cell.last_run_id}`,{headers:{'X-Workspace-Token':token!}})).json();
 expect(baselineRun.status).toBe('failed');
 expect(baselineRun.metrics.simulation_steps).toBeGreaterThan(1000);
 expect(baselineRun.metrics.cartons_sorted).toBe(0);
 expect(baselineRun.phase).toBe('dropped_object');

 await page.getByRole('button',{name:'Test both conditions · 6 trials'}).click();
 await expect(page.getByRole('button',{name:'Inspect completed trials while testing continues'})).toBeVisible({timeout:120_000});
 await page.getByRole('button',{name:'Inspect completed trials while testing continues'}).click();
 await expect(page.getByRole('button',{name:'Research',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.locator('.factory-benchmark > summary').click();
 await page.locator('.factory-benchmark-result .factory-trial-list li').first().getByRole('button',{name:'Inspect trial'}).click();
 await expect(page.getByRole('slider',{name:'Recorded sample'})).toBeVisible({timeout:90_000});
 expect(await page.evaluate(()=>localStorage.getItem('vivacity:factory-cell'))).toBe(cellId);
 await page.getByRole('button',{name:'Return to latest'}).click();
 await page.getByRole('button',{name:'Explore',exact:true}).click();
 await expect(page.getByRole('button',{name:'Inspect trials and replay'})).toBeVisible({timeout:process.env.FACTORY_E2E_EXTERNAL==='1'?1_500_000:300_000});
 const recordsResponse=await request.get(`${apiBase}/v1/factory/benchmarks`,{headers:{'X-Workspace-Token':token!}});
 expect(recordsResponse.ok()).toBeTruthy();
 const records=await recordsResponse.json();
 const benchmark=records.find((record:{cell_id:string})=>record.cell_id===cellId);
 expect(benchmark?.status).toBe('completed');
 expect(benchmark.trials).toHaveLength(6);
 expect(benchmark.trials.every((trial:{metrics:{simulation_steps:number}})=>trial.metrics.simulation_steps>1000)).toBe(true);
 expect(benchmark.comparison.partitions.training.baseline.successes).toBe(0);
 expect(benchmark.comparison.partitions.training.candidate.successes).toBeGreaterThan(0);
 expect(benchmark.comparison.partitions.held_out.baseline.trials).toBe(1);
 expect(benchmark.comparison.partitions.held_out.candidate.trials).toBe(1);
 expect(benchmark.comparison.selected_condition).toBe('candidate');
 console.log('LAB_E2E_BENCHMARK',JSON.stringify({id:benchmark.id,wall_time_s:benchmark.wall_time_s,training:benchmark.comparison.partitions.training,held_out:benchmark.comparison.partitions.held_out,steps:benchmark.trials.map((trial:{metrics:{simulation_steps:number}})=>trial.metrics.simulation_steps)}));
 await page.getByRole('button',{name:'Inspect trials and replay'}).click();
 await expect(page.getByRole('button',{name:'Research',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.locator('.factory-benchmark > summary').click();
 const candidate=page.locator('.factory-benchmark-result .factory-trial-list li').filter({hasText:'training / candidate'}).first();
 await candidate.getByRole('button',{name:'Inspect trial'}).click();
 const slider=page.getByRole('slider',{name:'Recorded sample'});
 await expect(slider).toBeVisible({timeout:90_000});
 await slider.focus();await slider.press('Home');
 await expect(page.getByText(/Viewport: recorded sample/)).toBeVisible();
 const csvPromise=page.waitForEvent('download');
 await page.getByRole('button',{name:'Export CSV'}).click();
 const csv=await csvPromise;
 expect(csv.suggestedFilename()).toMatch(/\.csv$/);
 const csvPath=await csv.path();
 expect(csvPath).toBeTruthy();
 expect(fs.readFileSync(csvPath!,'utf8')).toContain('time_s');
 const exportResponse=await request.get(`${apiBase}/v1/factory/benchmarks/${benchmark.id}/export`,{headers:{'X-Workspace-Token':token!}});
 expect(exportResponse.ok()).toBeTruthy();
 const exported=await exportResponse.json();
 expect(exported.schema_version).toBe('vivacity.factory-exchange/1.0');
 expect(exported.kind).toBe('benchmark');
});

test('reduced motion enters directly and the narrow layout has no horizontal overflow',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.setViewportSize({width:390,height:844});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('dialog',{name:'Isabella Labs introduction'})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 const mobileShots=path.resolve('test-results/isabella-home');fs.mkdirSync(mobileShots,{recursive:true});
 await page.screenshot({path:path.join(mobileShots,'mobile.png')});
 await page.locator('.isabella-primary').click();
 await page.getByRole('button',{name:/Open robotics lab/i}).click();
 await expect(page.getByRole('button',{name:'Run baseline'})).toBeEnabled({timeout:90_000});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)).toBe(false);
 await page.getByRole('button',{name:'Research',exact:true}).click();
 await expect(page.getByRole('button',{name:'Start production'})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)).toBe(false);
});
