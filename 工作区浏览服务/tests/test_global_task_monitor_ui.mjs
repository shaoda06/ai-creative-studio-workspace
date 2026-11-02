// Real sidebar, two synthetic spaces and in-memory actions; never reads real tasks.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {mkdtemp} from 'node:fs/promises';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {createServer}=await import(require.resolve('vite'));
const react=(await import(require.resolve('@vitejs/plugin-react'))).default;
const out=await mkdtemp('/private/tmp/W461-global-tasks-');
const server=await createServer({configFile:false,root:fileURLToPath(new URL('../frontend',import.meta.url)),plugins:[react()],server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 for(const width of [1280,1366,1920]) for(const selected of ['commercial','nora']) {
  const page=await browser.newPage({viewport:{width,height:width===1280?640:width===1366?768:1080}}),errors=[],writes=[],details=[];
  page.setDefaultTimeout(8000);
  const spaces=[{id:'nora',name:'Nora',view:'serial-drama',projects:[]},{id:'commercial',name:'Iris',view:'files',projects:[]}];
  const rows=spaces.map(s=>({id:s.id+'-queued',queue:'local',category:'queued',status:'local_queued',title:s.name+'排队任务',project:'隔离项目',task_type:'image',remote_url:'http://fixture-node',created_at:'2026-11-02T00:00:00Z',api_prefix:'/api/workspaces/'+s.id,workspace_name:s.name}));
  const active=spaces.map(s=>({...rows.find(t=>t.workspace_name===s.name),source:'local',queue:undefined,category:undefined,id:s.id+'-running',prompt_id:'remote-'+s.id,status:'running',title:s.name+'进行中任务',collected:0,expected:1,progress:null,connection:'connected'}));
  const history=spaces.map(s=>({...rows.find(t=>t.workspace_name===s.name),id:'same-history-id',category:'history',status:'completed',title:s.name+'历史任务',collected:1,expected:1}));
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.route('**/api/**',route=>{
   const req=route.request(),u=new URL(req.url()),path=u.pathname;
   if(path==='/api/workspaces')return route.fulfill({json:spaces});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:active,local_tasks:rows,remote_nodes:[{url:'http://fixture-node',name:'共用节点',connection:'connected',queue:[...active.map(t=>({prompt_id:t.prompt_id,status:'running',queue_position:null})),{prompt_id:'unknown',status:'queued',queue_position:1}],running_count:2,queued_count:1,updated_at:'2026-11-02T00:00:00Z'}],local_counts:{'http://fixture-node':{queued:rows.filter(t=>t.category==='queued').length,paused:rows.filter(t=>t.category==='paused').length,history:2}},history_updated_at:{}}});
   if(path==='/api/task-monitor/history')return route.fulfill({json:{items:history.filter(t=>t.title.includes(u.searchParams.get('q')||'')),total:history.length,next_offset:null}});
   const detail=/^\/api\/workspaces\/(nora|commercial)\/comfy\/tasks\/([^/]+)\/detail$/.exec(path);
   if(detail){details.push(path);const owner=spaces.find(s=>s.id===detail[1]);return route.fulfill({json:{summary:{...history.find(t=>t.workspace_name===owner.name),title:owner.name+'完整详情',source_session_name:'隔离会话',notification:'not_required',remote_url:'http://fixture-node'},group:null,events:[],outputs:[],records:[],notification_batches:[],resolution_evidence:[],replacement_tasks:[]}})}
   if(req.method()==='POST'&&path==='/api/workspaces/nora/comfy/tasks/nora-queued/action'){
    writes.push(path);const task=rows.find(t=>t.id==='nora-queued');task.status='paused';task.category='paused';return route.fulfill({json:{status:'paused'}});
   }
   throw new Error('Unexpected isolated request '+req.method()+' '+path);
  });
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/tests/task-sidebar.html?space=${selected}`);
  assert.equal(await page.title(),'任务侧栏隔离回归');
  await page.getByRole('button',{name:'展开任务进度',exact:true}).click();
  const side=page.getByRole('complementary',{name:'生成任务进度'}),remote=side.getByRole('region',{name:'远端队列'}),local=side.getByRole('region',{name:'本地队列'});
  await remote.getByText('Nora进行中任务',{exact:true}).waitFor();
  await remote.getByText('Iris进行中任务',{exact:true}).waitFor();
  assert.equal(await remote.getByText('其他来源提交',{exact:true}).count(),1,'only the genuinely unregistered remote task stays external');
  await remote.getByRole('button',{name:'查看Nora进行中任务详情',exact:true}).click();
  const dialog=page.getByRole('dialog');await dialog.getByText('Nora完整详情',{exact:true}).waitFor();
  await page.screenshot({path:`${out}/${width}-${selected}-detail.png`});
  await page.keyboard.press('Escape');
  await local.locator('.local-queue-card').filter({hasText:'Nora排队任务'}).getByRole('button',{name:'暂停',exact:true}).click();
  await local.getByRole('button',{name:'暂停中（1）',exact:true}).waitFor();
  assert.deepEqual(writes,['/api/workspaces/nora/comfy/tasks/nora-queued/action']);
  await local.getByRole('button',{name:'历史（2）',exact:true}).click();
  await local.getByText('Nora历史任务',{exact:true}).waitFor();await local.getByText('Iris历史任务',{exact:true}).waitFor();
  for(const name of ['Nora','Iris']){await local.getByRole('button',{name:`查看${name}历史任务详情`,exact:true}).click();await dialog.getByText(name+'完整详情',{exact:true}).waitFor();await page.keyboard.press('Escape')}
  assert.ok(details.includes('/api/workspaces/nora/comfy/tasks/same-history-id/detail'));
  assert.ok(details.includes('/api/workspaces/commercial/comfy/tasks/same-history-id/detail'));
  assert.equal(await page.locator('vite-error-overlay').count(),0);assert.deepEqual(errors,[]);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  console.log(JSON.stringify({width,selected,passed:true}));await page.close();
 }
 console.log('Screenshots: '+out);
}finally{await browser.close();await server.close()}
