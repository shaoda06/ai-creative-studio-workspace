// Browser plugin is unavailable; use the installed Playwright with isolated API fixtures.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {mkdtemp,readFile} from 'node:fs/promises';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {createServer}=await import(require.resolve('vite'));
const react=(await import(require.resolve('@vitejs/plugin-react'))).default;
const frontend=fileURLToPath(new URL('../frontend/',import.meta.url));
const version=JSON.parse(await readFile(frontend+'package.json','utf8')).version;
const out=await mkdtemp('/private/tmp/W472-resources-');
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen(); const browser=await chromium.launch({channel:'chrome',headless:true});
let activePage;
try {
 for(const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
  const page=activePage=await browser.newPage({viewport:{width,height}}),errors=[],unexpected=[];
  page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(String(error)));
  const base='/api/workspaces/commercial/projects/资源隔离测试';
  let failUpload=true,posts=0;
  const families=[['IMG-fixture','图片','人物参考图'],['VID-fixture','视频','表演参考视频'],['AUD-fixture','音频','用户参考声音']].map(([resource_id,kind,name])=>({resource_id,kind,name,version_count:2}));
  await page.route('**/api/**',route=>{
   const req=route.request(),url=new URL(req.url()),path=decodeURIComponent(url.pathname);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'commercial',name:'Iris',view:'files',projects:[{id:'资源隔离测试',name:'资源隔离测试'}]}]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path===base)return route.fulfill({json:{name:'资源隔离测试',files:[]}});
   if(path===base+'/resources') {
    if(req.method()==='POST') {
     posts++;assert.ok(req.headers()['content-type'].startsWith('multipart/form-data'));
     if(failUpload){failUpload=false;return route.fulfill({status:503,json:{detail:'隔离导入失败'}})}
     return route.fulfill({json:{resource_id:'IMG-fixture',version:'V003',file:'资源/图片/IMG-fixture/V003/修图.png'}});
    }
    const q=url.searchParams.get('q'),kind=url.searchParams.get('kind');
    const items=families.filter(item=>(!q||item.name.includes(q))&&(!kind||item.kind===kind));
    return route.fulfill({json:{items,total:items.length,page_size:12}});
   }
   if(path.startsWith(base+'/resources/')) {
    const family=families.find(item=>path.endsWith(item.resource_id));assert.ok(family);
    const kind=({图片:'image',视频:'video',音频:'audio'})[family.kind];
    return route.fulfill({json:{...family,versions:['V001','V002'].map((v,i)=>({resource_id:family.resource_id,version:v,file:`资源/${family.kind}/${family.resource_id}/${v}/fixture`,kind:family.kind,
     origin:i?'process':'user_upload',producer:null,registered_at:'2026-11-03T10:00:00+08:00',parent:i?{resource_id:family.resource_id,version:'V001',kind:family.kind,file:`资源/${family.kind}/${family.resource_id}/V001/fixture`}:null,
     facts:{bytes:1000,duration_seconds:kind==='image'?undefined:65},media:{kind,name:family.name,key:v,url:base+'/files/'+(kind==='image'?'fixture.png':kind==='video'?'fixture.webm':'fixture.wav')},
     uses:i?[{heading:'原审核记录',excerpt:'本次未通过，保持V001采用。',document:{kind:'markdown',name:'原审核记录',key:'审核.md',url:base+'/files/审核.md'}}]:[]}))}});
   }
   if(path.endsWith('fixture.png'))return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jLyoAAAAASUVORK5CYII=','base64')});
   if(path.endsWith('fixture.webm'))return route.fulfill({contentType:'video/webm',path:frontend+'public/component-samples/video.webm'});
   if(path.endsWith('fixture.wav'))return route.fulfill({contentType:'audio/wav',path:frontend+'public/component-samples/tone.wav'});
   if(path.endsWith('审核.md'))return route.fulfill({contentType:'text/plain',body:'# 原审核记录\n本次未通过，保持V001采用。'});
   unexpected.push(req.method()+' '+path);return route.abort();
  });
  const origin=`http://127.0.0.1:${server.httpServer.address().port}`;
  await page.goto(origin+'/#/spaces/commercial/projects/资源隔离测试');
  await page.getByRole('navigation',{name:'项目栏目',exact:true}).getByRole('button',{name:'项目资源',exact:true}).click();
  await page.getByRole('button',{name:/人物参考图.*2个版本/}).click();
  await page.getByText('IMG-fixture · 图片 · 共2个版本',{exact:true}).waitFor();
  await page.locator('summary').filter({hasText:'引用记录（1）'}).click();
  await page.getByText('本次未通过，保持V001采用。',{exact:true}).waitFor();
  await page.getByRole('button',{name:'导入新版本',exact:true}).click();
  const dialog=page.getByRole('dialog');await dialog.waitFor();
  await dialog.locator('input[type=file]').setInputFiles({name:'修改图.png',mimeType:'image/png',buffer:Buffer.from('fixture')});
  await dialog.getByRole('button',{name:'导入',exact:true}).click();
  await page.getByText('隔离导入失败',{exact:true}).waitFor();
  assert.equal(await dialog.count(),1);await dialog.getByRole('button',{name:'导入',exact:true}).click();
  await dialog.waitFor({state:'hidden'});assert.equal(posts,2);
  await page.getByRole('button',{name:'返回资源列表',exact:true}).click();
  const search=page.getByRole('searchbox',{name:'搜索项目资源',exact:true});await search.fill('没有该资源');
  await page.getByText('暂无符合条件的资源。',{exact:true}).waitFor();await search.fill('');
  await page.getByRole('button',{name:/表演参考视频.*2个版本/}).click();
  await page.getByText(/65.00秒（1分5.00秒）/).first().waitFor();
  await page.screenshot({path:`${out}/${width}-video.png`});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.getByRole('button',{name:'返回资源列表',exact:true}).click();
  await page.getByRole('button',{name:/用户参考声音.*2个版本/}).click();
  await page.getByRole('button',{name:'导入新版本',exact:true}).click();
  await page.getByRole('dialog').waitFor();
  assert.ok(await page.getByRole('dialog').evaluate(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight}));
  await page.screenshot({path:`${out}/${width}-upload.png`});
  await page.keyboard.press('Escape');
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);await page.close();
 }
 console.log(JSON.stringify({passed:true,screenshots:out,viewports:[1280,1366,1920]}));
}catch(error){if(activePage)await activePage.screenshot({path:out+'/failure.png'});throw error}
finally{await browser.close();await server.close()}
