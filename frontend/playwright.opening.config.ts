import {defineConfig} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';

const port=process.env.VIVACITY_OPENING_PORT??'5178';
const external=process.env.VIVACITY_OPENING_BASE_URL;
process.env.PLAYWRIGHT_BROWSERS_PATH??=path.resolve('../data/playwright');
if(process.platform==='win32'){
 const temp=path.resolve('../data/browser-temp');fs.mkdirSync(temp,{recursive:true});
 process.env.TEMP=temp;process.env.TMP=temp;
}

// This surface never starts a simulation. Keep its acceptance suite independent
// of Python workers and test the same compiled assets that would be deployed.
export default defineConfig({
 testDir:'./e2e',testMatch:'isabella-opening.spec.ts',workers:1,fullyParallel:false,
 timeout:45_000,expect:{timeout:8_000},retries:0,
 reporter:[['list'],['json',{outputFile:'../artifacts/the-one-browser-tests.json'}]],
 outputDir:'test-results/the-one-opening',
 use:{baseURL:external??`http://127.0.0.1:${port}`,viewport:{width:1440,height:900},
  channel:process.platform==='win32'?'chrome':undefined,headless:true,
  launchOptions:{args:process.platform==='win32'?[]:['--use-angle=swiftshader','--enable-unsafe-swiftshader']},
  screenshot:'only-on-failure',trace:'retain-on-failure'},
 webServer:external?undefined:{command:`npx vite preview --host 127.0.0.1 --port ${port} --strictPort`,url:`http://127.0.0.1:${port}`,reuseExistingServer:!process.env.CI,timeout:30_000}
});
