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
 status_items={}
 path=x.project/'README.md'; original=path.read_text()
 for status in ('制作中','待发布','已发布'):
  path.write_text(original.replace('| 视频状态 | 制作中 |',f'| 视频状态 | {status} |'))
  if status=='已发布':x.published_record()
  status_items[status]=browser.items(x.projects,x.project.name,x.api)
 path.write_text(original)
 print(json.dumps({'items':status_items['制作中'],'statusItems':status_items,'detail':browser.detail(x.projects,x.project.name,x.api,'V001'),'downloads':browser.downloads(x.projects,x.project.name,x.api,'V001')}))
finally:x.doCleanups()
`],{cwd:tool,encoding:'utf8'}));
// A real reference-video entry must retain an outside download when its popup is simplified.
const previewDetail=JSON.parse(JSON.stringify(fixture.detail),(key,value)=>{
 if(value && typeof value==='object' && value.references?.common && value.prompts){
  value.references.common.push({kind:'video',name:'隔离参考视频',label:'Video 1',url:'/component-samples/video.webm'});
 }
 return value;
});
fixture.detail=previewDetail;
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 for(const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
  const page=await browser.newPage({viewport:{width,height}});page.setDefaultTimeout(10000);
  const errors=[],unexpected=[],writes=[];let videoStatus="制作中";let notes={notes:{},rounds:{}};let failList=true;let taskMode=false;let taskFailure=true;let detailRequests=0;let scopedDetail=fixture.detail;
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   const request=route.request(),url=new URL(request.url()),path=decodeURIComponent(url.pathname);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'chloe',name:'Chloe AI视频带货',view:'chloe-commerce',...(taskMode ? {project_layout:'nested',projects:[{id:'甲项目',name:'甲项目'}]} : {projects:[]})} ]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path.endsWith('/后台任务状态.json'))return route.fulfill({json:{id:'isolated-task',status:'cancelled'}});
   if(path==='/api/workspaces/chloe/comfy/tasks/isolated-task/detail'){
    detailRequests++;
    if(taskFailure)return route.fulfill({status:503,json:{detail:'隔离详情读取失败'}});
    return route.fulfill({json:{summary:{id:'isolated-task',project:'甲项目::V001-隔离演示',title:'隔离任务详情',task_type:'video-first',status:'cancelled',collected:0,expected:2},
     events:[],outputs:[],records:[],notification_batches:[],resolution_evidence:[],replacement_tasks:[]}});
   }
   if(path.endsWith('/production-videos')){
    if(failList){return route.fulfill({status:409,body:'隔离读取失败'});}
    return route.fulfill({json:fixture.statusItems[videoStatus]});
   }
   if(path.endsWith('/production-detail'))return route.fulfill({json:{...scopedDetail,statusHtml:fixture.statusItems[videoStatus][0].statusHtml}});
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
  const card=page.locator('[data-episode="V001-隔离演示"]');await card.waitFor();
  assert.equal(await card.locator('strong').innerText(),'V001');
  assert.equal(await card.evaluate(el=>el.getBoundingClientRect().height),48);
  const heading=await page.getByRole('heading',{name:'作品列表',exact:true}).boundingBox();
  const stats=await page.locator('.production-statistics').boundingBox();
  const header=await page.locator('.production-list-heading').boundingBox();
  assert.ok(stats.x>heading.x+heading.width && stats.y<heading.y+heading.height,'statistics sit beside the heading');
  assert.ok(Math.abs(stats.x+stats.width-header.x-header.width)<1,'statistics align to the right edge');
  assert.equal(await page.locator('.production-list-heading').evaluate(el=>getComputedStyle(el).borderBottomWidth),'1px');
  assert.ok((await card.boundingBox()).y>header.y+header.height,'divider separates heading from works');
  for (const [status,color] of [['制作中','blue'],['待发布','orange'],['已发布','green']]) {
   videoStatus=status;await page.reload();await card.waitFor();
   const badge=card.locator('.episode-button-status .status-badge');
   await page.waitForFunction(status=>document.querySelector('.episode-button-status .status-badge')?.textContent===status,status);
   assert.equal(await badge.innerText(),status);
   assert.deepEqual(await page.locator('.production-statistics > span').allTextContents(), ['共 1 部', ...['制作中','待发布','已发布'].map(label=>`${label} ${label===status ? 1 : 0} 部`)]);
   assert.ok((await badge.getAttribute('class')).split(' ').includes('status-'+color));
   await page.waitForFunction(()=>{const el=document.querySelector('.episode-button-duration');return el && !el.textContent.includes('读取中');});
   const duration=await card.locator('.episode-button-duration').boundingBox(), label=await badge.boundingBox(), bounds=await card.boundingBox();
   assert.ok(label.x>=duration.x+duration.width && Math.abs(label.y+label.height/2-duration.y-duration.height/2)<2,'status stays beside duration');
   assert.ok(label.x+label.width<=bounds.x+bounds.width,'status stays within the card');
  }
  await card.click();
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
  assert.equal(await script.locator('.prose h3').nth(1).evaluate(el=>getComputedStyle(el).marginTop),'40px');
  assert.notEqual(await script.locator('.prose h3').first().evaluate(el=>getComputedStyle(el).marginTop),'40px');
  assert.equal(await script.locator('.prose p').first().evaluate(el=>getComputedStyle(el).marginTop),'13px');

  assert.equal(await page.locator('.scene-storyboard .file-action-links').count(),0);
  assert.equal(await page.locator('.scene-storyboard details.chapters').getAttribute('open'),null);
  await page.locator('.scene-storyboard details.chapters > summary').click();
  await page.locator('.scene-storyboard nav[aria-label="章节导航"] button.chapter-link').first().click();
  assert.equal(await page.locator('.scene-storyboard .prose :focus').count(),1);

  assert.equal(await script.getByRole('heading',{name:'脚本信息',exact:true}).count(),0);
  assert.equal(await script.getByRole('heading',{name:'内容与声音',exact:true}).count(),0);
  assert.equal(await script.getByRole('heading',{name:'修订记录',exact:true}).count(),0);
  assert.equal(await tabs.getByRole('button',{name:'分镜修改',exact:true}).count(),0);
  await page.getByRole('button',{name:'导演分镜表',exact:true}).click();
  await page.getByText('脚本 v01 暂无对应导演分镜表。',{exact:true}).waitFor();
  assert.equal(await page.getByText('分镜 v01 暂无对应导演分镜表。',{exact:true}).count(),0);
  await page.getByRole('button',{name:'分段制作',exact:true}).click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  const reference=page.locator('.segment-reference-images figure').filter({has:page.getByRole('button',{name:'查看 Video 1 隔离参考视频',exact:true})});
  assert.equal(await reference.getByRole('link',{name:'下载',exact:true}).count(),1);
  await reference.getByRole('button').click();
  assert.equal(await page.getByRole('dialog').locator('.file-action-links').count(),0);
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'轮次记录',exact:true}).click();
  const rounds=page.getByRole('dialog');
  assert.ok(await rounds.getByRole('link',{name:'下载',exact:true}).count()>0);
  await page.keyboard.press('Escape');
  // The shared task ledger belongs to the workspace, not its nested content context.
  taskMode=true;
  scopedDetail=JSON.parse(JSON.stringify(fixture.detail),(key,value)=>{
   if(value && typeof value==='object' && 'taskStateUrl' in value){
    value.url='';value.taskStatus='cancelled';
    value.taskStateUrl='/api/workspaces/chloe/contexts/甲项目/projects/V001-隔离演示/files/执行记录/E001/后台任务状态.json';
   }
   return value;
  });
  await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe/contexts/'+encodeURIComponent('甲项目')+'?section=production&video='+encodeURIComponent('V001-隔离演示'));
  await page.getByRole('button',{name:'查看任务详情',exact:true}).click();
  const dialog=page.getByRole('dialog');
  await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  assert.ok((await page.locator('body').innerText()).includes('隔离详情读取失败'));
  taskFailure=false;
  await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await dialog.getByText('隔离任务详情',{exact:true}).waitFor();
  assert.ok(detailRequests>=2);
  assert.ok(await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1}));
  await page.keyboard.press('Escape');
  assert.equal(await page.getByRole('dialog').count(),0);
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await page.close();
 }
 console.log('Chloe complete workbench adapter, retry, navigation and three desktop widths passed.');
} finally {await browser.close();await server.close();}
