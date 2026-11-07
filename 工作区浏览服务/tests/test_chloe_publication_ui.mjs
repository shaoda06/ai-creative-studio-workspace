// Actual document adapter output, isolated responses, no real project writes.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { readFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {createServer}=await import(require.resolve('vite'));
const react=(await import(require.resolve('@vitejs/plugin-react'))).default;
const frontend=fileURLToPath(new URL('../frontend/',import.meta.url));
const tool=fileURLToPath(new URL('../',import.meta.url));
const version=JSON.parse(await readFile(frontend+'package.json','utf8')).version;
const fixture=JSON.parse(execFileSync(tool+'.venv/bin/python',['-c',`
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
 x.row[3]='[成片](<成片/第二版成片.webm>)'
 x.row[4]=f'[本视频:{ref["resource_id"]}@{ref["version"]}](<{Path(ref["absolute_file"]).relative_to(x.project).as_posix()}>)'
 x.row[0]='Q002';x.row[1]='小红书';x.row[6]='另一平台的长标题'+('细节展示'*18)
 x.append(path,'发布资料',x.row)
 detail=publication.detail(x.root,x.project.name,x.api)
 images={c['media']['url']:base64.b64encode((x.root/c['media']['key']).read_bytes()).decode() for m in detail['materials'] for c in m['covers']}
 print(json.dumps({'list':publication.listing(x.root,x.api),'detail':detail,'images':images}))
finally:x.doCleanups()
`],{cwd:tool,encoding:'utf8'}));
const video=await readFile(frontend+'public/component-samples/video.webm');
const images=new Map(Object.entries(fixture.images).map(([url,bytes])=>[decodeURIComponent(url),Buffer.from(bytes,'base64')]));
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true});
const downloads=await mkdtemp(join(tmpdir(),'chloe-publication-downloads-'));
try {
 for(const [width,height] of [[1280,640],[1366,768],[1920,1080]]){
  const context=await browser.newContext({viewport:{width,height},permissions:['clipboard-read','clipboard-write']});
  const page=await context.newPage();page.setDefaultTimeout(10000);
  const errors=[],unexpected=[],writes=[];let failList=true, failDetail=false, empty=false, noMaterial=false, missingPortrait=false;
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   const request=route.request(),path=decodeURIComponent(new URL(request.url()).pathname);
   if(request.method()!=='GET')writes.push(path);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'chloe',name:'Chloe AI视频带货',view:'chloe-commerce',projects:[]}]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path.endsWith('/publication-videos'))return failList?route.fulfill({status:409,body:'隔离列表错误'}):route.fulfill({json:empty?[]:fixture.list});
   if(path.endsWith('/publication-videos/'+fixture.detail.project))return failDetail?route.fulfill({status:409,body:'隔离资料错误'}):route.fulfill({json:noMaterial?{...fixture.detail,materials:[],finals:[]}:missingPortrait?{...fixture.detail,materials:fixture.detail.materials.map(m=>({...m,covers:m.covers.map((c,i)=>i===1?{...c,media:null}:c)}))}:fixture.detail});
   if(path.endsWith('.webm'))return route.fulfill({contentType:'video/webm',body:video,headers:{'Content-Disposition':"inline; filename*=utf-8''"+encodeURIComponent('最终成片.webm')}});
   if(path.endsWith('.png'))return route.fulfill({contentType:'image/png',body:images.get(path)});
   unexpected.push(path);return route.fulfill({status:404,body:'unexpected isolated request'});
  });
  await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe?section=publication');
  await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  failList=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.locator(`[data-episode="${fixture.detail.project}"]`).click();
  await page.getByRole('region',{name:'视频发布资料'}).waitFor();
  for(const field of ['正文','话题','挂品链接']){
   await page.getByRole('button',{name:'复制'+field,exact:true}).click();
   assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),fixture.detail.materials[1].fields[field]);
  }
  await page.getByRole('button',{name:'复制挂品信息',exact:true}).click();
  assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),'商品：示例上衣\n款式或SKU：蓝色 M码\n挂品链接：https://example.com/product?id=1&sku=blue');
  for(const [label,bytes,filename] of [['下载成片',video,'第二版成片.webm'],...fixture.detail.materials[1].covers.map(c=>['下载'+c.label,images.get(decodeURIComponent(c.media.url)),c.media.name])]){
   const event=page.waitForEvent('download');await page.getByRole('button',{name:label,exact:true}).click();
   const download=await event;if(filename)assert.equal(download.suggestedFilename(),filename);
   const destination=join(downloads,width+'-'+download.suggestedFilename());await download.saveAs(destination);
   assert.deepEqual(await readFile(destination),bytes);await download.delete();
  }
  for(const [label,width] of [['横版封面',200],['竖版封面',120]]){
   await page.getByRole('region',{name:label,exact:true}).locator('button.cover').click();
   await page.getByRole('dialog').waitFor();
   await page.waitForFunction(width=>document.querySelector('dialog img')?.naturalWidth===width,width);
   await page.keyboard.press('Escape');
  }
  const player=page.locator('video');await player.evaluate(el=>el.play());
  await page.waitForFunction(()=>document.querySelector('video')?.currentTime>0);
  await player.evaluate(el=>el.pause());
  await page.getByRole('combobox',{name:'选择发布资料',exact:true}).click();
  await page.getByRole('option',{name:/Q001/}).click();
  await page.getByRole('button',{name:'复制标题',exact:true}).click();
  assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),fixture.detail.materials[0].fields['标题']);
  assert.equal(await page.locator('video').getAttribute('aria-label'),'最终成片.webm');
  await page.waitForFunction(()=>document.querySelector('.asset-media-card img')?.naturalWidth===160);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  if(process.env.CHLOE_UI_SCREENSHOT && width===1366){await page.getByRole('button',{name:'关闭提示',exact:true}).evaluateAll(buttons=>buttons.forEach(button=>button.click()));await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:process.env.CHLOE_UI_SCREENSHOT,fullPage:true});}
  missingPortrait=true;await page.reload();
  await page.getByText('尚未准备竖版封面。',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'下载竖版封面',exact:true}).isDisabled(),true);
  assert.equal(await page.getByRole('button',{name:'下载横版封面',exact:true}).isEnabled(),true);
  missingPortrait=false;noMaterial=true;await page.reload();await page.getByText('成片目录内暂无视频',{exact:false}).waitFor();
  assert.equal(await page.getByRole('button',{name:'下载成片',exact:true}).count(),0);
  failDetail=true;await page.reload();await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  failDetail=false;noMaterial=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.getByRole('button',{name:'下载成片',exact:true}).waitFor();
  empty=true;await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe?section=publication');await page.reload();
  await page.getByText('暂无视频项目。',{exact:false}).waitFor();
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);assert.deepEqual(writes,[]);
  await context.close();
 }
 console.log('Chloe publication: real adapter fixtures, copy, original downloads, playback, cover preview, switching, empty/error/retry and three desktop widths passed.');
}finally{await browser.close();await server.close();await rm(downloads,{recursive:true,force:true});}
