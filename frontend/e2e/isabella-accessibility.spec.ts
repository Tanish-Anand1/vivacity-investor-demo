import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

test('homepage has accessible controls, keyboard entry, and no serious WCAG violations',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('heading',{name:/Explore possible worlds/i})).toBeVisible();
 const shots=path.resolve('test-results/isabella-home');fs.mkdirSync(shots,{recursive:true});
 await expect(page.locator('.isabella-hero-scene canvas')).toBeVisible({timeout:60_000});
 await page.screenshot({path:path.join(shots,'desktop.png')});
 await page.keyboard.press('Tab');
 await expect(page.getByRole('link',{name:'Skip to content'})).toBeFocused();
 await page.keyboard.press('Enter');
 await expect(page).toHaveURL('/#isabella-main');
 const audit=await new AxeBuilder({page}).include('.isabella-home').withTags(['wcag2a','wcag2aa','wcag22aa']).analyze();
 expect(audit.violations.filter(issue=>issue.impact==='serious'||issue.impact==='critical').map(issue=>({id:issue.id,description:issue.description,nodes:issue.nodes.map(node=>node.target)}))).toEqual([]);
 await page.getByRole('button',{name:/Weak grip/i}).click();
 await expect(page.getByRole('status').filter({hasText:'Measured failure'})).toBeVisible();
 const samples=page.getByLabel('Recorded sample');await samples.focus();await samples.press('Home');
 for(let step=0;step<6;step++)await samples.press('ArrowRight');
 await expect(page.getByText(/7 \/ 27/)).toBeVisible();
 await page.locator('#experiment').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(shots,'comparison.png')});
 const before=await samples.inputValue();
 await page.getByRole('button',{name:'Play recorded trial'}).click();
 await expect.poll(()=>samples.inputValue()).not.toBe(before);
 await page.getByRole('button',{name:'Pause recorded trial'}).click();
});

test('world library opens from the homepage and loads a real workspace',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await page.getByRole('button',{name:'Worlds',exact:true}).click();
 await expect(page).toHaveURL('/worlds');
 await expect(page.getByRole('heading',{name:'Environment library'})).toBeVisible({timeout:90_000});
 const enter=page.getByRole('button',{name:'Enter workspace'});
 await expect(enter).toBeEnabled({timeout:90_000});
 await enter.click();
 await expect(page).toHaveURL('/workspace');
 await expect(page.getByRole('heading',{name:'Physical experiments'})).toBeVisible({timeout:90_000});
 await expect(page.getByRole('heading',{name:'Configure experiment'})).toBeVisible({timeout:90_000});
});

test('a missing 3D asset reports the limitation and preserves recorded measurements',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.route('**/vivacity/robot-geometry.json',route=>route.abort());
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('alert').filter({hasText:'The 3D preview could not load.'})).toBeVisible({timeout:30_000});
 await page.getByRole('button',{name:/Weak grip/i}).click();
 await expect(page.getByRole('status').filter({hasText:'Measured failure'})).toBeVisible();
});
