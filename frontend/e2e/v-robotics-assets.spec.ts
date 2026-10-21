import {test,expect} from '@playwright/test';

test('the robot view can recover after an asset fetch failure',async({page})=>{
  let failures=0;
  await page.route('**/vivacity/robots/ur5e/robot-geometry.json',async route=>{
    if(failures<3){failures++;await route.abort();}
    else await route.continue();
  });
  await page.goto('/workspace');
  await page.getByRole('button',{name:'Browse programs'}).click();
  await page.getByRole('button',{name:'Open experiment'}).click();
  await expect(page.getByRole('button',{name:'Retry 3D view'})).toBeVisible({timeout:60_000});
  expect(failures).toBe(3);
  await page.getByRole('button',{name:'Retry 3D view'}).click();
  await expect(page.getByRole('button',{name:'Retry 3D view'})).toHaveCount(0,{timeout:30_000});
  await expect.poll(async()=>page.evaluate(()=>Object.keys((window as unknown as {__vivacityScene?:{bodies:Record<string,unknown>}}).__vivacityScene?.bodies??{}).length)).toBeGreaterThan(1);
});
