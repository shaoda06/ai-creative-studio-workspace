// Real common production components; isolated inputs, media and in-memory review writes.
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
const out=await mkdtemp('/private/tmp/W464-production-');
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();const browser=await chromium.launch({channel:'chrome',headless:true});
let activePage;
try{
 for(const width of [1280,1366,1920]){
  const page=await browser.newPage({viewport:{width,height:width===1280?640:width===1366?768:1080}}),errors=[],unexpected=[],writes=[];
  const saved={notes:{},rounds:{}};let failSave=true;
  activePage=page;page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   const req=route.request(),u=new URL(req.url()),path=decodeURIComponent(u.pathname);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'commercial',name:'Iris',view:'files',projects:[{id:'隔离样片',name:'隔离样片'}]}]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   const historical=path.startsWith('/api/workspaces/commercial/projects/历史样片');
   const base='/api/workspaces/commercial/projects/'+(historical?'历史样片':'隔离样片');
   if(path===base)return route.fulfill({json:{name:'隔离样片',productionSection:'06-视频生产',files:[{kind:'group',name:'06-视频生产',key:'06-视频生产',children:[]}]}});
   if(path===base+'/production'){
    const segments=['P001','P002'].map((id,i)=>({id,duration:3,scriptHtml:'',videos:['一采','二采','后处理'].flatMap((stage,j)=>[1,2].map(n=>({key:`${id}/${stage}/R00${n}.webm`,url:base+`/files/${id}-${j}-${n}.webm`,run:`R00${n}`,stage,approved:false,adoptionKnown:false,candidateNumber:n,fileRevision:`fixture-${i}-${j}-${n}`,deliveryStatus:'已取回',taskStatus:'completed',taskStateUrl:'',checkedAt:'',context:{scriptHtml:`<h4>${id}-SH001</h4><p>${id}实际镜头</p>`,shots:[{id:`${id}-SH001`,duration:3,html:`<h4>${id}-SH001</h4><p>${id}实际镜头</p>`}],prompts:{english:`summary:\n${id} actual R00${n}`,chinese:`${id}同版中文R00${n}`},references:{common:[],segment:[{kind:'image',name:'fixture.png',label:'Picture 1',url:base+'/files/fixture.png'}]},issues:[]}})))}));
    if(historical){for(const item of segments){item.label=item.id;item.id='EP001-C001-'+item.id;for(const video of item.videos){delete video.context;video.contextUrl=base+'/production-context?source=history&identity='+item.id}}}
    return route.fulfill({json:{segments,batches:[{id:'R001',name:'R001-隔离一采',readOnly:historical,segments:segments.map(s=>({id:s.id,stage:'一采',key:s.videos[0].key}))},{id:'R002',name:'R002-隔离后处理',readOnly:historical,segments:segments.map(s=>({id:s.id,stage:'后处理',key:s.videos.at(-1).key}))}],issues:[]}});
   }
   if(path===base+'/production-context')return route.fulfill({json:{scriptHtml:'<p>历史分镜快照</p>',shots:[],prompts:{english:'historical prompt',chinese:''},references:{common:[],segment:[]},issues:[]}});
   if(historical&&path.includes('production-notes')){unexpected.push(path);return route.abort()}
   if(path===base+'/production-notes' || path===base+'/production-notes/export'){
    if(req.method()==='GET')return route.fulfill({json:saved});
    writes.push(path);const value=req.postDataJSON();
    if(failSave){failSave=false;return route.fulfill({status:503,json:{detail:'隔离保存失败，请重试'}})}
    const changes=path.endsWith('/export')?value.notes:[value];
    for(const note of changes){const key=`${note.segment}/${note.stage}/${note.run}`;saved.notes[key]={...note,updatedAt:'2026-11-03T00:00:00+08:00'};delete saved.notes[key].expectedText}
    return route.fulfill({json:path.endsWith('/export')?saved:saved.notes[`${value.segment}/${value.stage}/${value.run}`]});
   }
   if(path.endsWith('.webm'))return route.fulfill({contentType:'video/webm',path:frontend+'public/component-samples/video.webm'});
   if(path.endsWith('fixture.png'))return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jLyoAAAAASUVORK5CYII=','base64')});
   unexpected.push(req.method()+' '+path);return route.abort();
  });
  const origin=`http://127.0.0.1:${server.httpServer.address().port}`;
  await page.goto(origin+'/#/spaces/commercial/projects/隔离样片');
  await page.getByRole('navigation',{name:'项目栏目',exact:true}).getByRole('button',{name:'视频制作',exact:true}).click();
  await page.getByRole('combobox',{name:'生产批次',exact:true}).waitFor();
  await page.locator('.segment-video video').waitFor();
  await page.waitForFunction(()=>document.querySelector('.segment-video video')?.readyState>=2);
  await page.getByRole('button',{name:'提示词',exact:true}).click();
  await page.locator('pre.segment-prompt-text').filter({hasText:'P001同版中文R002'}).waitFor();
  await page.getByRole('combobox',{name:'画质选择',exact:true}).click();await page.getByRole('option',{name:'一采',exact:true}).click();
  await page.getByRole('combobox',{name:'版本切换',exact:true}).click();await page.getByRole('option',{name:'候选一',exact:true}).click();
  await page.locator('pre.segment-prompt-text').filter({hasText:'P001同版中文R001'}).waitFor();
  await page.getByRole('button',{name:'查看 Picture 1 fixture.png',exact:true}).click();await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  const editor=page.getByRole('textbox',{name:'修改意见',exact:true});await editor.fill('隔离P001一采意见');await editor.blur();
  await page.getByRole('button',{name:'重试保存',exact:true}).waitFor();assert.equal(await editor.inputValue(),'隔离P001一采意见');
  await page.getByRole('button',{name:'重试保存',exact:true}).click();await page.getByText('已保存',{exact:true}).waitFor();
  await page.getByRole('button',{name:/^分段 P002，计划时长/}).click();assert.equal(await editor.inputValue(),'');
  await page.getByRole('button',{name:/^分段 P001，计划时长/}).click();assert.equal(await editor.inputValue(),'隔离P001一采意见');
  await page.screenshot({path:`${out}/${width}-normal.png`});
  await page.getByRole('button',{name:'宽屏显示',exact:true}).click();
  await page.locator('.segment-workspace.is-wide').waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`${out}/${width}-wide.png`});
  await page.reload();await page.getByRole('navigation',{name:'项目栏目',exact:true}).getByRole('button',{name:'视频制作',exact:true}).click();
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  await page.getByRole('combobox',{name:'画质选择',exact:true}).click();await page.getByRole('option',{name:'一采',exact:true}).click();
  await page.getByRole('combobox',{name:'版本切换',exact:true}).click();await page.getByRole('option',{name:'候选一',exact:true}).click();
  assert.equal(await page.getByRole('textbox',{name:'修改意见',exact:true}).inputValue(),'隔离P001一采意见');
  await page.getByRole('combobox',{name:'生产批次',exact:true}).click();await page.getByRole('option',{name:'R001-隔离一采',exact:true}).click();
  await page.getByRole('button',{name:'导出修改意见',exact:true}).click();
  await page.getByRole('dialog').getByText('隔离P001一采意见',{exact:false}).first().waitFor();await page.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).click();
  await page.goto(origin+'/#/spaces/commercial/projects/历史样片');
  await page.getByRole('navigation',{name:'项目栏目',exact:true}).getByRole('button',{name:'视频制作',exact:true}).click();
  await page.locator('.segment-script-content').getByText('历史分镜快照',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'修改意见',exact:true}).count(),0);
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);assert.ok(writes.every(path=>path.endsWith('/production-notes')));
  console.log(JSON.stringify({width,passed:true,reviewWrites:writes.length}));await page.close();
 }
 console.log('Screenshots: '+out);
}catch(error){await activePage.screenshot({path:out+'/failure.png'});console.log('Failed body: '+await activePage.locator('body').innerText());console.log('Screenshots: '+out);throw error}finally{await browser.close();await server.close()}
