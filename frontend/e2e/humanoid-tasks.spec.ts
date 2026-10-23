import {expect,test} from '@playwright/test';

test('H1 traverses a physical threshold and Apollo actuates a switch from live physics jobs',async({page},testInfo)=>{
  test.setTimeout(240_000);
  const errors:string[]=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('/works',{waitUntil:'domcontentloaded'});
  await expect(page.getByRole('button',{name:'Run pickup experiment'})).toBeEnabled({timeout:60_000});

  await page.getByRole('button',{name:/Unitree H1.*Terrain mobility/}).click();
  await expect(page.getByRole('heading',{name:'Unitree H1'})).toBeVisible({timeout:60_000});
  await expect(page.getByRole('combobox',{name:'Test mode'})).toHaveValue('walk_to_goal');
  await page.getByRole('button',{name:'Run mobility trial'}).click();
  await expect(page.getByText('Task completed in simulation')).toBeVisible({timeout:60_000});
  await expect(page.locator('.humanoid-result')).toContainText(/walked to within.*of the goal/);
  await expect(page.locator('.humanoid-result')).toContainText('95th-percentile support slip');
  await expect(page.getByRole('button',{name:'Play replay'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Pause physics'})).toHaveCount(0);
  await page.screenshot({path:testInfo.outputPath('h1-measured.png'),fullPage:true});

  await page.getByRole('button',{name:/Apptronik Apollo.*Equipment control probe/}).click();
  await expect(page.getByRole('heading',{name:'Apptronik Apollo'})).toBeVisible({timeout:60_000});
  await expect(page.getByRole('combobox',{name:'Test mode'})).toHaveValue('service_machine');
  await page.getByRole('button',{name:'Run switch experiment'}).click();
  await expect(page.getByText('Switch cycle completed in simulation')).toBeVisible({timeout:60_000});
  await expect(page.locator('.humanoid-result')).toContainText(/contacted the switch, actuated the machine shaft/);
  await expect(page.locator('.humanoid-result')).toContainText('Measured floor contact friction');
  await page.screenshot({path:testInfo.outputPath('apollo-measured.png'),fullPage:true});
  await page.getByRole('button',{name:'Reset view'}).click();
  await page.getByRole('slider',{name:/Switch resistance/}).fill('16');
  await page.getByRole('button',{name:'Run switch experiment'}).click();
  await expect(page.getByText('Task not completed')).toBeVisible({timeout:60_000});
  await expect(page.locator('.humanoid-result')).toContainText(/switch not actuated/);
  await page.getByText('Compare with prior measured trial').click();
  await expect(page.locator('.humanoid-comparison')).toContainText('Succeeded');
  await expect(page.locator('.humanoid-comparison')).toContainText('Failed');
  await expect(page.locator('.humanoid-comparison')).toContainText('16.0 N·m/rad');
  expect(errors).toEqual([]);
});

test('pause freezes a real G1 physics job and resume continues its measured trace',async({page})=>{
  test.setTimeout(120_000);
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('/works',{waitUntil:'domcontentloaded'});
  await expect(page.getByRole('button',{name:'Run pickup experiment'})).toBeEnabled({timeout:60_000});
  await page.getByRole('button',{name:'Run pickup experiment'}).click();
  await page.getByRole('button',{name:'Pause physics'}).click();
  await expect(page.locator('.humanoid-result > strong')).toHaveText('Physics paused');
  const stopped=await page.locator('.humanoid-playback strong').innerText();
  await page.waitForTimeout(700);
  expect(await page.locator('.humanoid-playback strong').innerText()).toBe(stopped);
  await page.getByRole('button',{name:'Resume physics'}).click();
  await expect(page.getByText('Task completed in simulation')).toBeVisible({timeout:90_000});
  await expect(page.getByRole('button',{name:'Play replay'})).toBeVisible();
});
