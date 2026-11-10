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
const out=await mkdtemp('/private/tmp/W489-workbench-');
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true});
let activePage;
try {
 for (const width of [1280,1366,1920]) {
  const page=await browser.newPage({viewport:{width,height:width===1280?640:width===1366?768:1080}});
  activePage=page;page.setDefaultTimeout(10000);
  const errors=[],unexpected=[],downloads=[],writes=[],technicalDownloads=[];
  page.on('pageerror',error=>errors.push(String(error)));
  const base='/api/workspaces/commercial/projects/隔离多作品';
  const works=[{id:'F001',name:'产品片',key:'作品/F001-产品片',status:'待启动'},{id:'F002',name:'品牌片',key:'作品/F002-品牌片',status:'剪映草稿已交接'},
    {id:'F003',name:'中英同片',key:'作品/F003-中英同片',hasArchive:true},
    {id:'F004',name:'待启动作品',key:'作品/F004-待启动作品',status:'待启动'}];
  const saved={F001:{notes:{'P001/一采/R001':{segment:'P001',stage:'一采',run:'R001',text:'产品片原意见',fileRevision:'F001',updatedAt:'2026-11-06'}},rounds:{}},F002:{notes:{},rounds:{}},F003:{notes:{},rounds:{}}};
  let failWork=true,failSave=true,missing=true;
  let overviewStatus='待启动';
  saved.F001.notes['round/2/P001/一采/R002']={...saved.F001.notes['P001/一采/R001'],roundNumber:2,run:'R002'};
  const file=key=>({kind:'file',key,name:key.split('/').at(-1),url:base+'/files/'+key});
  await page.route('**/api/**',route=>{
   const request=route.request(),url=new URL(request.url()),path=decodeURIComponent(url.pathname);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'commercial',name:'Iris',view:'iris-commercial',projects:[{id:'隔离多作品',name:'隔离多作品'}]}]});
   if(path===base)return route.fulfill({json:{name:'隔离多作品',
    works:works.map(work=>({...work,statusLabel:work.id==='F001'?overviewStatus:work.status})),
    files:[file('README.md'),file('项目状态.md'),{kind:'group',key:'作品',name:'作品',children:[]}]}});
   if(path===base+'/document') {
    const key=url.searchParams.get('path');
    if(key==='项目状态.md'){
     const link=(work,label)=>`<a data-doc="${work.key}/作品状态.md" href="${base}/files/${work.key}/作品状态.md">${label}</a>`;
     const rows=works.map(work=>`<tr><td>${work.id}</td><td>${work.name}</td><td>${link(work,'作品状态')}</td></tr>`).join('');
     return route.fulfill({json:{html:`<h1>项目状态</h1><h2>当前状态</h2><p>${link(works[0],'查看 F001')}</p>
       <h2 id="作品入口">作品入口</h2><div class="table-scroll"><table><thead><tr><th>作品编号</th><th>作品</th><th>状态入口</th></tr></thead><tbody>${rows}</tbody></table></div>`}});
    }
    if(key.endsWith('生产任务-英文R001.md'))return route.fulfill({json:{title:'现行英文生产任务',html:'<p>隔离英文生产段与输入</p>'}});
    return route.fulfill({json:{html:key==='README.md'?'<h1>项目</h1><h2>项目说明</h2><p>项目共用说明</p>':`<h1>正文</h1><h2>作品正文</h2><p>${key.includes('F002')?'品牌片专属正文':'产品片专属正文'}</p>`,url:base+'/files/'+key}});
   }
   if(path===base+'/production-works')return route.fulfill({json:works.map(work=>({kind:'group',name:work.id,title:work.name,key:work.key,hasArchive:work.hasArchive,workStatusLabel:work.status}))});
   const match=path.match(/\/works\/(F\d{3})(.*)$/);
   if(match) {
    const identity=match[1],suffix=match[2],work=works.find(item=>item.id===identity),key=work.key;
    const archive=work.hasArchive && url.searchParams.get('view')==='archive';
    const script=key+'/03-创意脚本/制作脚本-v01.md',packageKey=key+'/07-返修交接/草稿.jianying.json';
    if(suffix==='') {
     if(identity==='F002'&&failWork){failWork=false;return route.fulfill({status:503,json:{detail:'隔离作品读取失败'}})}
     return route.fulfill({json:{productionSection:key+'/06-视频生产',files:[{kind:'group',name:'03-创意脚本',key:key+'/03-创意脚本',children:[file(script)]},{kind:'group',name:'06-视频生产',key:key+'/06-视频生产',children:[]}],irisPresentation:{primary:{'03-创意脚本':[script]},adopted:[],delivery:{status:'草稿可交接',summary:work.name+'交付版本',archivedHandoff:null,items:[{title:work.name+'横版',type:'剪映草稿',version:'v01',purpose:'本片版本',file:{...file(packageKey),jianying:{jypack:base+'/jianying-download?path='+encodeURIComponent(packageKey)}}}]}}}});
    }
    if(identity==='F004' && suffix==='/production-detail')
     return route.fulfill({json:{kind:'group',name:identity,scenes:['whole'],segments:{whole:[]}}});
    if(identity==='F004' && suffix==='/production-downloads'){
     const empty={count:0,url:null,files:[]};
     return route.fulfill({json:Object.fromEntries(['一采','二采','后处理'].map(stage=>[stage,{videos:empty,canvas:empty}]))});
    }
    if(suffix==='/production-detail') {
     const source=n=>({kind:'document',name:'分镜v0'+n+'.md',key:key+'/分镜-v0'+n+'.md',version:'v0'+n,doc:{html:'<h2>已保存分镜v0'+n+'</h2><p>'+identity+'历史来源</p>'}});
     const shot=(id,duration)=>({id,duration,html:'<h4>'+id+'</h4><p>隔离镜头 '+id+'</p>'});
     const video=(id,run,n)=>{
      const oldFailure=identity==='F002'&&id==='P001'&&run==='R001';
      const unavailable=oldFailure||identity==='F001'&&id==='P002'&&run==='R002'&&missing;
      const key=identity+'/'+id+'-'+run+'.webm', mediaUrl=base+'/files/'+identity+'-'+id+'-'+run+'.webm';
      const products=identity==='F002'&&id==='P001'&&run==='R002'?[{
       id:'raw',label:'原版',default:true,key,url:mediaUrl,fileRevision:'raw',
      },{
       id:'repair',label:'修复版',default:false,key:'F002/P001-repair.webm',url:base+'/files/F002-P001-repair.webm',fileRevision:'repair',
      }]:undefined;
      return {key,url:unavailable?'':mediaUrl,run,stage:'一采',approved:identity==='F002'&&n===2,candidateNumber:n,
       fileRevision:unavailable?'':identity+id+run,deliveryStatus:unavailable?'未取回':'已取回',taskStatus:oldFailure?'needs_attention':'completed',products,
       context:{scriptHtml:'<h4>SH001</h4><p><strong>动作</strong>：'+identity+'实际镜头 '+id+' '+run+'</p>',shots:identity==='F002'?(id==='P001'?[shot('SH001',1),shot('SH002',1)]:[shot('SH003',null)]):[shot('SH001',3)],shotTimingSource:identity==='F002'&&id==='P001'?'plan':undefined,dialogues:[{shot:'SH001',index:0,speaker:'角色',original:identity+'原台词'}],prompts:{english:identity+' actual prompt '+run,chinese:identity+'中文 '+run},references:{common:[],segment:[]},
        source:identity==='F001'&&id==='P001'&&run==='R001'?'沿用原视频的生成记录':undefined,issues:[]}};
     };
     const segment=id=>({id,duration:3,scriptHtml:'<h4>SH001</h4><p><strong>动作</strong>：'+identity+'原始动作</p>',videos:[video(id,'R001',1),video(id,'R002',2)]});
     const round=n=>({number:n,created_at:'2026-11-06',episodeRound:true,script:source(n),storyboard:source(n),issues:[],segments:['P001','P002'].map(id=>({id,duration:3,stage:'一采',run:'R00'+n,key:identity+'/'+id+'-R00'+n+'.webm',scriptHtml:segment(id).scriptHtml}))});
     const whole=archive?'C001':'whole';
     const history=file(key+'/06-视频生产/视频历史.md');
     const historicalScript=source(1);
     const scenes=identity==='F002'?['S001','S002']:[whole];
     const members=identity==='F002'?{whole:['P001','P002'],S001:['P001'],S002:['P002']}:{[whole]:['P001','P002']};
     const entries=Object.entries(members);
     const board={candidates:[1,2].map(number=>({kind:'image',name:'对应分镜v0'+number+'导演表',key:key+'/导演表-'+number+'.svg',url:'/component-samples/image.svg',page:1,version:'v0'+number,sourceVersion:'v0'+number,candidateNumber:number})),formal:[],record:null};
     const review=file(key+'/05-资产/资产清单与制作说明-v01.md');
     const materials=identity==='F002'?['pending','revision','adopted','history'].map(group=>({
       kind:'image',name:group+'图',key:key+'/'+group+'.svg',url:'/component-samples/image.svg',
       materialGroup:group,materialReview:review,approvalHtml:'<p>本版本审阅依据</p>',
     })):[];
     return route.fulfill({json:{kind:'group',name:identity,title:work.name,readOnly:archive,scenes:Object.keys(members),
       productionTask:work.hasArchive && !archive ? file(key+'/06-视频生产/生产任务-英文R001.md') : null,
       roundHistory:identity==='F001'?{...history,kind:'document',name:'轮次记录',doc:{html:
         `<h2>隔离轮次记录</h2><p><a href="${base}/files/${historicalScript.key}" data-doc="${historicalScript.key}">第 1 轮 · 制作脚本 v01</a></p>`}}:null,
       episodeRounds:[{number:1,scenes:[whole]},{number:2,scenes}],
       sceneRounds:Object.fromEntries(entries.map(([scene,ids])=>[scene,[1,2].filter(n=>(n===1?[whole]:scenes).includes(scene)).map(n=>({...round(n),segments:round(n).segments.filter(item=>ids.includes(item.id))}))])),
       segments:Object.fromEntries(entries.map(([scene,ids])=>[scene,ids.map(segment)])),script:source(2),storyboards:{[whole]:source(2)},
       directorSheets:{[whole]:board},materials,materialRecord:materials.length?review:null,
       workStatus:identity==='F002'?{label:'剪映草稿已交接',summaryHtml:'<p>隔离作品的现行制作状态</p>',record:file(key+'/作品状态.md')}:null,
       productionComplete:false,productionIssues:[]}});
    }
    if(suffix==='/production-downloads') {
     const download=base+'/jianying-download?path='+encodeURIComponent(packageKey);
     const stagePackage={name:'隔离交接包',count:2,url:download+'&format=zip'};
     const stages=Object.fromEntries(['一采','二采','后处理'].map(stage=>[stage,{videos:stage==='一采'?{...stagePackage,packages:[stagePackage],files:[]}:{count:0,url:null,files:[]},canvas:{count:0,url:null,files:[]}}]));
     if(identity==='F002'){
      stages['一采'].canvas={count:1,url:null,files:[{name:'R002 · P001 · 画布',url:base+'/files/isolated.workflow.json?download=1'}]};
     }
     const workPackages=identity==='F002'?[{key:packageKey,label:'R002 剪映草稿包',version:'R002',purpose:'隔离交接',rounds:[2],count:2,jypack:download+'&format=jypack',zip:download+'&format=zip'}]:archive?
       [{key:'归档/原剪映草稿.jypack',label:'第6轮 · 中文原交接',version:'第6轮',purpose:'隔离历史',rounds:[],archived:true,jypack:base+'/files/归档/原剪映草稿.jypack?download=1',zip:null}]:[];
     return route.fulfill({json:{...stages,workPackages}});
    }
    if(suffix==='/production-notes/export') {
     if(work.hasArchive)assert.equal(url.searchParams.get('view'),'current');
     const changes=request.postDataJSON();writes.push(identity+'-export');
     for(const note of changes.notes)saved[identity].notes[`round/${note.roundNumber}/${note.segment}/${note.stage}/${note.run}`]={...note,updatedAt:'2026-11-06'};
     for(const note of changes.rounds)saved[identity].rounds[note.number]={...note,updatedAt:'2026-11-06'};
     return route.fulfill({json:saved[identity]});
    }
    if(suffix==='/production')return route.fulfill({json:{issues:[],segments:[{id:'P001',duration:3,scriptHtml:'',videos:[{key:identity+'/P001.mp4',url:base+'/files/'+identity+'.webm',run:'R001',stage:'一采',approved:false,adoptionKnown:false,candidateNumber:1,fileRevision:identity,deliveryStatus:'已取回',context:{scriptHtml:'<p>'+identity+'实际镜头</p>',shots:[],prompts:{english:identity+' actual prompt',chinese:identity+'中文'},references:{common:[],segment:[]},issues:[]}}]}],batches:[{id:'R001',name:'R001-'+work.name,segments:[{id:'P001',stage:'一采',key:identity+'/P001.mp4'}]}]}});
    if(suffix==='/production-notes/archive' && work.hasArchive && request.method()==='GET') {
     const note={segment:'P001',stage:'一采',run:'R001',roundNumber:1,text:'原归档分段意见',fileRevision:'old',updatedAt:'2026-11-06'};
     return route.fulfill({json:{episode:'EP001',scenes:{C001:{notes:{'round/1/P001/一采/R001':note},rounds:{}}},
       rounds:{1:{number:1,text:'原归档总体意见',updatedAt:'2026-11-06'}}}});
    }
    if(suffix==='/production-notes' && !archive) {
     if(work.hasArchive)assert.equal(url.searchParams.get('view'),'current');
     if(request.method()==='GET')return route.fulfill({json:saved[identity]});
     writes.push(identity);
     if(failSave){failSave=false;return route.fulfill({status:503,json:{detail:'隔离保存失败'}})}
     const note=request.postDataJSON(),noteKey=(note.roundNumber?'round/'+note.roundNumber+'/':'')+note.segment+'/'+note.stage+'/'+note.run;saved[identity].notes[noteKey]={...note,updatedAt:'2026-11-06'};
     return route.fulfill({json:saved[identity].notes[noteKey]});
    }
   }
   if(path===base+'/jianying-download'){
    downloads.push(url.searchParams.get('path'));
    const extension=url.searchParams.get('format')==='zip'?'zip':'jypack';
    return route.fulfill({body:'isolated package',headers:{'Content-Disposition':'attachment; filename="F002.'+extension+'"'}});
   }
   if(path===base+'/resources')return route.fulfill({json:{items:[],total:0,page_size:20}});
   if(path.endsWith('/isolated.workflow.json')){
    technicalDownloads.push('canvas');
    return route.fulfill({body:'{"nodes":[]}',headers:{'Content-Disposition':'attachment; filename="R002.workflow.json"'}});
   }
   if(path.endsWith('.webm'))return url.searchParams.has('download')?route.continue():route.fulfill({contentType:'video/webm',path:frontend+'public/component-samples/video.webm'});
   unexpected.push(request.method()+' '+path);return route.abort();
  });
  const origin=`http://127.0.0.1:${server.httpServer.address().port}`;
  await page.goto(origin+'/#/spaces/commercial/projects/隔离多作品');
  const tabs=page.getByRole('navigation',{name:'项目栏目',exact:true});
  if(process.env.PRODUCTION_TABS_ONLY==='1') {
   await tabs.getByRole('button',{name:'视频制作',exact:true}).click();
   const workCard=page.locator('[data-episode=F002]');
   await workCard.waitFor();
   assert.equal(await workCard.evaluate(el=>el.getBoundingClientRect().height),48);
   await page.locator('[data-episode=F002]').click();
   const productionTabs=page.getByRole('navigation',{name:'作品制作内容',exact:true});
   await productionTabs.waitFor();
  assert.deepEqual(await page.locator('.episode-detail').evaluate(detail => {
   const panel = getComputedStyle(detail.closest('.panel'));
   const tabs = getComputedStyle(detail.querySelector('.scene-workspace-tabs'));
   const content = getComputedStyle(detail.querySelector('.episode-scene-content'));
   const breadcrumb = document.querySelector('.breadcrumbs');
   return [panel.backgroundColor, panel.borderRadius, panel.padding,
    tabs.marginTop, tabs.gap, content.paddingTop,
    Boolean(breadcrumb.closest('.page-heading-stacked')), getComputedStyle(breadcrumb).marginBottom];
  }), ['rgb(255, 255, 255)', '10px', '23px', '20px', '12px 20px', '20px', true, '0px']);

   assert.deepEqual(await productionTabs.getByRole('button').allTextContents(),['分段制作','分镜与声音','导演分镜表','分镜修改','资源下载']);
   await productionTabs.getByRole('button',{name:'分镜与声音',exact:true}).click();
   await page.locator('.scene-storyboard').getByRole('heading',{name:'已保存分镜v02',exact:true}).waitFor();
  assert.equal(await page.locator('.scene-storyboard .file-action-links').count(),0);
  assert.equal(await page.locator('.scene-storyboard details.chapters').getAttribute('open'),null);
  await page.locator('.scene-storyboard details.chapters > summary').click();
  await page.locator('.scene-storyboard nav[aria-label="章节导航"] button.chapter-link').first().click();
  assert.equal(await page.locator('.scene-storyboard .prose :focus').count(),1);

   await productionTabs.getByRole('button',{name:'分镜修改',exact:true}).click();
   await page.getByRole('region',{name:'修改场次分镜正文',exact:true}).waitFor();
   assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);assert.deepEqual(writes,[]);
   await page.close();continue;
  }
  await page.getByText('项目共用说明',{exact:true}).waitFor();
  const overview=page.getByRole('region',{name:'项目概况',exact:true});
  const firstRow=overview.getByRole('row',{name:/^F001 /});
  await firstRow.getByRole('link',{name:'待启动',exact:true}).waitFor();
  await overview.getByRole('row',{name:/^F003 /}).getByRole('link',{name:'作品状态',exact:true}).waitFor();
  overviewStatus='待审阅';
  await firstRow.getByRole('link',{name:'待审阅',exact:true}).click();
  await page.getByRole('dialog',{name:'待审阅'}).getByText('产品片专属正文',{exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await overview.getByRole('link',{name:'查看 F001',exact:true}).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'切换作品',exact:true}).count(),0);
  await tabs.getByRole('button',{name:'创意与音画',exact:true}).click();
  await page.getByText('产品片专属正文',{exact:true}).waitFor();
  const choose=async id=>{await page.getByRole('combobox',{name:'切换作品',exact:true}).or(page.getByRole('combobox',{name:'快速选择制作对象',exact:true})).click();await page.getByRole('option',{name:new RegExp('^'+id)}).click()};
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
  const workList=page.getByRole('region',{name:'视频制作',exact:true});
  await workList.getByRole('heading',{name:'作品列表',exact:true}).waitFor();
  assert.ok(await workList.evaluate(node=>Boolean(node.closest('.panel'))));
  assert.equal(await page.getByRole('region',{name:'片头与片尾',exact:true}).count(),0);
  const statistics=page.getByLabel('作品制作统计',{exact:true});
  for(const status of ['待启动 2 部','剪映草稿已交接 1 部','未登记制作状态 1 部'])await statistics.getByText(status,{exact:true}).waitFor();
  await page.locator('[data-episode=F002]').click();
  const location=page.getByRole('navigation',{name:'当前位置',exact:true});
  const productionSwitch=location.getByRole('combobox',{name:'快速选择制作对象',exact:true});
  await productionSwitch.waitFor();
  const videoLocator=page.locator('.segment-video video');
  await videoLocator.waitFor();
  await page.evaluate(()=>window.scrollTo(0,0));
  assert.deepEqual(await page.locator('.episode-detail').evaluate(detail=>{
   const strip=detail.querySelector('.segment-progress-scroll');
   const preparation=detail.querySelector('.scene-video-preparation');
   const player=detail.querySelector('.segment-video');
   return [getComputedStyle(detail.closest('.panel')).padding,
    getComputedStyle(detail.querySelector('.episode-scene-content')).paddingTop,
    strip.nextElementSibling===preparation, Boolean(preparation.compareDocumentPosition(player)&Node.DOCUMENT_POSITION_FOLLOWING)];
  }),['23px','20px',true,true]);
  assert.equal(await page.getByRole('region',{name:'作品制作状态',exact:true}).count(),0);
  assert.equal(await page.getByRole('heading',{name:'生产任务记录',exact:true}).count(),0);
  assert.equal(await page.getByRole('link',{name:'下载当前视频',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:/查看.*上集末段/}).count(),0);
  await page.screenshot({path:`${out}/${width}-production-first-screen.png`});
  const product=page.getByRole('combobox',{name:'产物选择',exact:true});
  await product.click();
  await page.getByRole('option',{name:'修复版',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.segment-video video')?.currentSrc.endsWith('F002-P001-repair.webm'));
  assert.equal(await page.getByRole('link',{name:/^查看视频原文件/}).count(),0);
  await product.click();
  await page.getByRole('option',{name:/^原版/}).click();
  await videoLocator.waitFor();
  assert.equal(await page.getByRole('combobox',{name:'修改轮次',exact:true}).getAttribute('data-value'),'2');
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  let editor=page.getByRole('textbox',{name:'修改意见',exact:true});
  assert.equal(await editor.inputValue(),'');
  await editor.fill('品牌片新意见');await editor.blur();
  await page.getByRole('button',{name:'重试保存',exact:true}).click();
  await page.getByText('已保存',{exact:true}).waitFor();
  await choose('F001');
  await page.getByRole('button',{name:'轮次记录',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'查看制作脚本',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'查看生产任务',exact:true}).count(),0);
  const historyDialog=page.getByRole('dialog',{name:'轮次记录'});
  await historyDialog.getByRole('combobox',{name:'查阅轮次'}).click();
  await historyDialog.getByRole('option',{name:'第1轮',exact:true}).click();
  await historyDialog.getByRole('button',{name:'制作脚本 v01',exact:true}).click();
  const scriptDialog=page.getByRole('dialog',{name:'分镜v01.md'});
  await scriptDialog.getByRole('heading',{name:'已保存分镜v01'}).waitFor();
  await scriptDialog.getByRole('button',{name:'关闭',exact:true}).click();
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  await editor.waitFor();
  assert.equal(await editor.inputValue(),'产品片原意见');
  await choose('F002');
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  await editor.waitFor();
  assert.equal(await editor.inputValue(),'品牌片新意见');
  assert.deepEqual(writes,['F002','F002']);
  await page.getByRole('button',{name:'导出修改意见',exact:true}).click();
  const dialog=page.getByRole('dialog');
  const overall=dialog.getByRole('textbox',{name:'第2轮 本轮总体意见',exact:true});
  await overall.fill('品牌片整片意见');
  await dialog.getByRole('button',{name:'保存',exact:true}).click();
  await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  assert.equal(saved.F002.rounds['2'].text,'品牌片整片意见');
  // A candidate outside the selected scene's registered rounds is a preview.
  await page.getByRole('combobox',{name:'版本切换',exact:true}).click();
  await page.getByRole('option',{name:/^候选一/}).click();
  await page.getByRole('img',{name:/^P001 一采：已采用（R002）/}).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'修改轮次',exact:true}).getAttribute('data-value'),'2');
  assert.equal(await page.getByRole('checkbox',{name:'连续播放',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'返回本轮组合',exact:true}).click();

  // Selecting a candidate registered in the scene switches the saved round, as in Nora.
  await choose('F001');
  const roundSelector=page.getByRole('combobox',{name:'修改轮次',exact:true});
  await page.getByRole('combobox',{name:'版本切换',exact:true}).click();
  await page.getByRole('option',{name:/^候选一/}).click();
  assert.equal(await roundSelector.getAttribute('data-value'),'1');
  await page.getByRole('button',{name:'提示词',exact:true}).click();
  await page.getByText('生成资料来源：沿用原视频的生成记录',{exact:true}).waitFor();
  await page.getByRole('button',{name:/^分段 P002/}).click();
  assert.ok(await page.locator('.segment-video video').isVisible());
  assert.equal(await page.getByRole('link',{name:/^查看视频原文件/}).count(),0);
  await page.getByRole('button',{name:'切换到最新修改轮次',exact:true}).click();
  await page.getByRole('button',{name:/^分段 P001/}).click();
  await choose('F002');
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  await editor.waitFor();

  await page.reload();
  await productionSwitch.waitFor();
  assert.equal(await productionSwitch.getAttribute('data-value'),'F002');
  await editor.waitFor();
  assert.equal(await editor.inputValue(),'品牌片新意见');

  // Historical sources and the complete storyboard/editor tabs use the same page as Nora.
  await page.getByRole('button',{name:'分镜与声音',exact:true}).last().click();
  await page.getByRole('heading',{name:'已保存分镜v02',exact:true}).waitFor();
  await page.getByRole('button',{name:'导演分镜表',exact:true}).click();
  await page.getByRole('img',{name:'对应分镜v02导演表',exact:true}).waitFor();
  await page.getByRole('button',{name:'历史版本',exact:true}).click();
  await page.getByRole('img',{name:'对应分镜v01导演表',exact:true}).waitFor();
  assert.equal(await page.getByRole('img',{name:'对应分镜v02导演表',exact:true}).count(),0);
  await page.getByRole('button',{name:'当轮',exact:true}).click();
  await page.getByRole('img',{name:'对应分镜v02导演表',exact:true}).waitFor();
  await page.getByRole('combobox',{name:'修改轮次',exact:true}).click();
  await page.getByRole('option',{name:/^第1轮/}).click();
  await page.getByRole('img',{name:'对应分镜v01导演表',exact:true}).waitFor();
  await page.getByRole('button',{name:/全屏查看第.*导演分镜表/}).click();
  await page.getByRole('button',{name:'退出全屏看图',exact:true}).click();
  await page.getByRole('button',{name:'切换到最新修改轮次',exact:true}).click();
  await page.getByRole('button',{name:'分镜修改',exact:true}).click();
  const draft=page.getByRole('textbox',{name:/P001.*动作/}).first();
  await draft.fill('仅页签草稿');
  await page.getByRole('button',{name:'导出分镜',exact:true}).click();
  await page.getByRole('textbox',{name:'导出分镜文本',exact:true}).waitFor();
  assert.ok((await page.getByRole('textbox',{name:'导出分镜文本',exact:true}).inputValue()).includes('仅页签草稿'));
  await page.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).click();
  assert.equal(writes.length,3); // The storyboard draft did not write any project file.
  await page.getByRole('button',{name:'分段制作',exact:true}).click();
  const firstScene=page.getByRole('button',{name:/^场次 S001/});
  const secondScene=page.getByRole('button',{name:/^场次 S002/});
  await firstScene.click();
  await page.getByRole('button',{name:'提示词',exact:true}).click();
  assert.equal(await page.getByText(/^生成资料来源：/).count(),0);
  await page.getByRole('button',{name:'分镜脚本',exact:true}).click();
  const shot=page.getByRole('button',{name:'跳转到SH002，1秒',exact:true});
  const timingHint='按计划时码定位，实际切点以画面为准。';
  const timingTooltip=page.getByRole('tooltip').filter({hasText:timingHint});
  assert.equal(await page.getByText(timingHint,{exact:true}).count(),0);
  await shot.hover();
  await timingTooltip.waitFor();
  await shot.click();
  await page.waitForFunction(()=>Math.abs(document.querySelector('.segment-video video').currentTime-1)<.05);
  assert.equal(await shot.getAttribute('aria-current'),'step');
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  assert.equal(await page.getByText(timingHint,{exact:true}).count(),0);
  await shot.hover();
  await timingTooltip.waitFor();
  await page.getByRole('button',{name:'SH002 本镜通过',exact:true}).click();
  assert.match(await editor.inputValue(),/00\.01\.0秒，SH002：这个分镜没问题/);
  await editor.blur();
  await page.getByText('已保存',{exact:true}).waitFor();
  await page.getByRole('checkbox',{name:'连续播放',exact:true}).check();
  await page.locator('.segment-video video').dispatchEvent('ended');
  await page.waitForFunction(()=>document.querySelector('[aria-label="版本切换"]').getAttribute('data-value')==='F002/P002-R002.webm');
  assert.equal(await page.getByRole('combobox',{name:'修改轮次',exact:true}).getAttribute('data-value'),'2');
  await secondScene.waitFor();
  assert.equal(await page.getByRole('button',{name:'SH003',exact:true}).isDisabled(),true);
  await editor.fill('第二场隔离意见');await editor.blur();
  await page.getByText('已保存',{exact:true}).waitFor();
  await page.getByRole('button',{name:'导出修改意见',exact:true}).click();
  await dialog.getByRole('heading',{name:'场次 S001',exact:true}).waitFor();
  await dialog.getByRole('heading',{name:'场次 S002',exact:true}).waitFor();
  assert.equal(await dialog.getByRole('textbox',{name:'第2轮 本轮总体意见',exact:true}).inputValue(),'品牌片整片意见');
  await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  await choose('F003');
  const editionTabs=page.getByRole('navigation',{name:'作品制作入口',exact:true});
  const currentEdition=editionTabs.getByRole('button',{name:'现行制作',exact:true});
  const archivedEdition=editionTabs.getByRole('button',{name:'历史归档（只读）',exact:true});
  assert.equal(await currentEdition.getAttribute('aria-current'),'page');
  await page.getByRole('button',{name:'轮次记录',exact:true}).click();
  await page.getByRole('dialog',{name:'轮次记录'}).getByRole('button',{name:'生产任务',exact:true}).click();
  await dialog.getByText('隔离英文生产段与输入',{exact:true}).waitFor();
  await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  await page.getByRole('button',{name:'修改意见',exact:true}).click();
  await page.getByRole('button',{name:'导出修改意见',exact:true}).click();
  await dialog.getByRole('textbox',{name:'第2轮 本轮总体意见',exact:true}).fill('同片现行总体意见');
  await dialog.getByRole('button',{name:'保存',exact:true}).click();
  await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  assert.equal(saved.F003.rounds['2'].text,'同片现行总体意见');
  const writesBeforeArchive=writes.length;
  await archivedEdition.click();
  await page.getByRole('button',{name:'下载归档剪映包',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'查看生产任务',exact:true}).count(),0);
  assert.equal(await productionSwitch.getAttribute('data-value'),'F003');
  await page.getByRole('button',{name:'查看历史意见',exact:true}).click();
  assert.equal(await dialog.getByRole('textbox',{name:/P001.*修改意见/}).inputValue(),'原归档分段意见');
  assert.equal(await dialog.getByRole('textbox',{name:/P001.*修改意见/}).getAttribute('readonly'),'');
  assert.equal(await dialog.getByRole('textbox',{name:'第1轮 本轮总体意见',exact:true}).inputValue(),'原归档总体意见');
  assert.equal(await dialog.getByRole('button',{name:'保存',exact:true}).count(),0);
  await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  assert.equal(writes.length,writesBeforeArchive);
  await currentEdition.click();
  await page.getByRole('button',{name:'轮次记录',exact:true}).click();
  await page.getByRole('dialog',{name:'轮次记录'}).getByRole('button',{name:'生产任务',exact:true}).waitFor();
  await page.getByRole('dialog',{name:'轮次记录'}).getByRole('button',{name:'关闭',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:'下载归档剪映包',exact:true}).count(),0);
  await choose('F001');
  await page.getByRole('button',{name:'分镜脚本',exact:true}).click();
  const continuous=page.getByRole('checkbox',{name:'连续播放',exact:true});
  await continuous.check();
  await page.locator('.segment-video video').dispatchEvent('ended');
  await page.getByText(/连续播放已停在当前分段/).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'版本切换',exact:true}).getAttribute('data-value'),'F001/P001-R002.webm');
  missing=false;
  await page.reload();
  await continuous.check();
  await page.locator('.segment-video video').dispatchEvent('ended');
  await page.waitForFunction(()=>document.querySelector('[aria-label="版本切换"]').getAttribute('data-value')==='F001/P002-R002.webm');
  await page.getByRole('button',{name:'宽屏显示',exact:true}).click();
  await page.getByRole('button',{name:'恢复布局',exact:true}).click();
  assert.equal(await page.getByRole('checkbox',{name:'重复播放',exact:true}).isDisabled(),true);
  await continuous.uncheck();
  await page.getByRole('checkbox',{name:'重复播放',exact:true}).check();
  assert.equal(await continuous.isChecked(),false);
  await page.getByRole('button',{name:'资源下载',exact:true}).click();
  await page.getByText('未关联整片轮次 · 隔离交接包',{exact:true}).waitFor();
  const before=downloads.length;
  assert.equal(before,1);
  const pack=page.waitForEvent('download');
  await page.getByRole('button',{name:'剪映草稿包',exact:true}).and(page.locator('button:not(:disabled)')).first().click();
  await pack;
  assert.equal(downloads.length,before+1);
  await choose('F002');
  const handoff=page.getByRole('group',{name:'整片交接下载',exact:true});
  await handoff.getByText('第2轮 · R002 剪映草稿包（2段）',{exact:true}).waitFor();
  assert.equal(downloads.length,before+1);
  for(const [label,ext] of [['剪映草稿包','jypack'],['本片 ZIP 下载','zip']]){
   const clicked=page.waitForEvent('download');
   await handoff.getByRole('button',{name:label,exact:true}).click();
   assert.equal((await clicked).suggestedFilename(),'F002.'+ext);
   assert.equal(downloads.at(-1),'作品/F002-品牌片/07-返修交接/草稿.jianying.json');
  }
  await page.getByText('制作素材与审阅（4）',{exact:true}).click();
  for(const group of ['待审核','待修改','当前采用','历史素材'])await page.getByText(group+'（1）',{exact:true}).waitFor();
  await page.getByRole('button',{name:'查看素材记录',exact:true}).click();
  await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  await page.getByRole('button',{name:'分段制作',exact:true}).click();
  await firstScene.click();
  await page.getByRole('img',{name:/^P001 一采：已采用（R002）/}).waitFor();
  await page.getByRole('combobox',{name:'修改轮次',exact:true}).click();
  await page.getByRole('option',{name:/^第1轮/}).click();
  assert.equal(await handoff.count(),0);
  await page.getByRole('img',{name:/^P001 一采：R001 · 任务状态待核对 · 未取回/}).waitFor();
  await page.getByRole('button',{name:'资源下载',exact:true}).click();
  await page.getByRole('region',{name:'一采资源下载',exact:true}).getByText('第2轮 · R002 剪映草稿包',{exact:true}).waitFor();
  const technical=page.getByLabel('一采原画布',{exact:true});
  await technical.getByText('原画布',{exact:true}).click();
  assert.deepEqual(technicalDownloads,[]);
  for(const [label,file] of [['画布','R002.workflow.json']]){
   const triggered=page.waitForEvent('download');
   await technical.getByRole('button',{name:'R002 · P001 · '+label,exact:true}).click();
   assert.equal((await triggered).suggestedFilename(),file);
  }
  assert.equal(await page.getByRole('combobox',{name:'修改轮次',exact:true}).getAttribute('data-value'),'1');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`${out}/${width}-works.png`});
  await choose('F004');
  assert.equal(await page.getByRole('combobox',{name:'修改轮次',exact:true}).isDisabled(),true);
  for(const [tab,title] of [['分段制作','暂无可显示的分段'],['分镜与声音','尚未登记分镜'],
   ['分镜修改','尚无可修改的分镜'],['资源下载','暂无可下载资源']]){
   await page.locator('.episode-detail').getByRole('button',{name:tab,exact:true}).click();
   await page.getByRole('heading',{name:title,exact:true}).waitFor();
  }
  await page.getByRole('button',{name:'轮次记录',exact:true}).click();
  await page.getByText('尚未登记轮次。',{exact:true}).waitFor();
  await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  await location.getByRole('link',{name:'视频制作',exact:true}).click();
  await workList.getByRole('heading',{name:'作品列表',exact:true}).waitFor();
  await tabs.getByRole('button',{name:'项目概况',exact:true}).click();
  await page.getByText('项目共用说明',{exact:true}).waitFor();
  assert.equal(await page.getByRole('combobox',{name:'切换作品',exact:true}).count(),0);
  for (const label of await tabs.getByRole('button').allTextContents()) {
   await tabs.getByRole('button',{name:label,exact:true}).click();
   const title = location.locator('[aria-current="page"]');
   assert.equal(await title.textContent(),label);
   assert.deepEqual(await title.evaluate(element=>{
    const style=getComputedStyle(element);
    return [style.color,style.fontSize,style.fontWeight];
   }),['rgb(37, 113, 99)','22px','600']);
   assert.equal(await page.getByRole('heading',{name:label,exact:true}).count(),0);
  }
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await page.close();
 }
 console.log(process.env.PRODUCTION_TABS_ONLY==='1'?'Iris制作页默认标签、分镜正文及修改入口三档检查通过':'Iris完整共用制作页隔离验收通过',out);
} catch(error) {if(activePage&&!activePage.isClosed())await activePage.screenshot({path:out+'/failure.png'});throw error}
finally {await browser.close();await server.close()}
