import {defineConfig} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';

process.env.PLAYWRIGHT_BROWSERS_PATH??=path.resolve('../data/playwright');
if(process.platform==='win32'){
  const temp=path.resolve('../data/browser-temp');
  fs.mkdirSync(temp,{recursive:true});
  process.env.TEMP=temp;process.env.TMP=temp;
}

export default defineConfig({
  testDir:'./e2e',
  testMatch:/(humanoid-pickup|humanoid-tasks)\.spec\.ts/,
  workers:1,fullyParallel:false,retries:0,timeout:420_000,
  expect:{timeout:90_000},
  reporter:[['list']],outputDir:'test-results-live',
  use:{baseURL:process.env.VIVACITY_LIVE_URL??'https://demo.tryvivacity.com',
    viewport:{width:1440,height:1080},headless:true,
    channel:process.platform==='win32'?'chrome':undefined,
    launchOptions:{args:process.platform==='win32'?[]:['--use-angle=swiftshader','--enable-unsafe-swiftshader']},
    screenshot:'only-on-failure',trace:'retain-on-failure'},
});
