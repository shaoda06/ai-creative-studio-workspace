// Two works share P001/R001; all writes and downloads stay in isolated fixtures.
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
const out=await mkdtemp('/private/tmp/W488-works-');
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true});
let activePage;
try {
 for (const width of [1280,1366,1920]) {
  const page=await browser.newPage({viewport:{width,height:width===1280?640:width===1366?768:1080}});
  activePage=page;page.setDefaultTimeout(10000);
  const errors=[],unexpected=[],downloads=[],writes=[];
  page.on('pageerror',error=>errors.push(String(error)));
  const base='/api/workspaces/commercial/projects/隔离多作品';
  const works=[{id:'F001',name:'产品片',key:'作品/F001-产品片'},{id:'F002',name:'品牌片',key:'作品/F002-品牌片'}];
  const saved={F001:{notes:{'P001/一采/R001':{segment:'P001',stage:'一采',run:'R001',text:'产品片原意见',fileRevision:'F001',updatedAt:'2026-11-06'}},rounds:{}},F002:{notes:{},rounds:{}}};
  let failWork=true,failSave=true;
  const file=key=>({kind:'file',key,name:key.split('/').at(-1),url:base+'/files/'+key});
  await page.route('**/api/**',route=>{
   const request=route.request(),url=new URL(request.url()),path=decodeURIComponent(url.pathname);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'commercial',name:'Iris',view:'iris-commercial',projects:[{id:'隔离多作品',name:'隔离多作品'}]}]});
   if(path===base)return route.fulfill({json:{name:'隔离多作品',works,files:[file('README.md'),file('项目状态.md'),{kind:'group',key:'作品',name:'作品',children:[]}]}});
   if(path===base+'/document') {
    const key=url.searchParams.get('path');
    return route.fulfill({json:{html:key==='README.md'?'<h1>项目</h1><h2>项目说明</h2><p>项目共用说明</p>':`<h1>正文</h1><h2>作品正文</h2><p>${key.includes('F002')?'品牌片专属正文':'产品片专属正文'}</p>`,url:base+'/files/'+key}});
   }
   const match=path.match(/\/works\/(F\d{3})(.*)$/);
   if(match) {
    const identity=match[1],suffix=match[2],work=works.find(item=>item.id===identity),key=work.key;
    const script=key+'/03-创意脚本/制作脚本-v01.md',packageKey=key+'/07-返修交接/草稿.jianying.json';
    if(suffix==='') {
     if(identity==='F002'&&failWork){failWork=false;return route.fulfill({status:503,json:{detail:'隔离作品读取失败'}})}
     return route.fulfill({json:{productionSection:key+'/06-视频生产',files:[{kind:'group',name:'03-创意脚本',key:key+'/03-创意脚本',children:[file(script)]},{kind:'group',name:'06-视频生产',key:key+'/06-视频生产',children:[]}],irisPresentation:{primary:{'03-创意脚本':[script]},adopted:[],delivery:{status:'草稿可交接',summary:work.name+'交付版本',archivedHandoff:null,items:[{title:work.name+'横版',type:'剪映草稿',version:'v01',purpose:'本片版本',file:{...file(packageKey),jianying:{jypack:base+'/jianying-download?path='+encodeURIComponent(packageKey)}}}]}}}});
    }
    if(suffix==='/production')return route.fulfill({json:{issues:[],segments:[{id:'P001',duration:3,scriptHtml:'',videos:[{key:identity+'/P001.mp4',url:base+'/files/'+identity+'.webm',run:'R001',stage:'一采',approved:false,adoptionKnown:false,candidateNumber:1,fileRevision:identity,deliveryStatus:'已取回',context:{scriptHtml:'<p>'+identity+'实际镜头</p>',shots:[],prompts:{english:identity+' actual prompt',chinese:identity+'中文'},references:{common:[],segment:[]},issues:[]}}]}],batches:[{id:'R001',name:'R001-'+work.name,segments:[{id:'P001',stage:'一采',key:identity+'/P001.mp4'}]}]}});
    if(suffix==='/production-notes') {
     if(request.method()==='GET')return route.fulfill({json:saved[identity]});
     writes.push(identity);
     if(failSave){failSave=false;return route.fulfill({status:503,json:{detail:'隔离保存失败'}})}
     const note=request.postDataJSON();saved[identity].notes['P001/一采/R001']={...note,updatedAt:'2026-11-06'};
     return route.fulfill({json:saved[identity].notes['P001/一采/R001']});
    }
   }
   if(path===base+'/jianying-download'){const key=url.searchParams.get('path');downloads.push(key);return route.fulfill({body:'isolated package',headers:{'Content-Disposition':'attachment; filename="F002.jypack"'}})}
   if(path===base+'/resources')return route.fulfill({json:{items:[],total:0,page_size:20}});
   if(path.endsWith('.webm'))return route.fulfill({contentType:'video/webm',path:frontend+'public/component-samples/video.webm'});
   unexpected.push(request.method()+' '+path);return route.abort();
  });
  const origin=`http://127.0.0.1:${server.httpServer.address().port}`;
  await page.goto(origin+'/#/spaces/commercial/projects/隔离多作品');
  const tabs=page.getByRole('navigation',{name:'项目栏目',exact:true});
  await page.getByText('项目共用说明',{exact:true}).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'切换作品',exact:true}).count(),0);
  await tabs.getByRole('button',{name:'创意与音画',exact:true}).click();
  await page.getByText('产品片专属正文',{exact:true}).waitFor();
  const choose=async id=>{await page.getByRole('combobox',{name:'切换作品',exact:true}).click();await page.getByRole('option',{name:new RegExp('^'+id)}).click()};
  await choose('F002');
  await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.getByText('品牌片专属正文',{exact:true}).waitFor();
  assert.equal(await page.getByText('产品片专属正文',{exact:true}).count(),0);
  await tabs.getByRole('button',{name:'交付与复盘',exact:true}).click();
  await page.getByRole('heading',{name:'品牌片横版',exact:true}).waitFor();
  assert.equal(downloads.length,0);
  const downloaded=page.waitForEvent('download');
  await page.getByRole('button',{name:'下载剪映草稿包',exact:true}).click();
  assert.equal((await downloaded).suggestedFilename(),'F002.jypack');
  assert.deepEqual(downloads,['作品/F002-品牌片/07-返修交接/草稿.jianying.json']);
  await tabs.getByRole('button',{name:'视频制作',exact:true}).click();
  await page.getByRole('button',{name:/R001-品牌片/}).click();
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  let editor=page.getByRole('textbox',{name:'修改意见',exact:true});
  assert.equal(await editor.inputValue(),'');
  await editor.fill('品牌片新意见');await editor.blur();
  await page.getByRole('button',{name:'重试保存',exact:true}).click();
  await page.getByText('已保存',{exact:true}).waitFor();
  await choose('F001');
  await page.getByRole('button',{name:/R001-产品片/}).click();
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  await editor.waitFor();
  assert.equal(await editor.inputValue(),'产品片原意见');
  await choose('F002');
  await page.getByRole('button',{name:/R001-品牌片/}).click();
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  await editor.waitFor();
  assert.equal(await editor.inputValue(),'品牌片新意见');
  assert.deepEqual(writes,['F002','F002']);
  await page.reload();
  await page.getByRole('combobox',{name:'切换作品',exact:true}).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'切换作品',exact:true}).getAttribute('data-value'),'F002');
  await editor.waitFor();
  assert.equal(await editor.inputValue(),'品牌片新意见');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`${out}/${width}-works.png`});
  await tabs.getByRole('button',{name:'项目概况',exact:true}).click();
  await page.getByText('项目共用说明',{exact:true}).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'切换作品',exact:true}).count(),0);
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await page.close();
 }
 console.log('Iris多作品网页隔离验收通过',out);
} catch(error) {if(activePage&&!activePage.isClosed())await activePage.screenshot({path:out+'/failure.png'});throw error}
finally {await browser.close();await server.close()}
