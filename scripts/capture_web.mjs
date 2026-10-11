#!/usr/bin/env node
import {chromium} from '../web/node_modules/playwright-core/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const args=Object.fromEntries(process.argv.slice(2).map(x=>{const [k,...v]=x.replace(/^--/,'').split('=');return[k,v.join('=')||true];}));
const out=path.resolve(root,args.out||'web/results');await fs.mkdir(out,{recursive:true});
const mime={'.js':'text/javascript','.mjs':'text/javascript','.html':'text/html','.json':'application/json','.glb':'model/gltf-binary','.png':'image/png'};
const server=http.createServer(async(req,res)=>{try{const url=new URL(req.url,'http://localhost');const p=path.resolve(root,'.'+decodeURIComponent(url.pathname));if(!p.startsWith(root+path.sep))throw Error('bad path');const body=await fs.readFile(p);res.writeHead(200,{'Content-Type':mime[path.extname(p)]||'application/octet-stream'});res.end(body);}catch{res.writeHead(404);res.end('Not found');}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}/web/index.html`;
const metadata={startedAt:new Date().toISOString(),host:{platform:process.platform,arch:process.arch,node:process.version},browserExecutable:args.chromium||'/usr/bin/chromium',runs:[],status:'running',note:'Actual cloud Chromium WebGL run; check each renderer provenance. Not a desktop or target-device performance claim.'};
let browser;
try{
const launchArgs=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'];
metadata.launchArgs=launchArgs;
const browserHome=path.join(out,'.browser-home');await fs.mkdir(browserHome,{recursive:true});
browser=await chromium.launch({executablePath:metadata.browserExecutable,headless:true,args:launchArgs,env:{...process.env,HOME:browserHome}});metadata.browserVersion=browser.version();
const modes=String(args.modes||'A,C').split(','),cameras=String(args.cameras||'hero,side,top').split(',');
for(const mode of modes)for(const camera of cameras){
const record={mode,camera,status:'not_run',console:[],startedAt:new Date().toISOString()};metadata.runs.push(record);
const page=await browser.newPage({viewport:{width:Number(args.width)||640,height:Number(args.height)||640},deviceScaleFactor:1});
page.on('console',m=>{if(['warning','error'].includes(m.type()))record.console.push({type:m.type(),text:m.text()});});page.on('pageerror',e=>record.console.push({type:'pageerror',text:String(e)}));
try{
const params=new URLSearchParams({mode,camera,capture:'1',width:String(args.width||640),height:String(args.height||640)});if(args.glb)params.set('glb',String(args.glb));if(args.spec)params.set('spec',String(args.spec));
await page.goto(base+'?'+params,{waitUntil:'load',timeout:45000});await page.waitForFunction(()=>['ready','failed'].includes(window.__BENCHMARK__?.status),{timeout:60000});
const state=await page.evaluate(()=>window.__BENCHMARK__);if(state.status!=='ready')throw new Error(state.errors?.join('\n')||'Viewer failed');
record.result=await page.evaluate(frames=>window.__renderBenchmark(frames),Number(args.frames)||8);record.status='passed';record.screenshot=`${mode}_${camera}.png`;await page.locator('canvas').screenshot({path:path.join(out,record.screenshot)});
}catch(e){record.status='failed';record.error=String(e);record.result=await page.evaluate(()=>window.__BENCHMARK__).catch(()=>null);}finally{await page.close();record.finishedAt=new Date().toISOString();await fs.writeFile(path.join(out,'benchmark.json'),JSON.stringify(metadata,null,2));}
console.log(`${mode}/${camera}: ${record.status}${record.result?.timing?` ${record.result.timing.medianMs.toFixed(2)}ms median · ${record.result.webgl.renderer}`:` ${record.error||''}`}`);
}
metadata.status=metadata.runs.every(x=>x.status==='passed')?'passed':metadata.runs.some(x=>x.status==='passed')?'partial':'failed';
}catch(e){metadata.status='not_run';metadata.error=String(e);if(!metadata.runs.length)for(const mode of String(args.modes||'A,C').split(','))for(const camera of String(args.cameras||'hero,side,top').split(','))metadata.runs.push({mode,camera,status:'not_run',reason:'Browser process failed before page load; no rendered evidence or timing measurements.'});console.error(e);}finally{metadata.finishedAt=new Date().toISOString();await fs.writeFile(path.join(out,'benchmark.json'),JSON.stringify(metadata,null,2));if(browser)await browser.close();await new Promise(r=>server.close(r));}
console.log(`Evidence: ${out}/benchmark.json`);if(metadata.status==='failed'||metadata.status==='not_run')process.exitCode=1;
