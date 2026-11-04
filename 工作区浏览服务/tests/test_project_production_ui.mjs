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
  const saved={notes:{},rounds:{}};let failSave=true,failRead=true,failStoryboard=true;
  activePage=page;page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   const req=route.request(),u=new URL(req.url()),path=decodeURIComponent(u.pathname);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'commercial',name:'Iris',view:'iris-commercial',projects:[{id:'隔离样片',name:'隔离样片'}]}]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path==='/api/workspaces/commercial/projects/未制作样片')return route.fulfill({json:{name:'未制作样片',files:[]}});
   const historical=path.startsWith('/api/workspaces/commercial/projects/历史样片');
   const requirementsOnly=path.startsWith('/api/workspaces/commercial/projects/仅有需求');
   const base='/api/workspaces/commercial/projects/'+(historical?'历史样片':requirementsOnly?'仅有需求':'隔离样片');
   const doc=(key)=>({kind:'file',name:key.split('/').at(-1),key,url:base+'/files/'+key});
   const folder=(name,files)=>({kind:'group',name,key:name,children:files.map(file=>doc(name+'/'+file))});
   const requirement='01-客户资料/需求与来源-v02.md';
   const brief='02-参考分析/制作简报.md';
   const archived='归档/旧订单/制作简报.md';
   const script='03-创意脚本/正式剧本-v04.md';
   const storyboard='04-分镜声音/分镜与声音制作稿.md';
   const assetList='05-资产/资产清单.md';
   const archivedAssets='归档/旧订单/05-资产准备/资产清单.md';
   const handoff='07-返修交接/交接说明.md';
   const review='08-完单复盘/项目复盘.md';
   const packageUrl=base+'/jianying-download?path=07-返修交接/剪辑.jianying.json&format=jypack';
   if(path===base)return route.fulfill({json:{name:'隔离样片',productionSection:'06-视频生产',
   irisPresentation:{primary:{
     '01-客户资料':historical?[]:[requirement],
     '02-参考分析':historical||requirementsOnly?[]:[brief],
     '03-创意脚本':historical||requirementsOnly?[]:[script],
     '04-分镜声音':historical||requirementsOnly?[]:[storyboard],
     '05-资产':historical||requirementsOnly?[]:[assetList],'06-视频生产':['06-视频生产/生产任务.md'],
     '07-返修交接':['07-返修交接/交接说明.md'],'08-完单复盘':['08-完单复盘/项目复盘.md'],
   },brief:{sources:historical||requirementsOnly?[]:[doc('01-客户资料/需求原件.md'),{...doc('资源/参考-fixture.png'),kind:'image'}],
     archived:historical?[doc(archived)]:[]},
     stageArchives:historical?{
       '03-创意脚本':[folder('归档/旧订单/03-创意与脚本',['旧脚本.md'])],
       '04-分镜声音':[folder('归档/旧订单/04-分镜与视觉方案',['旧分镜.md'])],
       '05-资产':[doc(archivedAssets)],
     }:{},
     delivery:{status:requirementsOnly?'样片审阅中':'剪映草稿已交接',summary:'隔离交付状态。',archivedHandoff:null,
       items:requirementsOnly?[]:[
         {title:'隔离剪映草稿',type:'剪映草稿',version:'R006',purpose:'交给剪辑。',file:{...doc('07-返修交接/剪辑.jianying.json'),jianying:{jypack:packageUrl}}},
         {title:'隔离审阅样片',type:'审阅样片',version:'v01',purpose:'供审阅。',file:{...doc('资源/预览.webm'),kind:'video'}},
       ]},
     adopted:historical||requirementsOnly?[]:[{title:'A001 · 隔离采用图',version:'V001',media:{...doc('fixture.png'),kind:'image'}}]},files:[
     doc('README.md'),doc('项目状态.md'),folder('01-客户资料',historical?[]:['需求原件.md','需求与来源-v02.md','需求与来源-v01.md']),
     folder('02-参考分析',historical||requirementsOnly?[]:['制作简报.md']),
     folder('03-创意脚本',historical||requirementsOnly?[]:['正式剧本-v04.md','正式剧本-v03.md']),
     folder('04-分镜声音',historical||requirementsOnly?[]:['分镜与声音制作稿.md','导演表.md']),folder('05-资产',historical||requirementsOnly?[]:['资产清单.md','候选.png']),folder('06-视频生产',['生产任务.md','执行记录.md']),
     folder('07-返修交接',['交接说明.md']),folder('08-完单复盘',['项目复盘.md']),folder('99-综合资料',['项目实验.md']),
   ]}});
   if(path===base+'/document'){
    const key=u.searchParams.get('path');
    if(key==='README.md'&&failRead){
     failRead=false;return route.fulfill({status:503,json:{detail:'隔离读取失败'}});
    }
    if(key===storyboard&&failStoryboard){
     failStoryboard=false;return route.fulfill({status:503,json:{detail:'隔离分镜读取失败'}});
    }
    const html=key==='README.md' ? '<h1>隔离项目说明</h1><h2>项目专用约定</h2><p>这里是项目说明正文。</p>'
      : key==='项目状态.md' ? '<h1>状态</h1><h2>当前决定</h2><p>'+ (historical?'已交付并归档':'等待用户审阅。') +'</p>'
        : key===brief ? '<h1>简报封面</h1><h2>制作简报正文</h2><p>这里是现行制作简报。</p>'
          : key===requirement ? '<h1>需求记录</h1><h2>需求正文</h2><p>这里是现行需求。</p>'
            : key===archived ? '<h1>历史简报正文</h1>'
              : key===script ? '<h1>剧本封面</h1><h2>剧本正文</h2><p>这里是正式剧本v04。</p>'
                : key===storyboard ? '<h1>分镜封面</h1><h2>逐镜正文</h2><p>这里是现行分镜。</p>'
                  : key===assetList ? '<h1>清单封面</h1><h2>统一资产清单</h2><table><tbody><tr><td>本镜采用 A001</td></tr></tbody></table>'
                    : key===archivedAssets ? '<h1>历史清单封面</h1><h2>旧订单的资产清单</h2>'
                      : key===handoff ? '<h1>交接记录</h1><h2>交接正文</h2>'
                        : key===review ? '<h1>复盘记录</h1><h2>复盘正文</h2>'
        : '<h1>隔离资料正文</h1>';
    return route.fulfill({json:{html,url:base+'/files/'+key}});
   }
   if(path===base+'/resources')return route.fulfill({json:{items:[],total:0,page_size:20}});
   if(path===base+'/jianying-download')return route.fulfill({body:'隔离下载响应',headers:{'Content-Disposition':'attachment; filename="fixture.jypack"'}});
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
  const tabs=page.getByRole('navigation',{name:'项目栏目',exact:true});
  const overview=page.getByRole('navigation',{name:'概况文档',exact:true});
  await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.getByText('这里是项目说明正文。',{exact:true}).waitFor();
  assert.equal(await overview.getByRole('button',{name:'项目说明',exact:true}).getAttribute('aria-current'),'page');
  assert.equal(await page.getByRole('dialog').count(),0);
  const chapters=page.locator('.document .chapters');
  assert.equal(await chapters.getAttribute('open'),null);
  assert.ok(await page.getByText('这里是项目说明正文。',{exact:true}).evaluate(node=>node.getBoundingClientRect().bottom<=innerHeight-44));
  await chapters.getByText('章节导航',{exact:true}).click();
  await chapters.getByRole('button',{name:'项目专用约定',exact:true}).waitFor();
  await chapters.getByText('章节导航',{exact:true}).click();
  await page.screenshot({path:`${out}/${width}-overview.png`});
  await overview.getByRole('button',{name:'项目状态',exact:true}).click();
  await page.getByText('等待用户审阅。',{exact:true}).waitFor();
  await page.getByRole('heading',{name:'当前决定',exact:true}).waitFor();
  assert.equal(await page.getByRole('dialog').count(),0);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await overview.getByRole('button',{name:'项目说明',exact:true}).click();
  await page.getByText('这里是项目说明正文。',{exact:true}).waitFor();
  assert.deepEqual(await tabs.getByRole('button').allTextContents(),['项目概况','需求与参考','创意与音画','分镜与声音','资产准备','视频制作','交付与复盘','项目资源','全部资料']);
  await tabs.getByRole('button',{name:'需求与参考',exact:true}).click();
  const briefTabs=page.getByRole('navigation',{name:'需求与参考文档',exact:true});
  await page.getByRole('heading',{name:'制作简报正文',exact:true}).waitFor();
  assert.equal(await page.getByRole('dialog').count(),0);
  const sources=page.locator('details').filter({has:page.locator('summary').getByText('客户原件与参考',{exact:true})});
  assert.ok(await chapters.evaluate(node=>Boolean(node.compareDocumentPosition(node.parentElement.querySelector('.iris-brief-attachments'))&Node.DOCUMENT_POSITION_FOLLOWING)));
  assert.equal(await sources.getAttribute('open'),null);
  assert.equal(await sources.getByRole('button',{name:'需求原件',exact:true}).isVisible(),false);
  await chapters.getByText('章节导航',{exact:true}).click();
  await chapters.getByRole('button',{name:'制作简报正文',exact:true}).click();
  assert.ok(await page.getByRole('heading',{name:'制作简报正文',exact:true}).evaluate(node=>node===document.activeElement));
  await chapters.getByText('章节导航',{exact:true}).click();
  await sources.getByText('客户原件与参考',{exact:true}).click();
  await page.getByRole('button',{name:'需求原件',exact:true}).click();
  await page.getByRole('dialog').getByRole('heading',{name:'隔离资料正文',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'参考-fixture',exact:true}).click();
  await page.getByRole('dialog').getByRole('img',{name:'参考-fixture',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await briefTabs.getByRole('button',{name:'需求与来源',exact:true}).click();
  await page.getByRole('heading',{name:'需求正文',exact:true}).waitFor();
  await briefTabs.getByRole('button',{name:'制作简报',exact:true}).click();
  await page.getByRole('heading',{name:'制作简报正文',exact:true}).waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`${out}/${width}-brief.png`});
  await page.locator('summary').getByText('其他资料（含工作稿、旧版和执行记录）',{exact:true}).click();
  await page.locator('summary').getByText('01-客户资料',{exact:true}).click();
  await page.getByRole('button',{name:'需求与来源-v01.md',exact:true}).waitFor();
  await tabs.getByRole('button',{name:'创意与音画',exact:true}).click();
  const creative=page.getByRole('region',{name:'创意与音画正文',exact:true});
  await creative.getByText('这里是正式剧本v04。',{exact:true}).waitFor();
  assert.equal(await creative.getByRole('heading',{name:'剧本封面',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'正式剧本-v03.md',exact:true}).isVisible(),false);
  await creative.getByText('章节导航',{exact:true}).click();
  await creative.getByRole('button',{name:'剧本正文',exact:true}).click();
  assert.ok(await creative.getByRole('heading',{name:'剧本正文',exact:true}).evaluate(node=>node===document.activeElement));
  await tabs.getByRole('button',{name:'分镜与声音',exact:true}).click();
  await page.getByRole('button',{name:'重新读取',exact:true}).click();
  const storyboardPanel=page.getByRole('region',{name:'分镜与声音正文',exact:true});
  await storyboardPanel.getByText('这里是现行分镜。',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'导演表.md',exact:true}).isVisible(),false);
  await page.locator('summary').getByText('其他资料（含工作稿、旧版和执行记录）',{exact:true}).click();
  await page.getByRole('button',{name:'导演表.md',exact:true}).click();
  await page.getByRole('dialog').getByRole('heading',{name:'隔离资料正文',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await tabs.getByRole('button',{name:'资产准备',exact:true}).click();
  const assetTabs=page.getByRole('navigation',{name:'资产准备视图',exact:true});
  const adoptedPanel=page.getByRole('region',{name:'已采用素材',exact:true});
  assert.equal(await assetTabs.getByRole('button',{name:'已采用素材',exact:true}).getAttribute('aria-current'),'page');
  await adoptedPanel.getByText('资源版本：V001',{exact:true}).waitFor();
  assert.equal(await adoptedPanel.getByRole('link',{name:'下载',exact:true}).count(),0);
  await page.getByRole('img',{name:'fixture.png',exact:true}).click();
  await page.getByRole('dialog').getByRole('link',{name:'下载',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await assetTabs.getByRole('button',{name:'资产清单与制作说明',exact:true}).click();
  const assetListPanel=page.getByRole('region',{name:'资产清单与制作说明正文',exact:true});
  await assetListPanel.getByRole('cell',{name:'本镜采用 A001',exact:true}).waitFor();
  await assetListPanel.getByText('章节导航',{exact:true}).waitFor();
  assert.equal(await page.getByRole('dialog').count(),0);
  assert.equal(await page.getByRole('button',{name:'候选.png',exact:true}).isVisible(),false);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await tabs.getByRole('button',{name:'项目资源',exact:true}).click();
  await page.getByText('暂无符合条件的资源。',{exact:true}).waitFor();
  await tabs.getByRole('button',{name:'交付与复盘',exact:true}).click();
  const deliveryTabs=page.getByRole('navigation',{name:'交付与复盘视图',exact:true});
  const deliveryResults=page.getByRole('region',{name:'交付成果',exact:true});
  await deliveryResults.getByRole('heading',{name:'剪映草稿已交接',exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.iris-delivery-item video')?.readyState>=2);
  const packageDownload=page.waitForEvent('download');
  await deliveryResults.getByRole('button',{name:'下载剪映草稿包',exact:true}).click();
  assert.equal((await packageDownload).suggestedFilename(),'fixture.jypack');
  await deliveryTabs.getByRole('button',{name:'返修与交接',exact:true}).click();
  await page.getByRole('heading',{name:'交接正文',exact:true}).waitFor();
  assert.equal(await deliveryResults.count(),0);
  await deliveryTabs.getByRole('button',{name:'完单复盘',exact:true}).click();
  await page.getByRole('heading',{name:'复盘正文',exact:true}).waitFor();
  assert.equal(await page.getByRole('dialog').count(),0);
  await tabs.getByRole('button',{name:'全部资料',exact:true}).click();
  await page.getByText('01-客户资料',{exact:true}).waitFor();
  await page.getByText('99-综合资料',{exact:true}).waitFor();
  await tabs.getByRole('button',{name:'视频制作',exact:true}).click();
  await page.getByRole('heading',{name:'生产批次',exact:true}).waitFor();
  await page.getByRole('button',{name:'生产任务.md',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'执行记录.md',exact:true}).isVisible(),false);
  assert.equal(await page.locator('.segment-video video').count(),0);
  await page.screenshot({path:`${out}/${width}-batches.png`});
  await page.getByRole('button',{name:/R002-隔离后处理/}).click();
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
  await page.getByRole('button',{name:'返回批次列表',exact:true}).click();
  await page.getByRole('heading',{name:'生产批次',exact:true}).waitFor();
  await page.goto(origin+'/#/spaces/commercial/projects/历史样片');
  await overview.getByRole('button',{name:'项目状态',exact:true}).click();
  await page.getByText('已交付并归档',{exact:true}).waitFor();
  await tabs.getByRole('button',{name:'需求与参考',exact:true}).click();
  await page.getByText('查看历史需求与参考',{exact:true}).click();
  await page.getByRole('button',{name:'制作简报.md',exact:true}).click();
  await page.getByRole('dialog').getByRole('heading',{name:'历史简报正文',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await tabs.getByRole('button',{name:'创意与音画',exact:true}).click();
  await creative.getByText('查看历史创意与音画',{exact:true}).click();
  await creative.getByText('归档/旧订单/03-创意与脚本',{exact:true}).click();
  await creative.getByRole('button',{name:'旧脚本.md',exact:true}).click();
  await page.getByRole('dialog').getByRole('heading',{name:'隔离资料正文',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await tabs.getByRole('button',{name:'分镜与声音',exact:true}).click();
  await storyboardPanel.getByText('查看历史分镜与声音',{exact:true}).click();
  await storyboardPanel.getByText('归档/旧订单/04-分镜与视觉方案',{exact:true}).click();
  await storyboardPanel.getByRole('button',{name:'旧分镜.md',exact:true}).waitFor();
  await tabs.getByRole('button',{name:'资产准备',exact:true}).click();
  await page.getByRole('heading',{name:'旧订单的资产清单',exact:true}).waitFor();
  assert.equal(await assetTabs.getByRole('button',{name:'查看历史资产清单',exact:true}).getAttribute('aria-current'),'page');
  assert.equal(await page.getByRole('dialog').count(),0);
  await page.getByRole('navigation',{name:'项目栏目',exact:true}).getByRole('button',{name:'视频制作',exact:true}).click();
  await page.getByRole('button',{name:/R002-隔离后处理.*历史只读/}).click();
  await page.locator('.segment-script-content').getByText('历史分镜快照',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'修改意见',exact:true}).count(),0);
  await page.goto(origin+'/#/spaces/commercial/projects/仅有需求');
  await tabs.getByRole('button',{name:'需求与参考',exact:true}).click();
  await page.getByRole('heading',{name:'需求正文',exact:true}).waitFor();
  assert.equal(await briefTabs.count(),0);
  await tabs.getByRole('button',{name:'创意与音画',exact:true}).click();
  await creative.getByText('暂无可确认的阶段主文件。',{exact:true}).waitFor();
  await tabs.getByRole('button',{name:'交付与复盘',exact:true}).click();
  await deliveryResults.getByRole('heading',{name:'样片审阅中',exact:true}).waitFor();
  assert.equal(await deliveryResults.getByRole('button',{name:'下载剪映草稿包',exact:true}).count(),0);
  await deliveryResults.getByRole('button',{name:'前往视频制作',exact:true}).click();
  await page.getByRole('heading',{name:'生产批次',exact:true}).waitFor();
  await page.goto(origin+'/#/spaces/commercial/projects/未制作样片');
  await page.getByText('暂无项目说明或状态记录。',{exact:true}).waitFor();
  await tabs.getByRole('button',{name:'视频制作',exact:true}).click();
  await page.getByText('本项目暂无视频制作资料。',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);assert.ok(writes.every(path=>path.endsWith('/production-notes')));
  console.log(JSON.stringify({width,passed:true,reviewWrites:writes.length}));await page.close();
 }
 console.log('Screenshots: '+out);
}catch(error){await activePage.screenshot({path:out+'/failure.png'});console.log('Failed body: '+await activePage.locator('body').innerText());console.log('Screenshots: '+out);throw error}finally{await browser.close();await server.close()}
