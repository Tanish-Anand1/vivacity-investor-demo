/** Render the authored WebGL scene to reproducible stills for inspection/encoding.
 * Run with `node cinematic/render.mjs preview` or `node cinematic/render.mjs film`.
 * The Vite authoring server must be listening on port 5181.
 */
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';

const mode=process.argv[2]??'preview';
const format=process.argv[3]??'landscape';
const framesPerSecond=60;
const portrait=format==='portrait';
const width=portrait?720:1440,height=portrait?1280:810;
const output=path.resolve(`../artifacts/isabella-cinema-${mode}-${format}`);
fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,channel:process.platform==='win32'?'chrome':undefined,
 args:process.platform==='win32'?[]:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
 page.on('pageerror',error=>console.error('PAGE ERROR',error.message));
 page.on('console',message=>{if(message.type()==='error')console.error('CONSOLE',message.text());});
 await page.goto('http://127.0.0.1:5181/cinematic/',{waitUntil:'domcontentloaded',timeout:120_000});
 await page.waitForFunction(()=>window.__cinemaReady===true,null,{timeout:120_000});
 await page.evaluate(()=>document.fonts.ready);
 const samples=mode==='preview'?[.3,.9,1.8,2.6,3.5,4.6,5.6,6.5,7.5]
  :mode==='detail'?[.6,1.25,1.42,1.55,1.68,1.9,2.05,2.2,3.12,3.37,3.75,4.1,5.1,6.1,6.75]
  :Array.from({length:framesPerSecond*7.5},(_,i)=>i/framesPerSecond);
 const start=performance.now();
 for(let i=0;i<samples.length;i++){
  const time=samples[i];const kind=mode==='film'?'image/jpeg':'image/png';
  const data=await page.evaluate(([t,type])=>{
   window.__setCinemaTime(t);
   return window.__cinemaCanvas.toDataURL(type,type==='image/jpeg'?.94:undefined).split(',')[1];
  },[time,kind]);
  const name=mode==='film'?`${String(i).padStart(4,'0')}.jpg`:`${String(time).replace('.','_')}s.png`;
  fs.writeFileSync(path.join(output,name),Buffer.from(data,'base64'));
  if(mode==='film'&&i%60===0)console.log(`${format}: ${i}/${samples.length}`);
 }
 console.log(JSON.stringify({mode,format,width,height,frames:samples.length,seconds:(performance.now()-start)/1000,output}));
}finally{await browser.close();}
