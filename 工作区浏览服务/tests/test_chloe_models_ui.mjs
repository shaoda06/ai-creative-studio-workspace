import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { mkdtemp, readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(require.resolve('vite'));
const react = (await import(require.resolve('@vitejs/plugin-react'))).default;
const tool = fileURLToPath(new URL('../', import.meta.url));
const frontend = tool+'frontend/';
const version = JSON.parse(await readFile(frontend+'package.json', 'utf8')).version;
const sample = JSON.parse(execFileSync(tool+'.venv/bin/python',['-c',`
import base64,json,os,tempfile
from pathlib import Path
from PIL import Image
from backend.chloe_models import model_cards,model_detail
from chloe_init import initialize_workspace,initialize_asset,SKILLS
import sys
sys.path.insert(0,str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media
import project_resources as resources
with tempfile.TemporaryDirectory() as tmp:
 root=initialize_workspace(Path(tmp)/'Chloe Workspace')
 model=initialize_asset(root,'模特','M001','示例模特甲')
 initialize_asset(root,'模特','M002','示例模特乙')
 image=Path(tmp)/'portrait.png'
 Image.new('RGB',(200,300),'#b4d6ca').save(image)
 ref=resources.register(root/'综合资料',image,key='ui-sample',info=resources.facts(image))
 target=resources.local(root/'综合资料',ref['file'])
 path=model/'模特说明.md'
 text=path.read_text().replace('| 来源说明 | 待核实 |','| 来源说明 | 不应显示的来源文字 |')
 start=text.index('## 当前采用')
 end=text.index('\\n\\n',text.index('| ---',start))
 row='\\n| 正面面部 | [共用:'+ref['resource_id']+'@'+ref['version']+'](<'+os.path.relpath(target,model)+'>) | 隔离示例采用 | 2026-11-07T12:00:00+08:00 |'
 path.write_text(text[:end]+row+text[end:])
 def append(heading,row):
  text=path.read_text();start=text.index('## '+heading);end=text.index('\\n\\n',text.index('| ---',start))
  path.write_text(text[:end]+'\\n| '+' | '.join(row)+' |'+text[end:])
 def label(file,rid,version):
  return '[共用:'+rid+'@'+version+'](<'+os.path.relpath(file,model)+'>)'
 first=label(target,ref['resource_id'],ref['version'])
 append('参考版本',['正面面部',first,'用户提供','不适用'])
 for purpose,color,size,key in [('正面面部','#95aabb',(200,300),'face2'),('全身三视图原图','#bbaabb',(600,300),'views'),('全身三视图遮面版','#444444',(600,300),'masked')]:
  source=Path(tmp)/(key+'.png');Image.new('RGB',size,color).save(source)
  result=import_media(root,source,key,resource_id=ref['resource_id'] if key=='face2' else None)
  reference=label(Path(result['absolute_file']),result['resource_id'],result['version'])
  append('参考版本',[purpose,reference,original if key=='masked' else first,'不适用'])
  if key=='views':original=reference
  if key in ('views','masked'):append('当前采用',[purpose,reference,'隔离采用','2026-11-07T12:00:00+08:00'])
 look=initialize_asset(root,'造型','L001','通勤造型')/'造型说明.md'
 text=look.read_text().replace('| 模特编号 | 待确定 |','| 模特编号 | M001 |')
 start=text.index('## 关联资料');end=text.index('\\n\\n',text.index('| ---',start))
 look.write_text(text[:end]+'\\n| 模特 | M001 | [模特](<../../AI模特/M001-示例模特甲/模特说明.md>) | 穿搭人物 |'+text[end:])
 detail=model_detail(root,'M001' ,'/api/workspaces/chloe')
 media={item['media']['url']:base64.b64encode((root/item['media']['key']).read_bytes()).decode() for item in detail['images']}
 print(json.dumps({'cards':model_cards(root,'/api/workspaces/chloe'),'details':[detail,model_detail(root,'M002','/api/workspaces/chloe')],'media':media,'image':base64.b64encode(image.read_bytes()).decode()}))
`],{cwd:tool,encoding:'utf8'}));
const output = await mkdtemp('/private/tmp/chloe-models-');
const server = await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
  const page=await browser.newPage({viewport:{width,height}}), errors=[], unexpected=[];
  let fail=false, long=false;
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   const path=new URL(route.request().url()).pathname;
   if(route.request().method()!=='GET') unexpected.push(path);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'chloe',name:'Chloe AI视频带货',view:'chloe-commerce',projects:[]}]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path==='/api/workspaces/chloe/shared-models') {
    if(fail)return route.fulfill({status:409,json:{detail:'isolated invalid document'}});
    const cards=structuredClone(sample.cards);
    if(long){cards[0].name='LongModelName'.repeat(30);}
    return route.fulfill({json:cards});
   }
   const detail=sample.details.find(item=>path===`/api/workspaces/chloe/shared-models/${item.id}`);
   if(detail)return route.fulfill({json:detail});
   if(sample.media[path])return route.fulfill({body:Buffer.from(sample.media[path],'base64'),contentType:'image/png'});
   if(path===sample.cards[0].media.url)return route.fulfill({body:Buffer.from(sample.image,'base64'),contentType:'image/png'});
   unexpected.push(path);return route.fulfill({status:404,json:{detail:'unexpected'}});
  });
  await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe?section=assets');
  await page.getByRole('heading',{name:'M001 · 示例模特甲',exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('.asset-media-card img')?.naturalWidth===200);
  assert.equal(await page.locator('.asset-media-card').count(),2);
  assert.equal(await page.locator('.asset-media-card img').count(),1);
  await page.getByText('尚未采用正面面部图',{exact:true}).waitFor();
  const placeholder=page.locator('.asset-media-placeholder');
  assert.equal(await placeholder.count(),1);
  const blankBox=await placeholder.boundingBox(), imageBox=await page.locator('.asset-media-card-link').first().locator('.cover').boundingBox();
  assert.equal(blankBox.height,imageBox.height);
  assert.ok(Math.abs(blankBox.width-imageBox.width)<=1);
  assert.equal(await placeholder.getByRole('button').count(),0);

  assert.equal(await page.locator('.page-heading .breadcrumbs').count(),1);
  assert.equal(await page.locator('section[aria-label="共用资产"] > h2').count(),0);
  await page.screenshot({path:output+`/${width}-cards.png`,fullPage:true});
  assert.equal(await page.getByRole('button',{name:'查看详情',exact:true}).count(),0);
  assert.equal(await page.locator('.asset-media-field,.asset-media-footer').count(),0);
  const tabsBox=await page.getByRole('navigation',{name:'共用资产分类',exact:true}).boundingBox();
  const gridBox=await page.locator('.asset-media-grid').boundingBox();
  assert.ok(gridBox.y-tabsBox.y-tabsBox.height>=19);
  const card=page.getByRole('link',{name:'M001 · 示例模特甲',exact:true});
  assert.equal(await card.locator('button,a').count(),0);
  await card.focus(); await page.keyboard.press('Enter');
  await page.getByRole('heading',{name:'人物特征',exact:true}).waitFor();
  const featureTable=page.locator('.prose-field-table table');
  const featureRatio=await featureTable.evaluate(table=>table.querySelector('th').getBoundingClientRect().width/table.getBoundingClientRect().width);
  assert.ok(Math.abs(featureRatio-.4)<.005,'人物特征表格左40%、右60%');
  assert.equal(await page.getByRole('dialog').count(),0);
  assert.match(page.url(),/model=M001/);
  assert.equal(await page.locator('.breadcrumbs [aria-current="page"]').textContent(),'M001 · 示例模特甲');
  assert.equal(await page.getByRole('heading',{name:'基础全身三视图',exact:true}).count(),0);
  assert.equal(await page.getByRole('link',{name:'查看 ↗',exact:true}).count(),0);
  assert.equal(await page.getByRole('link',{name:'下载',exact:true}).count(),0);
  await page.getByRole('navigation',{name:'模特详情分类'}).getByRole('button',{name:'模特图片',exact:true}).click();
  await page.getByRole('heading',{name:'基础全身三视图',exact:true}).waitFor();
  assert.equal(await page.getByRole('heading',{name:'人物特征',exact:true}).count(),0);
  assert.equal(await page.getByRole('navigation',{name:'当前采用三视图'}).locator('[aria-current="page"]').textContent(),'遮面版');
  await page.getByRole('navigation',{name:'当前采用三视图'}).getByRole('button',{name:'原图',exact:true}).click();
  await page.getByRole('region',{name:'基础全身三视图',exact:true}).getByText('参考版本',{exact:true}).click();
  await page.getByRole('navigation',{name:'模特图片用途'}).getByRole('button',{name:'全身三视图原图',exact:true}).click();
  await page.reload();
  await page.getByRole('heading',{name:'基础全身三视图',exact:true}).waitFor();
  assert.match(page.url(),/modelTab=images/);
  assert.match(page.url(),/view=original/);
  assert.match(page.url(),/purpose=/);
  const detailTabs=page.getByRole('navigation',{name:'模特详情分类'});
  assert.deepEqual(await detailTabs.getByRole('button').allTextContents(),['模特信息','模特图片','造型']);
  assert.equal(await page.getByText('不应显示的来源文字',{exact:true}).count(),0);
  assert.equal(await page.getByRole('heading',{name:'资产身份',exact:true}).count(),0);
  const faceColumn=page.getByRole('region',{name:'正面面部图',exact:true});
  const bodyColumn=page.getByRole('region',{name:'基础全身三视图',exact:true});
  const faceBox=await faceColumn.boundingBox(),bodyBox=await bodyColumn.boundingBox();
  assert.ok(faceBox.x+faceBox.width<bodyBox.x && Math.abs(faceBox.y-bodyBox.y)<1,'面部和三视图同页左右排列');
  assert.ok(bodyBox.x+bodyBox.width<=width+1);
  await page.screenshot({path:output+`/${width}-images.png`,fullPage:true});
  const refs=page.locator('section.panel').filter({has:page.getByRole('heading',{name:'参考版本',exact:true})});
  await refs.locator('.asset-media-card').nth(1).waitFor();
  assert.equal(await refs.locator('.asset-media-card').count(),2);
  await refs.locator('.cover').last().click();
  await page.getByRole('dialog').waitFor(); assert.match(page.url(),/ref=/);
  await page.reload(); await page.getByRole('dialog').waitFor();
  assert.equal(await page.getByRole('dialog').locator('img').count(),1);
  await page.keyboard.press('Escape');

  const records=page.locator('.chloe-model-detail > details');
  assert.equal(await records.count(),1);
  assert.equal(await records.getAttribute('open'),null);
  const summary=records.locator(':scope > summary');
  assert.equal(await summary.textContent(),'资料与制作记录');
  assert.equal(await summary.evaluate(el=>getComputedStyle(el).color),await page.locator('body').evaluate(el=>getComputedStyle(el).color));
  await summary.focus(); await page.keyboard.press('Enter');
  await records.locator(':scope > details > summary').first().waitFor();
  assert.deepEqual(await records.locator(':scope > details > summary').allTextContents(),['关联资料','采用依据与时间','采用变更','执行记录']);
  assert.equal(await records.locator(':scope > details[open]').count(),0);
  await page.getByText('执行记录',{exact:true}).click();
  await page.getByText('暂无执行记录。',{exact:true}).waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:output+`/${width}-detail.png`,fullPage:true});
  await detailTabs.getByRole('button',{name:'造型',exact:true}).click();
  await page.getByRole('link',{name:'L001 · 通勤造型',exact:true}).click();
  await page.getByRole('heading',{name:'L001｜通勤造型 造型说明',exact:true}).waitFor();
  assert.match(page.url(),/look=L001/);
  assert.equal(await page.getByRole('dialog').count(),0);
  await page.reload();
  await page.getByRole('link',{name:'返回造型列表',exact:true}).click();
  await page.getByRole('link',{name:'L001 · 通勤造型',exact:true}).waitFor();
  await page.locator('.breadcrumbs').getByRole('link',{name:'AI 模特',exact:true}).click();
  await page.getByRole('link',{name:'M002 · 示例模特乙',exact:true}).click();
  await page.getByRole('heading',{name:'人物特征',exact:true}).waitFor();
  await page.getByRole('navigation',{name:'模特详情分类'}).getByRole('button',{name:'造型',exact:true}).click();
  await page.getByText('暂无该模特的造型资料。',{exact:true}).waitFor();
  await page.locator('.breadcrumbs').getByRole('link',{name:'AI 模特',exact:true}).click();
  await page.getByRole('link',{name:'M001 · 示例模特甲',exact:true}).waitFor();
  for(const oldTab of ['face','body']) {
    await page.goto(server.resolvedUrls.local[0]+`#/spaces/chloe?section=assets&asset=models&model=M001&modelTab=${oldTab}`);
    await page.getByRole('heading',{name:'基础全身三视图',exact:true}).waitFor();
    assert.equal(await page.getByRole('navigation',{name:'模特详情分类'}).locator('[aria-current="page"]').textContent(),'模特图片');
    await page.getByRole('heading',{name:'正面面部图',exact:true}).waitFor();
  }
  await page.locator('.breadcrumbs').getByRole('link',{name:'AI 模特',exact:true}).click();
  long=true;await page.reload();
  await page.getByRole('heading',{name:'M001 · '+'LongModelName'.repeat(30),exact:true}).waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  const titleSize=await page.locator('.asset-media-card h3').first().evaluate(el=>({height:el.getBoundingClientRect().height,line:parseFloat(getComputedStyle(el).lineHeight)}));
  assert.ok(Math.abs(titleSize.height-titleSize.line)<=1);

  for(const element of await page.locator('.asset-media-card').all()){
   const box=await element.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1);
  }
  fail=true;await page.reload();await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  assert.equal(await page.locator('.asset-media-card').count(),0);
  fail=false;long=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.getByRole('heading',{name:'M001 · 示例模特甲',exact:true}).waitFor();
  await page.getByRole('navigation',{name:'共用资产分类',exact:true}).getByRole('button',{name:'服装',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent==='服装');
  assert.equal(await page.locator('.asset-media-card').count(),0);
  await page.getByRole('navigation',{name:'当前位置',exact:true}).getByRole('link',{name:'共用资产',exact:true}).click();
  await page.getByRole('heading',{name:'M001 · 示例模特甲',exact:true}).waitFor();
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await page.close();
 }
 console.log('Chloe model cards passed: document-based fixtures, one card per model, adopted/empty portraits, entry metadata hidden/image preview, breadcrumbs, long content and retry; screenshots '+output);
}finally{await browser.close();await server.close();}
