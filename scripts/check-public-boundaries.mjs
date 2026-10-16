// Cheap real SciPy journey for console, reload, alias and network recovery.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
process.chdir(path.resolve(import.meta.dirname,'..'));
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('data/playwright');
process.env.TEMP=process.env.TMP=path.resolve('data/browser-temp');
const {chromium}=await import('../frontend/node_modules/playwright-core/index.mjs');
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const api=process.env.API_URL??JSON.parse(fs.readFileSync('data/public/endpoint.json','utf8').replace(/^\uFEFF/, '')).apiUrl;
const urls=process.env.UI_URL?[process.env.UI_URL]:['https://demo.tryvivacity.com/','https://vivacity-investor-demo.vercel.app/'];
const prefix=process.env.BOUNDARY_PROOF_PREFIX??'master-public';
const proof={checks:[],errors:[],expected_offline_errors:[],started_unix_s:Date.now()/1000};
try{
  for(const url of urls){
    const context=await browser.newContext({viewport:{width:375,height:900},reducedMotion:'reduce'});
    await context.addInitScript(()=>localStorage.setItem('vivacity:lab','scipy'));
    const page=await context.newPage();let fault=false;
    page.on('pageerror',error=>proof.errors.push(error.message));
    page.on('console',message=>{if(message.type()==='error')(fault?proof.expected_offline_errors:proof.errors).push(message.text());});
    await page.route(`${api}/v1/sessions`,async route=>{
      if(route.request().method()!=='POST')return route.continue();
      const body=route.request().postDataJSON();body.max_cycles=1;await route.continue({postData:JSON.stringify(body)});
    });
    await page.goto(url,{waitUntil:'domcontentloaded'});
    await page.getByRole('button',{name:'Start experiments',exact:true}).click();
    await page.getByTestId('branch-row').first().waitFor({timeout:90000});
    await page.waitForFunction(()=>window.__vivacityScience?.predictedPosition,{timeout:60000});
    const layout=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,
      overflow:[...document.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>innerWidth+1)
        .slice(0,20).map(e=>({tag:e.tagName,class:e.className,right:e.getBoundingClientRect().right}))}));
    if(layout.scroll>layout.width){proof.layout_failure=layout;await page.screenshot({path:`artifacts/${prefix}-discovery-overflow.png`,fullPage:true});}
    assert(layout.scroll<=layout.width,JSON.stringify(layout));
    if(url.includes('demo.tryvivacity.com'))await page.screenshot({path:`artifacts/${prefix}-discovery-mobile.png`,fullPage:true});
    const session=await page.evaluate(()=>localStorage.getItem('vivacity:scipy:session'));
    await page.reload({waitUntil:'domcontentloaded'});
    await page.getByTestId('branch-row').first().waitFor({timeout:60000});
    assert.equal(await page.evaluate(()=>localStorage.getItem('vivacity:scipy:session')),session);
    fault=true;await page.route(`${api}/v1/sessions/*`,route=>route.abort('connectionfailed'));
    await page.getByText('Simulation runtime unavailable.',{exact:true}).waitFor({timeout:15000});
    assert.equal(await page.getByTestId('branch-row').count(),2);
    await page.unroute(`${api}/v1/sessions/*`);
    await page.getByRole('button',{name:'Reconnect',exact:true}).first().click();
    await page.waitForFunction(()=>document.querySelector('.connection')?.textContent==='Viva Physics connected',{timeout:30000});
    await page.getByTestId('branch-row').first().waitFor({timeout:60000});
    fault=false;proof.checks.push({url,real_fits:true,reload_reuses_session:true,narrow_no_overflow:true,offline_preserves_evidence:true,reconnect:true});
    await context.close();
  }
  assert.deepEqual(proof.errors,[]);proof.status='passed';console.log(`${urls.length} live origin(s): real fits, console, direct reload and offline recovery passed.`);
}catch(error){proof.status='failed';proof.failure=error.message;throw error;}
finally{proof.finished_unix_s=Date.now()/1000;fs.writeFileSync(`artifacts/${prefix}-boundaries.json`,JSON.stringify(proof,null,2));await browser.close();}
