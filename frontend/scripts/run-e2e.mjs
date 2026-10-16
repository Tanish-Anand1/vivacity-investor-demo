import { mkdirSync } from 'node:fs';
import { spawn } from 'node:child_process';
import path from 'node:path';
const temp=path.resolve('../data/browser-temp'); mkdirSync(temp,{recursive:true});
const env={...process.env,PLAYWRIGHT_BROWSERS_PATH:process.env.PLAYWRIGHT_BROWSERS_PATH??path.resolve('../data/playwright')};
if(process.platform==='win32'){env.TEMP=temp;env.TMP=temp;}
const child=spawn(process.execPath,['node_modules/@playwright/test/cli.js','test',...process.argv.slice(2)],{stdio:'inherit',env});
child.on('exit',code=>process.exit(code??1));
child.on('error',err=>{console.error(err);process.exit(1);});
