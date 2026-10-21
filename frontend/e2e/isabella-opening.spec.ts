import {expect,test} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('the authored 7.5-second film hands control to the real homepage',async({page})=>{
 await page.addInitScript(()=>Object.defineProperty(navigator,'connection',{configurable:true,value:{saveData:true,effectiveType:'4g'}}));
 await page.addInitScript(()=>document.addEventListener('ended',event=>{
  if((event.target as Element)?.matches?.('.lab-opening-video'))(window as typeof window&{__isabellaMediaEnd?:number}).__isabellaMediaEnd=(event.target as HTMLVideoElement).currentTime;
 },true));
 const media=fs.readFileSync(path.resolve('public/vivacity/isabella-impossible-landscape-lite.mp4'));
 await page.route('**/vivacity/isabella-impossible-landscape-lite.mp4',route=>route.fulfill({body:media,contentType:'video/mp4'}));
 await page.goto('/');
 const intro=page.getByRole('dialog',{name:'Isabella Labs introduction'});
 await expect(intro).toBeVisible();
 const video=page.locator('.lab-opening-video');
 await page.waitForFunction(()=>{
  const element=document.querySelector<HTMLVideoElement>('.lab-opening-video');
  return element&&!element.paused&&element.currentTime>.02;
 },null,{timeout:9_000});
 const shots=path.resolve('../artifacts/isabella-cinema-runtime');fs.mkdirSync(shots,{recursive:true});
 await expect.poll(()=>video.evaluate(element=>element.currentTime)).toBeGreaterThan(6.5);
 await expect(intro).toHaveCount(0,{timeout:10_000});
 expect(await page.evaluate(()=>(window as typeof window&{__isabellaMediaEnd?:number}).__isabellaMediaEnd)).toBeCloseTo(7.5,2);
 await expect(page.locator('.isabella-home')).not.toHaveAttribute('inert');
 await expect(page.getByRole('heading',{name:/Let robots.*fail here.*first/i})).toBeVisible();
 await page.screenshot({path:path.join(shots,'homepage-after-7_5s.png')});
 await page.locator('.isabella-hero-actions').getByRole('button',{name:/Enter the lab/i}).click();
 await expect(page).toHaveURL(/\/laboratory$/);
});
