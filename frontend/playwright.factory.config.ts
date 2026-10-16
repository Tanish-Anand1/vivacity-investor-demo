import {defineConfig} from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

process.env.PLAYWRIGHT_BROWSERS_PATH??=path.resolve('../data/playwright');
const external=process.env.FACTORY_E2E_EXTERNAL==='1';
const baseURL=process.env.FACTORY_E2E_BASE_URL??'http://127.0.0.1:5176';
if(process.platform==='win32'){
 const temp=path.join(process.env.LOCALAPPDATA??os.tmpdir(),'Temp','vivacity-factory-e2e');fs.mkdirSync(temp,{recursive:true});
 process.env.TEMP=temp;process.env.TMP=temp;
}

export default defineConfig({
 testDir:'./e2e',testMatch:'factory-configurator.spec.ts',fullyParallel:false,workers:1,
 timeout:900_000,expect:{timeout:120_000},retries:0,
 reporter:[['list'],['json',{outputFile:'test-results/factory-configurator/report.json'}]],
 outputDir:'test-results/factory-configurator',
 use:{baseURL,channel:process.platform==='win32'?'chrome':undefined,viewport:{width:1440,height:1000},headless:true,
  launchOptions:{args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']},
  screenshot:'only-on-failure',trace:'retain-on-failure'},
 webServer:external?[]:[
  {command:'powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\start-factory-e2e.ps1 backend',cwd:path.resolve('..'),url:'http://127.0.0.1:8002/health',reuseExistingServer:true,timeout:600_000},
  {command:'powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\start-factory-e2e.ps1 frontend',cwd:path.resolve('..'),url:'http://127.0.0.1:5176',reuseExistingServer:true,timeout:180_000}
 ]
});
