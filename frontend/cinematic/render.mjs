/** Render the authored WebGL scene to reproducible stills for inspection/encoding.
 * `node cinematic/render.mjs previz portrait` captures low-cost layout frames.
 * `node cinematic/render.mjs preview landscape` captures final-lighting frames.
 * `node cinematic/render.mjs film landscape` captures the full 450-frame film.
 * The Vite authoring server must be listening on port 5181.
 */
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';

const mode=process.argv[2]??'preview';
const format=process.argv[3]??'landscape';
if(!['previz','preview','detail','film'].includes(mode))throw new Error(`Unknown render mode: ${mode}`);
if(!['landscape','portrait'].includes(format))throw new Error(`Unknown film format: ${format}`);
const framesPerSecond=60;
const portrait=format==='portrait';
const previz=mode==='previz';
const width=portrait?(previz?540:720):(previz?960:1440),height=portrait?(previz?960:1280):(previz?540:810);
const output=path.resolve(`../artifacts/the-one-${mode}-${format}`);
const sourceURL=new URL(process.env.VIVACITY_CINEMA_URL??'http://127.0.0.1:5181/cinematic/');
if(previz)sourceURL.searchParams.set('previz','1');
fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,channel:process.platform==='win32'?'chrome':undefined,
 args:process.platform==='win32'?[]:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});
 const errors=[];
 page.on('pageerror',error=>{errors.push(error.message);console.error('PAGE ERROR',error.message);});
 page.on('console',message=>{if(message.type()==='error')console.error('CONSOLE',message.text());});
 await page.goto(sourceURL.href,{waitUntil:'domcontentloaded',timeout:120_000});
 await page.waitForFunction(()=>window.__cinemaReady===true,null,{timeout:120_000});
 await page.evaluate(()=>document.fonts.ready);
 const samples=mode==='preview'||previz?[.4,1.4,2.65,3.65,4.4,5.1,6,6.9,7.5]
  :mode==='detail'?[0,.4,.8,1.4,2.2,2.65,3.05,3.35,3.65,4.1,4.4,4.65,5.1,5.55,6,6.5,6.9,7.5]
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
 if(errors.length)throw new Error(`Source render failed: ${errors.join('; ')}`);
 const report={mode,format,previz,width,height,frames:samples.length,fps:framesPerSecond,
  duration_s:7.5,source:sourceURL.href,timestamps_s:samples,seconds:(performance.now()-start)/1000,
  source_metrics:await page.evaluate(()=>window.__cinemaMetrics),output};
 fs.writeFileSync(path.join(output,'render.json'),JSON.stringify(report,null,2));
 const {timestamps_s,...summary}=report;console.log(JSON.stringify(summary));
}finally{await browser.close();}
