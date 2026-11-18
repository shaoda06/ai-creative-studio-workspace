// Actual document adapter output, isolated responses, no real project writes.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {createServer}=await import(pathToFileURL(require.resolve('vite')));
const react=(await import(pathToFileURL(require.resolve('@vitejs/plugin-react')))).default;
const frontend=fileURLToPath(new URL('../frontend/',import.meta.url));
const tool=fileURLToPath(new URL('../',import.meta.url));
const version=JSON.parse(await readFile(frontend+'package.json','utf8')).version;
const python=join(tool,'.venv',...(process.platform==='win32'?['Scripts','python.exe']:['bin','python']));
const fixture=JSON.parse(execFileSync(python,['-X','utf8','-c',`
import base64,json
from tests.test_chloe_publication import ChloePublicationTests, publication
x=ChloePublicationTests();x.setUp()
try:
 film, cover, path=x.prepare()
 from media_files import store_media
 from chloe_resources import import_media
 from PIL import Image
 from pathlib import Path
 store_media(x.project,x.project/'成片/第二版成片.webm',source=film)
 second=x.base/'第二封面.png';Image.new('RGB',(200,150),'navy').save(second)
 ref=import_media(x.root,second,'second-cover',project=x.project.name)
 x.append(x.project/'README.md','发布记录',['P001',x.row[3],x.row[4],x.row[5],'[Q001](<发布资料.md>)',x.row[8],x.row[10],x.row[11],
                                      '未取得','未取得','立即发布','待提交','未取得','未取得','示例安排','未取得'])
 x.row[3]='[成片](<成片/第二版成片.webm>)'
 x.row[4]=f'[本视频:{ref["resource_id"]}@{ref["version"]}](<{Path(ref["absolute_file"]).relative_to(x.project).as_posix()}>)'
 x.row[0]='Q002';x.row[1]='小红书';x.row[6]='另一平台的长标题'+('细节展示'*18)
 x.row[12]='2026-11-18T20:30:00+08:00';x.row[13]='用户手动'
 x.append(path,'发布资料',x.row)
 readme=x.project/'README.md'
 readme.write_text(readme.read_text().replace('| 视频状态 | 制作中 |','| 视频状态 | 已发布 |'))
 x.append(readme,'发布记录',['P002',x.row[3],x.row[4],x.row[5],'[Q002](<发布资料.md>)',x.row[8],x.row[10],x.row[11],
                            '未取得','2026-11-18T21:00:00+08:00','立即发布','已发布','sample-002','https://example.com/post/002','示例安排','https://example.com/post/002'])
 detail=publication.detail(x.root,x.project.name,x.api)
 images={c['media']['url']:base64.b64encode((x.root/c['media']['key']).read_bytes()).decode() for m in detail['materials'] for c in m['covers']}
 print(json.dumps({'list':publication.listing(x.root,x.api),'detail':detail,'images':images}))
finally:x.doCleanups()
`],{cwd:tool,encoding:'utf8'}));
const listItems=[{...fixture.list[0],id:'V002',project:'V002-测试',status:'待发布'}, {...fixture.list[0],id:'V1000',project:'V1000-测试',status:'已发布'}, ...fixture.list, {...fixture.list[0],id:'V010',project:'V010-测试'}];
const removable={...fixture.detail.finals[0],name:'未引用成片.webm',key:fixture.detail.finals[0].key.replace(/[^/]+$/, '未引用成片.webm'),url:fixture.detail.finals[0].url.replace(/[^/]+$/,encodeURIComponent('未引用成片.webm')),videoMetadata:null};
fixture.detail.finals[0].videoMetadata={width:1920,height:1088,duration:8};
fixture.detail.finals[1].videoMetadata={width:1088,height:1920,duration:12.345};
fixture.detail.finals.push(removable);
const uploaded={...fixture.detail.finals[0],name:'最新上传.webm',key:fixture.detail.finals[0].key.replace(/[^/]+$/, '最新上传.webm'),url:fixture.detail.finals[0].url.replace(/[^/]+$/,encodeURIComponent('最新上传.webm'))};
const uploadPath=decodeURIComponent(removable.url).split('/files/')[0]+'/files';
const video=await readFile(frontend+'public/component-samples/video.webm');
const images=new Map(Object.entries(fixture.images).map(([url,bytes])=>[decodeURIComponent(url),Buffer.from(bytes,'base64')]));
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 for(const [width,height] of [[1280,640],[1366,768],[1920,1080]]){
  const context=await browser.newContext({viewport:{width,height},permissions:['clipboard-read','clipboard-write']});
  const page=await context.newPage();page.setDefaultTimeout(10000);
  const errors=[],unexpected=[],writes=[];let failList=true, failDetail=false, empty=false, noMaterial=false, missingPortrait=false, failDelete=true, removed=false, hasUpload=false;
  let uploadedFile=uploaded, pendingDownload, materialsOverride;
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',async route=>{
   const request=route.request(),path=decodeURIComponent(new URL(request.url()).pathname);
   if(request.method()!=='GET')writes.push(path);
   if(request.method()==='POST' && path===uploadPath){
    assert.match(request.headers()['content-type'],/^multipart\/form-data/);
    assert.equal(await page.getByRole('button',{name:'更换文件',exact:true}).isDisabled(),true);
    hasUpload=true;return route.fulfill({status:201,json:{name:uploaded.name,key:uploaded.key}});
   }
   if(request.method()==='PATCH' && path===decodeURIComponent(uploaded.url)){
    const {name}=request.postDataJSON();
    if(name==='同名')return route.fulfill({status:409,json:{detail:'已有同名成片，请换一个文件名'}});
    assert.equal(name,'新文件名');
    uploadedFile={...uploaded,name:name+'.webm',key:uploaded.key.replace(/[^/]+$/,name+'.webm'),url:uploaded.url.replace(/[^/]+$/,encodeURIComponent(name+'.webm'))};
    return route.fulfill({json:{name:uploadedFile.name,key:uploadedFile.key}});
   }
   if(request.method()==='DELETE' && path===decodeURIComponent(removable.url)){
    if(failDelete)return route.fulfill({status:409,json:{detail:'隔离删除失败，请重试'}});
    removed=true;return route.fulfill({json:{ok:true}});
   }
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'chloe',name:'Chloe AI视频带货',view:'chloe-commerce',projects:[]}]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path.endsWith('/production-detail')){
    const item=listItems.find(item=>path.includes('/projects/'+item.project+'/'));
    const color={'制作中':'blue','待发布':'orange','已发布':'green'}[item.status];
    return route.fulfill({json:{kind:'group',name:item.project,statusHtml:`<span class="status-badge status-${color}">${item.status}</span>`,scenes:['whole'],segments:{whole:[{id:'P001',duration:20,videos:[]}]}}});
   }
   if(path.endsWith('/publication-videos'))return failList?route.fulfill({status:409,body:'隔离列表错误'}):route.fulfill({json:empty?[]:listItems});
   if(path.endsWith('/publication-videos/'+fixture.detail.project))return failDetail?route.fulfill({status:409,body:'隔离资料错误'}):route.fulfill({json:noMaterial?{...fixture.detail,materials:[],finals:[],history:[]}:missingPortrait?{...fixture.detail,materials:fixture.detail.materials.map(m=>({...m,covers:m.covers.map((c,i)=>i===1?{...c,media:null}:c)}))}:{...fixture.detail,materials:materialsOverride??fixture.detail.materials,finals:[...(hasUpload?[uploadedFile]:[]),...fixture.detail.finals.filter(f=>!removed||f.key!==removable.key)]} });
   if(path.endsWith('.webm')){
    if(path===decodeURIComponent(fixture.detail.finals[0].url))await pendingDownload?.promise;
    return route.fulfill({contentType:'video/webm',body:video,headers:{'Content-Disposition':"inline; filename*=utf-8''"+encodeURIComponent('最终成片.webm')}});
   }
   if(path.endsWith('.png'))return route.fulfill({contentType:'image/png',body:images.get(path)});
   unexpected.push(path);return route.fulfill({status:404,body:'unexpected isolated request'});
  });
  await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe?section=publication');
  await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  failList=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
  const cards=page.locator('.episode-grid > .episode-button');
  await cards.first().waitFor();
  assert.deepEqual(await page.locator('[aria-label="作品发布统计"] > span').allTextContents(), ['共 4 部', ...['制作中','待发布','已发布'].map(status=>`${status} ${listItems.filter(item=>item.status===status).length} 部`)]);
  assert.deepEqual(await cards.locator('strong').allTextContents(),['V1000','V010','V002',fixture.list[0].id]);
  const card=page.locator(`[data-episode="${fixture.detail.project}"]`);
  assert.equal(await card.locator('.episode-button-title').innerText(),fixture.list[0].title);
  await card.locator('.episode-button-status').getByText(fixture.list[0].status,{exact:true}).waitFor();
  await card.locator('.episode-button-duration').getByText('20秒*',{exact:true}).waitFor();
  assert.equal(await page.locator('.episode-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length),2);
  assert.deepEqual(await card.evaluate(el=>[el.getBoundingClientRect().height,getComputedStyle(el).padding,getComputedStyle(el).gap]),[48,'8px 12px','8px']);
  await card.focus();await page.keyboard.press('Enter');
  assert(new URL(page.url()).hash.includes('section=publication&video='), '作品按钮仍进入发布详情');
  const detail=page.getByRole('region',{name:'作品成片与发布'});
  const tabs=detail.getByRole('navigation',{name:'成片与发布子页'});
  const directoryTab=tabs.getByRole('button',{name:'成片目录',exact:true});
  const releaseTab=tabs.getByRole('button',{name:'发布资料',exact:true});
  const historyTab=tabs.getByRole('button',{name:'发布记录',exact:true});
  const files=detail.getByRole('region',{name:'成片目录',exact:true});
  const history=detail.getByRole('region',{name:'发布记录',exact:true});
  const platforms=detail.getByRole('navigation',{name:'发布平台',exact:true});
  const douyin=platforms.getByRole('button',{name:'抖音',exact:true});
  const xiaohongshu=platforms.getByRole('button',{name:'小红书',exact:true});
  const materialSelect=detail.getByRole('combobox',{name:'选择发布资料'});
  const releaseTitle=detail.getByRole('region',{name:'标题',exact:true}).getByRole('paragraph');
  const textArea=detail.getByRole('region',{name:'发布文字资料'});
  const suggestedAt=textArea.getByRole('region',{name:'建议发布时间',exact:true});
  const executor=textArea.getByRole('region',{name:'发布执行',exact:true});
  await files.waitFor();
  assert.equal(await directoryTab.getAttribute('aria-current'),'page');
  assert.equal(await history.count(),0);
  assert.equal(await detail.getByRole('region',{name:'本次成片'}).count(),0);
  assert.equal(await platforms.count(),0);
  const directoryUrl=page.url();
  assert.deepEqual(await tabs.getByRole('button').allTextContents(),['成片目录','发布资料','发布记录']);
  await releaseTab.focus();await page.keyboard.press('Enter');
  await platforms.waitFor();
  assert.equal(await releaseTab.getAttribute('aria-current'),'page');
  assert.equal(await files.count(),0);
  assert.equal(await history.count(),0);
  assert.match(new URL(page.url()).hash,/&publicationTab=release$/);
  const releaseUrl=page.url();
  await page.goBack();await files.waitFor();
  assert.equal(page.url(),directoryUrl);
  await page.goForward();await platforms.waitFor();
  assert.equal(page.url(),releaseUrl);
  await page.reload();await platforms.waitFor();
  assert.equal(await releaseTab.getAttribute('aria-current'),'page');
  assert.equal(await files.count(),0);
  assert.deepEqual(await platforms.getByRole('button').allTextContents(),['抖音','小红书']);
  assert.equal(await xiaohongshu.getAttribute('aria-current'),'page');
  assert.equal(await materialSelect.count(),0);
  await douyin.focus();await page.keyboard.press('Enter');
  assert.equal(await douyin.getAttribute('aria-current'),'page');
  assert.equal(await releaseTitle.innerText(),fixture.detail.materials[0].fields['标题']);
  assert.ok((await suggestedAt.getByRole('paragraph').innerText()).startsWith(fixture.detail.materials[0].fields['建议发布时间']));
  assert.equal(await executor.getByRole('paragraph').innerText(),fixture.detail.materials[0].fields['发布执行']);
  await xiaohongshu.click();
  assert.equal(await releaseTitle.innerText(),fixture.detail.materials[1].fields['标题']);
  assert.deepEqual(await textArea.getByRole('heading',{level:2}).allTextContents(),['标题','正文','话题','建议发布时间','发布执行']);
  assert.equal(await suggestedAt.getByRole('paragraph').innerText(),`${fixture.detail.materials[1].fields['建议发布时间']}（具体发布安排以确认结果为准）`);
  assert.equal(await executor.getByRole('paragraph').innerText(),fixture.detail.materials[1].fields['发布执行']);
  assert.equal(await detail.getByText('已有发布记录引用此资料',{exact:true}).count(),0);
  assert.equal(await detail.getByText(/^建议发布时间：|^发布执行：/).count(),0);
  assert.equal(await tabs.evaluate(el=>[...el.querySelectorAll('button')].every(button=>
   button.getBoundingClientRect().right<=el.getBoundingClientRect().right+1)),true);
  const infoTabs=detail.getByRole('navigation',{name:'发布信息分类'});
  const mediaTabs=detail.getByRole('navigation',{name:'发布媒体分类'});
  const basicTab=infoTabs.getByRole('button',{name:'基础信息',exact:true});
  const productTab=infoTabs.getByRole('button',{name:'挂品信息',exact:true});
  const landscapeTab=mediaTabs.getByRole('button',{name:'封面（横版）',exact:true});
  const portraitTab=mediaTabs.getByRole('button',{name:'封面（竖版）',exact:true});
  const videoTab=mediaTabs.getByRole('button',{name:'本次视频',exact:true});
  assert.equal(await basicTab.getAttribute('aria-current'),'page');
  assert.equal(await landscapeTab.getAttribute('aria-current'),'page');
  assert.equal(await detail.getByRole('region',{name:'竖版封面',exact:true}).count(),0);
  assert.equal(await detail.getByRole('region',{name:'挂品信息',exact:true}).count(),0);
  const layout=await detail.evaluate(el=>{
   const left=el.querySelector('[aria-label="发布文字资料"]').getBoundingClientRect();
   const right=el.querySelector('[aria-label="发布媒体"]').getBoundingClientRect();
   const host=el.querySelector('.chloe-publication-preparation').getBoundingClientRect();
   return {ratio:left.width/(left.width+right.width), separated:left.right<right.left,
    aligned:left.top===right.top, fits:right.right<=host.right+1};
  });
  assert.ok(Math.abs(layout.ratio-.4)<.005 && layout.separated && layout.aligned && layout.fits,JSON.stringify(layout));
  const matchColumnHeights=async()=>{
   const boxes=await detail.evaluate(el=>{
    const left=el.querySelector('[aria-label="发布文字资料"]').getBoundingClientRect();
    const right=el.querySelector('[aria-label="发布媒体"]').getBoundingClientRect();
    const card=el.querySelector('.chloe-publication-preview .asset-media-card').getBoundingClientRect();
    return {left:left.height,right:right.height,bottomDelta:Math.abs(card.bottom-right.bottom)};
   });
   assert.ok(Math.abs(boxes.left-boxes.right)<1 && boxes.bottomDelta<1,JSON.stringify(boxes));
   return boxes.left;
  };
  const basicHeight=await matchColumnHeights();
  for(const field of ['标题','正文','话题']){
   const copy=detail.getByRole('region',{name:field,exact:true}).getByRole('button',{name:'复制'+field,exact:true});
   assert.equal(await copy.innerText(),'复制');
   assert.deepEqual(await copy.evaluate(el=>[getComputedStyle(el).fontSize,getComputedStyle(el).textDecorationLine,getComputedStyle(el).borderTopWidth]),['13px','underline','0px']);
   await copy.click();
   assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replaceAll('\r\n','\n'),fixture.detail.materials[1].fields[field]);
  }
  await productTab.focus();await page.keyboard.press('Enter');
  assert.equal(await productTab.getAttribute('aria-current'),'page');
  assert.equal(await landscapeTab.getAttribute('aria-current'),'page');
  assert.equal(await detail.getByRole('region',{name:'正文',exact:true}).count(),0);
  assert.equal(await suggestedAt.count(),0);
  assert.equal(await executor.count(),0);
  await page.getByRole('button',{name:'复制挂品链接',exact:true}).click();
  assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replaceAll('\r\n','\n'),fixture.detail.materials[1].fields['挂品链接']);
  await page.getByRole('button',{name:'复制挂品信息',exact:true}).click();
  assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replaceAll('\r\n','\n'),'商品：示例上衣\n款式或SKU：蓝色 M码\n挂品链接：https://example.com/product?id=1&sku=blue');
  const mediaArea=detail.getByRole('region',{name:'发布媒体'});
  const previewCard=mediaArea.locator('.asset-media-card');
  const dimensions=mediaArea.locator('.chloe-publication-dimensions');
  const productHeight=await matchColumnHeights();
  assert.ok(Math.abs(productHeight-basicHeight)>1,'changing left tabs changes the reference height');
  const firstCard=await previewCard.boundingBox();
  for(const [tab,value] of [[landscapeTab,'200 × 150 · 4:3'],[portraitTab,'120 × 160 · 3:4'],[videoTab,'320 × 180 · 16:9']]){
   await tab.click();
   assert.equal(await dimensions.locator('.field-label').innerText(),'尺寸和比例');
   assert.ok((await dimensions.innerText()).endsWith(value));
   assert.ok((await dimensions.boundingBox()).y < (await previewCard.boundingBox()).y);
   assert.equal(await previewCard.locator('.asset-media-preview-caption').count(),0);
   assert.equal(await productTab.getAttribute('aria-current'),'page');
   assert.equal(await mediaArea.getByRole('button',{name:/^下载/}).count(),0);
   const bounds=await previewCard.boundingBox();
   assert.deepEqual([bounds.width,bounds.height],[firstCard.width,firstCard.height]);
   assert.equal(await matchColumnHeights(),productHeight);
  }
  const inCardVideo=previewCard.locator('video');
  assert.equal(await inCardVideo.getAttribute('controlslist'),'nodownload');
  const fittedVideo=await inCardVideo.evaluate(el=>({
   height:el.getBoundingClientRect().height,frame:el.parentElement.getBoundingClientRect().height,
   objectFit:getComputedStyle(el).objectFit,
  }));
  assert.ok(fittedVideo.height>0 && Math.abs(fittedVideo.height-fittedVideo.frame)<1);
  assert.equal(fittedVideo.objectFit,'contain');
  await basicTab.click();
  assert.equal(await matchColumnHeights(),basicHeight);
  assert.ok(Math.abs((await previewCard.boundingBox()).height-firstCard.height)>1);
  await directoryTab.click();
  await files.waitFor();
  assert.equal(page.url(),directoryUrl);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  const table=files.getByRole('table',{name:'成片文件',exact:true});
  assert.equal(await files.locator('details').count(),0);
  assert.equal(await files.getByText('这里可查看目录文件',{exact:false}).count(),0);
  assert.equal(await table.locator('tbody tr').count(),fixture.detail.finals.length);
  assert.deepEqual(await table.getByRole('columnheader').allTextContents(),['文件时间','文件名','文件类型','分辨率与比例','时长','操作']);
  const fileRows=table.locator('tbody tr');
  assert.equal(await table.getByRole('button',{name:'重命名',exact:true}).evaluateAll(buttons=>
   buttons.every(button=>Math.abs(button.getBoundingClientRect().right-button.parentElement.getBoundingClientRect().right)<2)),true);
  assert.equal(await fileRows.first().locator('time').getAttribute('datetime'),fixture.detail.finals[0].fileTime);
  assert.match(await fileRows.first().locator('time').innerText(),/\d{4}.*\d{2}:\d{2}:\d{2}/);
  assert.equal(await fileRows.nth(0).getByRole('cell').nth(1).innerText(),fixture.detail.finals[0].name.replace(/\.webm$/,''));
  assert.equal(await fileRows.nth(0).getByRole('cell').nth(2).innerText(),'.webm');
  assert.equal(await fileRows.nth(0).getByRole('cell').nth(3).innerText(),'1920 × 1088 · 16:9');
  assert.equal(await fileRows.nth(1).getByRole('cell').nth(3).innerText(),'1088 × 1920 · 9:16');
  assert.equal(await fileRows.nth(0).getByRole('cell').nth(4).innerText(),'8 秒');
  assert.equal(await fileRows.nth(1).getByRole('cell').nth(4).innerText(),'12.35 秒');
  assert.equal(await fileRows.nth(2).getByRole('cell',{name:'—',exact:true}).count(),2);
  assert.ok(await table.evaluate(el=>{
   const box=el.getBoundingClientRect();
   return Math.abs(box.width-el.closest('section').getBoundingClientRect().width)<2;
  }));
  const alignment=await table.evaluate(el=>{
   const row=el.querySelector('tbody tr'),cell=row.cells[1],actions=row.cells[5].querySelector('.chloe-publication-file-actions');
   const buttons=actions.querySelectorAll('button'),left=buttons[0].getBoundingClientRect(),right=buttons[buttons.length-1].getBoundingClientRect(),box=actions.getBoundingClientRect();
   return {vertical:getComputedStyle(cell).verticalAlign,align:getComputedStyle(cell).textAlign,
    centered:Math.abs((left.left+right.right)/2-(box.left+box.right)/2)<2,oneLine:left.top===right.top,
    containerWidth:box.width,buttonWidths:[...buttons].map(button=>button.getBoundingClientRect().width)};
  });
  assert.ok(alignment.vertical==='middle' && alignment.align==='left' && alignment.centered && alignment.oneLine,JSON.stringify(alignment));
  const removeRow=table.getByRole('row').filter({has:page.getByText('未引用成片',{exact:true})});
  const buttonStyles=await removeRow.getByRole('cell').nth(5).locator('button').evaluateAll(buttons=>buttons.map(button=>{const s=getComputedStyle(button);return {font:s.fontSize,height:button.getBoundingClientRect().height};}));
  assert(buttonStyles.every(style=>style.font==='14px' && style.height===buttonStyles[0].height));
  assert(await removeRow.getByRole('button',{name:'删除',exact:true}).evaluate(button=>button.classList.contains('danger-button')));
  await removeRow.getByRole('button',{name:'删除',exact:true}).click();
  assert(await page.getByRole('button',{name:'确认删除',exact:true}).evaluate(button=>button.classList.contains('danger-button')));
  await page.getByRole('dialog',{name:'删除成片',exact:true}).getByRole('button',{name:'取消',exact:true}).click();
  assert.deepEqual(writes,[]);
  await removeRow.getByRole('button',{name:'删除',exact:true}).click();
  await page.getByRole('dialog',{name:'删除成片',exact:true}).getByRole('button',{name:'确认删除',exact:true}).click();
  await page.getByText('隔离删除失败，请重试',{exact:true}).waitFor();
  assert.equal(await removeRow.count(),1);failDelete=false;
  await page.getByRole('dialog',{name:'删除成片',exact:true}).getByRole('button',{name:'确认删除',exact:true}).click();
  await removeRow.waitFor({state:'hidden'});
  assert.equal(await page.getByRole('dialog').count(),0);
  const actionsCell=fileRows.first().getByRole('cell').nth(5);
  const idleBounds=await actionsCell.boundingBox();
  const fileDownload=page.waitForEvent('download');
  pendingDownload=Promise.withResolvers();
  let busyLayout;
  try {
   await actionsCell.getByRole('button',{name:'下载',exact:true}).click();
   const preparing=actionsCell.getByRole('button',{name:'正在准备…',exact:true});
   await preparing.waitFor();
   assert.equal(await preparing.getAttribute('aria-busy'),'true');
   busyLayout=await actionsCell.evaluate((cell,idleHeight)=>{
    const {left,right,height}=cell.getBoundingClientRect();
    const buttons=[...cell.querySelectorAll('button')].map(button=>button.getBoundingClientRect());
    return Math.abs(height-idleHeight)<1 && buttons.length===3 && buttons.every(button=>
     Math.abs(button.top-buttons[0].top)<1 && button.left>=left && button.right<=right);
   },idleBounds.height);
  } finally {
   pendingDownload.resolve();
   pendingDownload=undefined;
  }
  const exported=await fileDownload;assert.equal(exported.suggestedFilename(),fixture.detail.finals[0].name);
  assert.deepEqual(await readFile(await exported.path()),video);await exported.delete();
  assert.equal(busyLayout,true,`${width}px 下载准备中三个操作同排且行高不变`);
  await page.getByRole('button',{name:'预览成片',exact:true}).first().click();
  const dialog=page.getByRole('dialog');await dialog.waitFor();
  assert.equal(await dialog.locator('.file-action-links').count(),0);
  assert.equal(await dialog.getByRole('button',{name:'下载',exact:true}).count(),0);
  assert.equal(await dialog.getByRole('link',{name:/查看/}).count(),0);
  await dialog.locator('video').evaluate(el=>el.play());
  await page.waitForFunction(()=>document.querySelector('dialog video')?.currentTime>0);
  await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  assert.equal(await page.getByRole('dialog').count(),0);
  const uploadButton=files.getByRole('button',{name:'上传',exact:true});
  assert.ok(await uploadButton.evaluate(button=>{
   const header=button.parentElement,heading=header.querySelector('h2');
   const a=button.getBoundingClientRect(),b=header.getBoundingClientRect(),c=heading.getBoundingClientRect();
   return Math.abs(a.right-b.right)<2 && a.top<c.bottom && a.bottom>c.top;
  }));
  await uploadButton.click();
  const uploadDialog=page.getByRole('dialog',{name:'上传成片',exact:true});
  const submit=uploadDialog.getByRole('button',{name:'上传',exact:true});
  assert.equal(await uploadDialog.getByRole('button',{name:'取消',exact:true}).evaluate(button=>{
   const group=button.parentElement;
   return Math.abs(button.getBoundingClientRect().right-group.getBoundingClientRect().right)<2
     && group.firstElementChild.getBoundingClientRect().top===button.getBoundingClientRect().top;
  }),true,'上传和取消同排右对齐');
  assert.equal(await submit.isDisabled(),true);
  assert.equal(await uploadDialog.getByText('未选择文件',{exact:true}).isVisible(),true);
  const chooseVideo=page.waitForEvent('filechooser');
  await uploadDialog.getByRole('button',{name:'选择视频',exact:true}).click();
  await (await chooseVideo).setFiles({name:uploaded.name,mimeType:'video/webm',buffer:video});
  assert.equal(await uploadDialog.getByText(uploaded.name,{exact:true}).isVisible(),true);
  assert.equal(await submit.isEnabled(),true);
  await submit.click();
  await uploadDialog.waitFor({state:'hidden'});
  const newRow=table.locator('tbody tr').first();
  assert.equal(await newRow.getByRole('cell').nth(1).innerText(),'最新上传');
  await newRow.getByRole('button',{name:'重命名',exact:true}).click();
  const nameField=newRow.getByRole('textbox',{name:'新文件名',exact:true});
  assert.equal(await nameField.inputValue(),'最新上传');
  assert.equal(await nameField.evaluate(el=>el.selectionStart===0 && el.selectionEnd===el.value.length),true);
  await nameField.fill('未提交');
  await nameField.press('Escape');
  assert.equal(await nameField.count(),0);
  assert.equal(writes.length,3);
  await newRow.getByRole('button',{name:'重命名',exact:true}).click();
  await nameField.fill('同名');
  await nameField.press('Enter');
  await newRow.getByRole('alert').getByText('已有同名成片，请换一个文件名',{exact:true}).waitFor();
  assert.equal(await nameField.inputValue(),'同名');
  await nameField.fill('新文件名');
  await newRow.getByRole('button',{name:'保存文件名',exact:true}).click();
  await newRow.getByText('新文件名',{exact:true}).waitFor();
  assert.equal(await newRow.getByRole('cell').nth(2).innerText(),'.webm');
  assert.equal(await page.getByRole('dialog').count(),0);
  await releaseTab.click();
  await platforms.waitFor();
  for(const [tab,label,width] of [[landscapeTab,'横版封面',200],[portraitTab,'竖版封面',120]]){
   await tab.click();
   const imageButton=page.getByRole('region',{name:label,exact:true}).locator('button.cover');
   await imageButton.click({button:label==='横版封面'?'right':'left'});
   const imagePreview=page.getByRole('dialog',{name:label});
   await imagePreview.waitFor();
   await imagePreview.getByRole('button',{name:'退出全屏看图'}).waitFor();
   await page.waitForFunction(width=>document.querySelector('dialog img')?.naturalWidth===width,width);
   await page.keyboard.press('Escape');
   await imagePreview.waitFor({state:'hidden'});
  }
  await videoTab.click();
  const player=previewCard.locator('.cover video');await player.evaluate(el=>el.play());
  await page.waitForFunction(()=>document.querySelector('.chloe-publication-preview video')?.currentTime>0);
  await player.click({button:'right',position:{x:20,y:20}});
  const fullscreenFilm=page.getByRole('dialog',{name:'本次视频'});
  await fullscreenFilm.waitFor();
  const fullscreenPlayer=fullscreenFilm.locator('video');
  assert.equal(await player.evaluate(video=>video.paused),true);
  assert.equal(await fullscreenPlayer.getAttribute('controlslist'),'nodownload');
  await fullscreenPlayer.evaluate(video=>video.play());
  const fullscreenVideo=await fullscreenPlayer.elementHandle();
  await page.keyboard.press('Escape');
  await fullscreenFilm.waitFor({state:'hidden'});
  assert.equal(await fullscreenVideo.evaluate(video=>video.paused),true);
  await landscapeTab.click();
  assert.equal(await player.count(),0);
  await historyTab.click();await history.waitFor();
  assert.equal(await historyTab.getAttribute('aria-current'),'page');
  assert.match(new URL(page.url()).hash,/&publicationTab=history$/);
  await page.reload();
  await history.getByRole('heading',{name:'P001 · 待提交',exact:true}).waitFor();
  await history.getByRole('heading',{name:'P002 · 已发布',exact:true}).waitFor();
  assert.equal(await history.getByRole('link',{name:'打开已发布作品'}).getAttribute('href'),'https://example.com/post/002');
  assert.equal(await platforms.count(),0);
  assert.equal(await mediaArea.count(),0);
  assert.equal(await files.count(),0);
  await history.getByRole('button',{name:'查看 Q001 发布资料',exact:true}).click();
  await platforms.waitFor();
  assert.equal(await releaseTab.getAttribute('aria-current'),'page');
  assert.equal(await history.count(),0);
  assert.equal(await douyin.getAttribute('aria-current'),'page');
  await page.getByRole('button',{name:'复制标题',exact:true}).click();
  assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),fixture.detail.materials[0].fields['标题']);
  await page.waitForFunction(()=>document.querySelector('.asset-media-card img')?.naturalWidth===160);
  await videoTab.click();
  assert.equal(await player.getAttribute('aria-label'),'最终成片.webm');
  await player.evaluate(el=>el.play());
  await directoryTab.click();
  await files.waitFor();
  assert.equal(await player.count(),0);
  await releaseTab.click();
  await platforms.waitFor();
  assert.equal(await basicTab.getAttribute('aria-current'),'page');
  assert.equal(await landscapeTab.getAttribute('aria-current'),'page');
  assert.equal(await player.count(),0);
  await videoTab.click();
  assert.equal(await player.getAttribute('aria-label'),'最终成片.webm');
  assert.equal(await player.evaluate(el=>el.paused),true);
  await landscapeTab.click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  if(process.env.CHLOE_UI_SCREENSHOT && width===1366){await page.getByRole('button',{name:'关闭提示',exact:true}).evaluateAll(buttons=>buttons.forEach(button=>button.click()));await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:process.env.CHLOE_UI_SCREENSHOT,fullPage:true});}
  missingPortrait=true;await page.reload();
  await previewCard.waitFor();
  const loadedHeight=(await previewCard.boundingBox()).height;
  const loadedColumnHeight=await matchColumnHeights();
  await portraitTab.click();
  await page.getByText('尚未准备竖版封面。',{exact:true}).waitFor();
  assert.ok((await dimensions.innerText()).endsWith('—'));
  await previewCard.click({button:'right'});
  assert.equal(await page.getByRole('dialog').count(),0);
  assert.equal((await previewCard.boundingBox()).height,loadedHeight);
  assert.equal(await matchColumnHeights(),loadedColumnHeight);
  assert.equal(await mediaArea.getByRole('button',{name:/^下载/}).count(),0);
  missingPortrait=false;
  const [firstMaterial, secondMaterial]=fixture.detail.materials;
  materialsOverride=[firstMaterial];await page.reload();await platforms.waitFor();
  assert.deepEqual(await platforms.getByRole('button').allTextContents(),['抖音']);
  assert.equal(await douyin.getAttribute('aria-current'),'page');
  assert.equal(await materialSelect.count(),0);
  materialsOverride=[firstMaterial,secondMaterial,
   {...secondMaterial,id:'Q003',fields:{...secondMaterial.fields,'平台':'快手','标题':'快手发布标题'}},
   {...firstMaterial,id:'Q004',fields:{...firstMaterial.fields,'账号':'另一个抖音账号','标题':'另一个抖音标题'}},
   {...firstMaterial,id:'Q005',fields:{...firstMaterial.fields,'平台':'待确定'}}];
  await page.reload();await platforms.waitFor();
  assert.deepEqual(await platforms.getByRole('button').allTextContents(),['抖音','小红书','快手']);
  assert.equal(await douyin.getAttribute('aria-current'),'page');
  assert.equal(await releaseTitle.innerText(),'另一个抖音标题');
  assert.match(await materialSelect.innerText(),/Q004 · 另一个抖音账号/);
  await materialSelect.click();
  const choices=detail.getByRole('listbox',{name:'选择发布资料'});
  assert.equal(await choices.getByRole('option').count(),2);
  await choices.getByRole('option',{name:'Q001 · 示例账号',exact:true}).click();
  assert.equal(await releaseTitle.innerText(),firstMaterial.fields['标题']);
  assert.equal(await douyin.getAttribute('aria-current'),'page');
  await platforms.getByRole('button',{name:'快手',exact:true}).click();
  assert.equal(await releaseTitle.innerText(),'快手发布标题');
  assert.equal(await materialSelect.count(),0);
  materialsOverride=undefined;noMaterial=true;await page.reload();
  await detail.getByText('暂无发布准备资料。',{exact:true}).waitFor();
  assert.equal(await platforms.count(),0);
  assert.equal(await files.count(),0);
  assert.equal(await page.getByRole('button',{name:'下载成片',exact:true}).count(),0);
  await historyTab.click();
  await history.getByText('暂无发布安排或结果。',{exact:true}).waitFor();
  await directoryTab.click();
  assert.equal(await page.getByRole('cell',{name:'暂无成片',exact:true}).getAttribute('colspan'),'6');
  await releaseTab.click();
  failDetail=true;await page.reload();await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  failDetail=false;noMaterial=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await videoTab.click();
  await mediaArea.getByRole('region',{name:'本次视频',exact:true}).locator('video').waitFor();
  await page.getByRole('button',{name:'成片与发布',exact:true}).click();
  await cards.first().waitFor();
  assert.equal(await tabs.count(),0);
  empty=true;await page.reload();
  await page.getByText('暂无视频项目。',{exact:false}).waitFor();
  assert.deepEqual(await page.locator('[aria-label="作品发布统计"] > span').allTextContents(), ['共 0 部','制作中 0 部','待发布 0 部','已发布 0 部']);
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);assert.deepEqual(writes,[decodeURIComponent(removable.url),decodeURIComponent(removable.url),uploadPath,decodeURIComponent(uploaded.url),decodeURIComponent(uploaded.url)]);
  await context.close();
 }
 console.log('Chloe publication: real adapter fixtures, copy, original downloads, playback, cover preview, switching, empty/error/retry and three desktop widths passed.');
}finally{await browser.close();await server.close();}
