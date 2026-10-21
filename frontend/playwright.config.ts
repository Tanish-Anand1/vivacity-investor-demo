import { defineConfig } from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';
// Use an isolated production-preview port so a developer's Vite/HMR session
// cannot silently substitute its compile-time behavior for the shipped build.
const appPort=process.env.VIVACITY_E2E_PORT??'5174';

// Keep downloaded browsers and temporary files on the project drive on Windows.
process.env.PLAYWRIGHT_BROWSERS_PATH ??= path.resolve('../data/playwright');
if(process.platform==='win32'){
  const temp=path.resolve('../data/browser-temp'); fs.mkdirSync(temp,{recursive:true});
  process.env.TEMP=temp;process.env.TMP=temp;
}
export default defineConfig({
  testDir:'./e2e', fullyParallel:false, workers:1, timeout:420_000,
  expect:{timeout:30_000}, retries:0,
  reporter:[['list'],['json',{outputFile:process.env.VIVACITY_TEST_REPORT??'../artifacts/v2-final-browser-tests.json'}]],
  outputDir:'test-results',
  use:{baseURL:`http://127.0.0.1:${appPort}`,viewport:{width:1440,height:1080},headless:true,
    channel:process.platform==='win32'?'chrome':undefined,
    launchOptions:{args:process.platform==='win32'?[]:['--use-angle=swiftshader','--enable-unsafe-swiftshader']},
    screenshot:'only-on-failure',trace:'retain-on-failure'},
  webServer:[
    {command:'.venv\\Scripts\\python -m uvicorn vivacity.api:app --host 127.0.0.1 --port 8000',cwd:path.resolve('..'),url:'http://127.0.0.1:8000/health',reuseExistingServer:!process.env.CI,timeout:30_000},
    {command:`npx vite preview --host 127.0.0.1 --port ${appPort} --strictPort`,url:`http://127.0.0.1:${appPort}`,reuseExistingServer:!process.env.CI,timeout:30_000}
  ]
});
