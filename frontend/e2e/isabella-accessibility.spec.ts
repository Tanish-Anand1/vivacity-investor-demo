import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

test('robotics homepage has keyboard entry, measured interactions, and no serious WCAG violations',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('heading',{name:/Let robots fail here first/i})).toBeVisible();
 const shots=path.resolve('test-results/isabella-home');fs.mkdirSync(shots,{recursive:true});
 await expect(page.locator('.isabella-hero-scene')).toBeVisible();
 await page.screenshot({path:path.join(shots,'desktop.png')});
 await page.keyboard.press('Tab');
 await expect(page.getByRole('link',{name:'Skip to content'})).toBeFocused();
 await page.keyboard.press('Enter');
 await expect(page).toHaveURL('/#isabella-main');
 const audit=await new AxeBuilder({page}).include('.isabella-home').withTags(['wcag2a','wcag2aa','wcag22aa']).analyze();
 expect(audit.violations.filter(issue=>issue.impact==='serious'||issue.impact==='critical').map(issue=>({id:issue.id,nodes:issue.nodes.map(node=>node.target)}))).toEqual([]);
 const weak=page.getByRole('button',{name:/Weak grip/i});
 await weak.click();await expect(weak).toHaveAttribute('aria-pressed','true');
 await expect(page.getByText('carton not delivered')).toBeVisible();
 await page.getByRole('button',{name:/Full grip/i}).click();
 await expect(page.getByText('carton delivered', {exact:true})).toBeVisible();
 const selected=page.getByRole('button',{name:/Full grip/i});
 await selected.hover();
 expect(await selected.evaluate(element=>({background:getComputedStyle(element).backgroundColor,color:getComputedStyle(element).color}))).toEqual({background:'rgb(224, 223, 211)',color:'rgb(17, 23, 19)'});
 await page.screenshot({path:path.join(shots,'comparison.png')});
});

test('world library opens from the new homepage and loads a real robotics workspace',async({page})=>{
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
 expect(await page.locator('body').innerText()).not.toMatch(/\bMuJoCo\b/i);
});

test('a missing robot asset reports the limitation and preserves recorded measurements',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.route('**/vivacity/robot-geometry.json',route=>route.abort());
 await page.goto('/',{waitUntil:'domcontentloaded'});
 await expect(page.getByRole('alert').filter({hasText:'The 3D preview could not load.'})).toBeVisible({timeout:30_000});
 await expect(page.locator('.isabella-hero-scene')).toBeVisible();
 await page.getByRole('button',{name:'Weak grip'}).click();
 await expect(page.getByRole('status').filter({hasText:/carton not delivered/i})).toBeVisible();
});
