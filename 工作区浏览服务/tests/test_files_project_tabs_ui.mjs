// Real registered-project page, synthetic documents; no production reads or writes.
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
const out=await mkdtemp('/private/tmp/W462-project-tabs-');
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();const browser=await chromium.launch({channel:'chrome',headless:true});
const fixtures={
 'C001-fixture':['06-视频制作','07-审阅','历史制作资料'],
 'C002-fixture':['01-客户资料','03-创意脚本','04-分镜声音','05-资产','06-视频生产','归档'],
 'C003-fixture':['01-客户资料','02-参考分析','04-分镜声音','05-资产','06-视频生产','归档'],
};
try{
 for(const width of [1280,1366,1920]){
  const page=await browser.newPage({viewport:{width,height:width===1280?640:width===1366?768:1080}}),errors=[],writes=[];
  page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.route('**/api/**',route=>{
   const req=route.request(),u=new URL(req.url()),path=decodeURIComponent(u.pathname);
   assert.equal(req.method(),'GET');
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'nora',name:'Nora',view:'serial-drama',projects:[]},{id:'commercial',name:'Iris',view:'files',projects:Object.keys(fixtures).map(id=>({id,name:id}))}]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   const m=/^\/api\/workspaces\/commercial\/projects\/([^/]+)(\/document)?$/.exec(path);
   if(m){
    const name=m[1],base='/api/workspaces/commercial/projects/'+name;
    if(m[2])return route.fulfill({json:{title:'栏目资料',html:'<h1>隔离正文 '+u.searchParams.get('path')+'</h1>'}});
    const files=['README.md','项目状态.md'].map(name=>({kind:'file',name,key:name,url:base+'/files/'+name}));
    files.push(...fixtures[name].map(folder=>({kind:'group',name:folder,key:folder,children:[{kind:'file',name:folder+'资料.md',key:folder+'/资料.md',url:base+'/files/'+encodeURIComponent(folder)+'/资料.md'}]})));
    return route.fulfill({json:{name,files}});
   }
   throw new Error('Unexpected request '+req.url());
  });
  page.on('request',r=>{if(r.method()!=='GET')writes.push(r.url())});
  for(const [name,folders] of Object.entries(fixtures)){
   await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/#/spaces/commercial/projects/${name}`);
   await page.getByRole('heading',{name,exact:true}).waitFor();
   const tabs=page.getByRole('navigation',{name:'项目栏目',exact:true}),panel=page.getByRole('region',{name:'项目资料',exact:true});
   await tabs.getByRole('button',{name:'项目概况',exact:true}).waitFor();
   assert.equal(await tabs.getByRole('button',{name:'项目概况',exact:true}).getAttribute('aria-current'),'page');
   await panel.getByRole('button',{name:'README.md',exact:true}).waitFor();
   for(const folder of folders){
    await tabs.getByRole('button',{name:folder.replace(/^\d+[-_、.\s]+/,''),exact:true}).click();
    await panel.getByRole('button',{name:folder+'资料.md',exact:true}).waitFor();
    assert.equal(await panel.getByRole('button',{name:'README.md',exact:true}).count(),0);
   }
   await panel.getByRole('button',{name:folders.at(-1)+'资料.md',exact:true}).click();
   await page.getByRole('dialog').getByRole('heading',{name:'隔离正文 '+folders.at(-1)+'/资料.md',exact:true}).waitFor();
   await page.keyboard.press('Escape');
   await tabs.getByRole('button',{name:'全部资料',exact:true}).click();
   assert.ok((await panel.innerText()).includes(folders[0]));
   assert.equal(await page.locator('vite-error-overlay').count(),0);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:`${out}/${width}-${name}.png`});
  }
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  console.log(JSON.stringify({width,projects:3,passed:true}));await page.close();
 }
 console.log('Screenshots: '+out);
}finally{await browser.close();await server.close()}
