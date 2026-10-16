import fs from 'node:fs';
import path from 'node:path';
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');
process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const browser=await chromium.launch({headless:true});
const results=[];
try {
  for(const [name,url] of [['brand','https://www.tryvivacity.com/'],['deployed','https://vivacity-investor-demo.vercel.app/']]){
    const page=await browser.newPage({viewport:{width:1440,height:960}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
    await page.screenshot({path:`artifacts/v2-baseline-${name}.png`,fullPage:false,timeout:30000});
    results.push({name,url,errors,...await page.evaluate(()=>({title:document.title,text:document.body.innerText.slice(0,7000),font:getComputedStyle(document.body).fontFamily,scripts:[...document.scripts].map(s=>s.src),animations:document.getAnimations().map(a=>({name:a.animationName,frames:a.effect?.getKeyframes()}))}))});
    await page.close();
  }
} finally {await browser.close();fs.writeFileSync('artifacts/v2-baseline-sites.json',JSON.stringify(results,null,2));}
console.log(JSON.stringify(results,null,2));
