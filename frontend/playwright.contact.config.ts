import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir:'./e2e',testMatch:'contact-lab.spec.ts',workers:1,fullyParallel:false,retries:0,
  timeout:600_000,expect:{timeout:90_000},
  outputDir:'../data/contact-browser-output',
  reporter:[['list'],['json',{outputFile:'../artifacts/physical-truth-runtime/contact-browser-tests.json'}]],
  use:{baseURL:process.env.VIVACITY_CONTACT_UI??'http://127.0.0.1:5186',headless:true,
    viewport:{width:1440,height:1050},screenshot:'only-on-failure',trace:'off'},
  projects:[{name:'chromium',use:{browserName:'chromium'}},
            {name:'firefox',use:{browserName:'firefox',launchOptions:{firefoxUserPrefs:{'webgl.force-enabled':true}}}},
            {name:'webkit',use:{browserName:'webkit'}}],
});
