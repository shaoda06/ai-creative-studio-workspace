import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {mkdtemp,readFile} from 'node:fs/promises';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {createServer}=await import(require.resolve('vite'));
const react=(await import(require.resolve('@vitejs/plugin-react'))).default;
const tool=fileURLToPath(new URL('../',import.meta.url));
const fixture=JSON.parse(execFileSync(tool+'.venv/bin/python',['-c',`
import base64,json
from pathlib import Path
from PIL import Image
from tests.test_chloe_resource_library import ChloeResourceLibraryTests
from backend.chloe_resource_library import catalog,detail_data
from chloe_resources import import_media
x=ChloeResourceLibraryTests();x.setUp()
try:
 for i in range(9):
  p=x.base/(('超长文件名用于核对桌面展示边界-'*7 if i==0 else 'sample-')+str(i)+'.png')
  Image.new('RGB',(30,40),(i,30,90)).save(p);import_media(x.root,p,'extra-'+str(i))
 items,owners=catalog(x.root,x.api)
 details={v['key']:detail_data(x.root,x.api,v['owner'],v['resource_id'],v['version']) for v in items}
 docs={p:x.client.get(x.api+'/resource-library/document',params={'path':p}).json() for d in details.values() for p in ([d['producer_file']] if d['producer_file'] else [])+[u['path'] for u in d['uses']]}
 files={v['file']:base64.b64encode((x.root/v['file']).read_bytes()).decode() for v in items}
 print(json.dumps({'items':items,'owners':owners,'details':details,'docs':docs,'files':files,'api':x.api}))
finally:x.doCleanups()
`],{cwd:tool,encoding:'utf8',env:{...process.env,PATH:'/opt/homebrew/bin:'+process.env.PATH}}));
const version=JSON.parse(await readFile(tool+'frontend/package.json','utf8')).version;
const output=await mkdtemp('/tmp/chloe-resources-ui-');
const server=await createServer({configFile:false,root:tool+'frontend',plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 for(const [width,height] of [[1280,640],[1366,768],[1920,1080]]){
  const page=await browser.newPage({viewport:{width,height},acceptDownloads:true});
  const errors=[],unexpected=[];let fail=false;
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   const url=new URL(route.request().url()),path=decodeURIComponent(url.pathname),params=url.searchParams;
   if(route.request().method()!=='GET')unexpected.push(route.request().method()+' '+path);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'test',name:'隔离项目',view:'chloe-commerce',projects:[]}]});
   if(path===fixture.api+'/resource-library'){
    if(fail)return route.fulfill({status:503,json:{detail:'隔离读取错误'}});
    const q=(params.get('q')||'').toLowerCase(),kind=params.get('kind'),owner=params.get('owner');
    const items=fixture.items.filter(v=>(!kind||v.kind===kind)&&(!owner||v.owner===owner)&&(!q||(v.name+' '+v.title+' '+v.resource_id+'@'+v.version).toLowerCase().includes(q)));
    const size=12,current=Math.min(Number(params.get('page')||1),Math.max(1,Math.ceil(items.length/size)));
    return route.fulfill({json:{items:items.slice((current-1)*size,current*size),total:items.length,page:current,page_size:size,owners:fixture.owners}});
   }
   if(path===fixture.api+'/resource-library/detail')return route.fulfill({json:fixture.details[params.get('owner')+'/'+params.get('resource_id')+'@'+params.get('version')]});
   if(path===fixture.api+'/resource-library/document')return route.fulfill({json:fixture.docs[params.get('path')]});
   if(path.startsWith(fixture.api+'/resource-library/files/')){
    const key=path.split('/files/')[1],file=fixture.files[key];
    if(file)return route.fulfill({body:Buffer.from(file,'base64'),contentType:key.endsWith('.png')?'image/png':key.endsWith('.wav')?'audio/wav':'video/webm',headers:params.has('download')?{'content-disposition':'attachment; filename="sample.png"'}:{}});
   }
   unexpected.push(path);return route.fulfill({status:404,json:{detail:'unexpected isolated request'}});
  });
  const url=server.resolvedUrls.local[0]+'#/spaces/test/contexts/'+encodeURIComponent('隔离甲项目')+'?section=resources';
  await page.goto(url);
  await page.locator('.chloe-resource-item').first().waitFor();
  assert.equal(await page.locator('.chloe-resource-item').count(),12);
  await page.getByRole('button',{name:'下一页',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.chloe-resource-item').length===2);
  await page.getByRole('button',{name:'图片',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.chloe-resource-item').length===12);
  const cells=await page.locator('.chloe-resource-item').all();
  const boxes=await Promise.all(cells.slice(0,3).map(el=>el.boundingBox()));
  assert.ok(boxes.every(b=>Math.abs(b.y-boxes[0].y)<1),'three image columns');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:output+'/'+width+'-images.png',fullPage:true});
  await page.getByRole('combobox',{name:'资源归属'}).click();await page.getByRole('option',{name:'共用资源',exact:true}).click();
  await page.getByRole('searchbox',{name:'搜索资源'}).fill('UPSCALED');
  await page.waitForFunction(()=>document.querySelectorAll('.chloe-resource-item').length===1);
  const card=page.locator('.chloe-resource-item');await card.locator('.cover').click();
  await page.getByRole('dialog').waitFor();assert.equal(await page.locator('dialog img').count(),1);await page.keyboard.press('Escape');
  const download=page.waitForEvent('download');await card.getByRole('link',{name:'下载',exact:true}).click();await download;
  await card.getByRole('button',{name:'详情',exact:true}).click();
  await page.getByRole('heading',{name:'来源与制作记录',exact:true}).waitFor();
  await page.getByRole('button',{name:'查看生成／处理记录',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('dialog[open]').length===2);await page.keyboard.press('Escape');
  await page.getByRole('combobox',{name:'资源版本'}).click();await page.getByRole('option',{name:/V001 · portrait.png/}).click();
  await page.getByRole('heading',{name:'已记录的关联与引用（4）',exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:'进入对应资产／作品'}).count(),4);
  assert.ok((await page.getByRole('link',{name:'进入对应资产／作品'}).first().getAttribute('href')).includes('/contexts/'));
  await page.keyboard.press('Escape');
  await page.getByRole('searchbox',{name:'搜索资源'}).fill('');
  await page.getByRole('combobox',{name:'资源归属'}).click();await page.getByRole('option',{name:'全部归属',exact:true}).click();
  await page.getByRole('button',{name:'视频',exact:true}).click();
  await page.getByRole('button',{name:'播放 video.webm',exact:true}).click();
  await page.locator('dialog video').waitFor();await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'音频',exact:true}).click();
  await page.locator('.audio-reference-card').waitFor();
  const audioBox=await page.locator('.chloe-resource-item').boundingBox(),gridBox=await page.locator('.chloe-resource-grid').boundingBox();assert.equal(audioBox.width,gridBox.width);
  await page.getByRole('button',{name:'播放tone.wav',exact:true}).click();await page.getByRole('button',{name:'暂停tone.wav',exact:true}).waitFor();
  await page.getByRole('searchbox',{name:'搜索资源'}).fill('not found');await page.getByText('暂无符合条件的资源。',{exact:true}).waitFor();
  assert.ok(await page.locator('audio').evaluate(el=>el.paused),'filter stops audio');
  fail=true;await page.reload();await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  fail=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();await page.locator('.chloe-resource-item').first().waitFor();
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);await page.close();
 }
 console.log('Resource library passed: filters, paging, exact versions, previews, lineage, downloads, error retry and three desktop sizes. Screenshots: '+output);
}finally{await browser.close();await server.close();}
