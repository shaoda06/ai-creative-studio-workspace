// Complete public workbench on Chloe's real document adapter; all writes are isolated.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {createServer}=await import(require.resolve('vite'));
const react=(await import(require.resolve('@vitejs/plugin-react'))).default;
const frontend=fileURLToPath(new URL('../frontend/',import.meta.url));
const tool=fileURLToPath(new URL('../',import.meta.url));
const version=JSON.parse(await readFile(frontend+'package.json','utf8')).version;
const fixture=JSON.parse(execFileSync(tool+'.venv/bin/python',['-c',`
import json
from tests.test_chloe_production import ChloeProductionTests, browser
x=ChloeProductionTests();x.setUp()
try:
 x.test_shared_request_context_and_native_pack_refer_original()
 x.rounds([x.round(1,[('P001','E001'),('P002','E002')])])
 print(json.dumps({'items':browser.items(x.projects,x.project.name,x.api),'detail':browser.detail(x.projects,x.project.name,x.api,'V001'),'downloads':browser.downloads(x.projects,x.project.name,x.api,'V001')}))
finally:x.doCleanups()
`],{cwd:tool,encoding:'utf8'}));
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 for(const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
  const page=await browser.newPage({viewport:{width,height}});page.setDefaultTimeout(10000);
  const errors=[],unexpected=[],writes=[];let notes={notes:{},rounds:{}};let failList=true;
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   const request=route.request(),url=new URL(request.url()),path=decodeURIComponent(url.pathname);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'chloe',name:'Chloe AI视频带货',view:'chloe-commerce',projects:[]} ]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path.endsWith('/production-videos')){
    if(failList){return route.fulfill({status:409,body:'隔离读取失败'});}
    return route.fulfill({json:fixture.items});
   }
   if(path.endsWith('/production-detail'))return route.fulfill({json:fixture.detail});
   if(path.endsWith('/production-downloads'))return route.fulfill({json:fixture.downloads});
   if(path.endsWith('/production-notes')||path.endsWith('/production-notes/export')){
    if(request.method()==='PUT'){
     writes.push(path);const input=request.postDataJSON();const rows=input.notes||[input];
     for(const note of rows){const key=(note.roundNumber?`round/${note.roundNumber}/`:'')+`${note.segment}/${note.stage}/${note.run}`;notes.notes[key]={...note,updatedAt:'2026-11-07T12:00:00+08:00'};}
     for(const note of input.rounds||[])notes.rounds[note.number]={...note,updatedAt:'2026-11-07T12:00:00+08:00'};
     if(!input.notes)return route.fulfill({json:Object.values(notes.notes).at(-1)});
    }
    return route.fulfill({json:notes});
   }
   if(path.endsWith('/document'))return route.fulfill({json:{title:'隔离脚本原件',html:'<h2>实际分镜</h2><p>SH001 展示商品</p>'}});
   if(path.endsWith('.mp4'))return route.fulfill({contentType:'video/webm',path:frontend+'public/component-samples/video.webm'});
   if(path.endsWith('.png'))return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jLyoAAAAASUVORK5CYII=','base64')});
   unexpected.push(path);return route.fulfill({status:404,body:'unexpected isolated request'});
  });
  await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe?section=production');
  await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  failList=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
  const card=page.locator('[data-episode="V001-隔离演示"]');await card.waitFor();await card.click();
  await page.locator('.episode-detail').waitFor();
  assert.ok(page.url().includes('video='));
  const tabs=page.getByRole('navigation',{name:'作品制作内容'});
  await tabs.waitFor();
  assert.deepEqual(await page.locator('.episode-detail').evaluate(detail => {
   const panel = getComputedStyle(detail.closest('.panel'));
   const tabs = getComputedStyle(detail.querySelector('.scene-workspace-tabs'));
   const content = getComputedStyle(detail.querySelector('.episode-scene-content'));
   const breadcrumb = document.querySelector('.breadcrumbs');
   return [panel.backgroundColor, panel.borderRadius, panel.padding,
    tabs.marginTop, tabs.gap, content.paddingTop,
    Boolean(breadcrumb.closest('.page-heading-stacked')), getComputedStyle(breadcrumb).marginBottom];
  }), ['rgb(255, 255, 255)', '10px', '23px', '20px', '12px 20px', '20px', true, '0px']);

  assert.deepEqual(await tabs.getByRole('button').allTextContents(),['分段制作','分镜脚本','导演分镜表','资源下载']);
  await page.addInitScript(()=>sessionStorage.setItem('nora-auto-refresh-position',JSON.stringify({href:location.href,scrollY:0,values:{'project//api/workspaces/chloe/production/V001-隔离演示/scene-view':'dialogue'}})));
  await page.reload();
  await page.locator('.scene-storyboard').waitFor();
  assert.equal(await page.getByRole('region',{name:'修改场次分镜正文',exact:true}).count(),0);
  await page.getByRole('button',{name:'资源下载',exact:true}).click();
  await page.locator('details[aria-label="一采画布与导演包"] > summary').click();
  await page.getByText('E001 · 导演包',{exact:false}).first().waitFor();
  await page.getByRole('button',{name:'分镜脚本',exact:true}).click();
  const script=page.locator('.scene-storyboard');
  await script.getByRole('heading',{name:/SH001/}).waitFor();
  assert.equal(await script.getByRole('heading',{name:'脚本信息',exact:true}).count(),0);
  assert.equal(await script.getByRole('heading',{name:'内容与声音',exact:true}).count(),0);
  assert.equal(await script.getByRole('heading',{name:'修订记录',exact:true}).count(),0);
  assert.equal(await tabs.getByRole('button',{name:'分镜修改',exact:true}).count(),0);
  await page.getByRole('button',{name:'导演分镜表',exact:true}).click();
  await page.getByRole('button',{name:'分段制作',exact:true}).click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await page.close();
 }
 console.log('Chloe complete workbench adapter, retry, navigation and three desktop widths passed.');
} finally {await browser.close();await server.close();}
