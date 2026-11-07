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
from backend.chloe_clothing import clothing_cards,clothing_detail
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
 for purpose,color,size,key in [('正面面部','#95aabb',(200,300),'face2'),('正面面部','#95aacc',(200,300),'face3'),('正面面部','#95aadd',(200,300),'face4'),('正面面部','#95aaee',(200,300),'face5'),('全身三视图原图','#bbaabb',(600,300),'views'),('全身三视图遮面版','#444444',(600,300),'masked')]:
  source=Path(tmp)/(key+'.png');Image.new('RGB',size,color).save(source)
  result=import_media(root,source,key,resource_id=ref['resource_id'] if key.startswith('face') else None)
  reference=label(Path(result['absolute_file']),result['resource_id'],result['version'])
  append('参考版本',[purpose,reference,original if key=='masked' else first,'不适用'])
  if key=='views':original=reference
  if key in ('views','masked'):append('当前采用',[purpose,reference,'隔离采用','2026-11-07T12:00:00+08:00'])
 look=initialize_asset(root,'造型','L001','通勤造型')/'造型说明.md'
 text=look.read_text().replace('| 模特编号 | 待确定 |','| 模特编号 | M001 |')
 start=text.index('## 关联资料');end=text.index('\\n\\n',text.index('| ---',start))
 look.write_text(text[:end]+'\\n| 模特 | M001 | [模特](<../../AI模特/M001-示例模特甲/模特说明.md>) | 穿搭人物 |'+text[end:])
 path=look
 for index,purpose in enumerate(['全身三视图原图']+['全身三视图遮面版']*5):
  source=Path(tmp)/('look'+str(index)+'.png');Image.new('RGB',(600,300),(50+index*20,90,130)).save(source)
  result=import_media(root,source,'look'+str(index),resource_id=look_resource if index>1 else None)
  if index==1:look_resource=result['resource_id']
  reference=label(Path(result['absolute_file']),result['resource_id'],result['version']).replace(os.path.relpath(Path(result['absolute_file']),model),os.path.relpath(Path(result['absolute_file']),look.parent))
  append('参考版本',[purpose,reference,'用户提供','不适用'])
  if index<=1:append('当前采用',[purpose,reference,'隔离采用','2026-11-07T12:00:00+08:00'])
 append('执行记录',['E001','图片生成','不适用','隔离测试','测试','不适用','隔离测试','未取得','未取得','未取得','准备中','未取得'])
 for slot,color in [('1','#ee9a70'),('2','#336688')]:
  source=Path(tmp)/('clothing'+slot+'.png');Image.new('RGB',(200,300),color).save(source)
  result=import_media(root,source,'clothing'+slot)
  reference=label(Path(result['absolute_file']),result['resource_id'],result['version']).replace(os.path.relpath(Path(result['absolute_file']),model),os.path.relpath(Path(result['absolute_file']),look.parent))
  append('输入记录',['E001',slot,'服装参考','不适用',reference])
 clothing=initialize_asset(root,'服装','O001','示例外套')
 initialize_asset(root,'服装','O002','未选图服装')
 path=clothing/'服装说明.md'
 path.write_text(path.read_text().replace('| 来源说明 | 待核实 |','| 来源说明 | 不显示的服装来源 |'))
 for index,purpose in enumerate(['正面']*5+['背面','细节/纽扣']):
  source=Path(tmp)/('garment'+str(index)+'.png');Image.new('RGB',(240,320),(80+index*15,130,90)).save(source)
  result=import_media(root,source,'garment'+str(index),resource_id=garment_resource if 0<index<5 else None)
  if index==0:garment_resource=result['resource_id']
  reference='[共用:'+result['resource_id']+'@'+result['version']+'](<'+os.path.relpath(result['absolute_file'],clothing)+'>)'
  append('参考版本',[purpose,reference,'用户提供','不适用'])
  if index in (0,5,6):append('当前采用',[purpose,reference,'隔离采用','2026-11-07T12:00:00+08:00'])
 clothes=[clothing_detail(root,id,'/api/workspaces/chloe') for id in ['O001','O002']]
 detail=model_detail(root,'M001' ,'/api/workspaces/chloe')
 media={item['media']['url']:base64.b64encode((root/item['media']['key']).read_bytes()).decode() for item in detail['images']+[image for look in detail['looks'] for image in look['images']+look['clothing']]+[image for item in clothes for image in item['images']]}
 print(json.dumps({'clothingCards':clothing_cards(root,'/api/workspaces/chloe'),'clothes':clothes,'cards':model_cards(root,'/api/workspaces/chloe'),'details':[detail,model_detail(root,'M002','/api/workspaces/chloe')],'media':media,'image':base64.b64encode(image.read_bytes()).decode()}))
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
   if(path==='/api/workspaces/chloe/shared-clothing')return route.fulfill({json:sample.clothingCards});
   const garment=sample.clothes.find(item=>path===`/api/workspaces/chloe/shared-clothing/${item.id}`);
   if(garment)return route.fulfill({json:garment});
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
  await page.getByRole('heading',{name:/^基础全身三视图/}).waitFor();
  assert.equal(await page.getByRole('heading',{name:'人物特征',exact:true}).count(),0);
  assert.equal(await page.getByRole('navigation',{name:'当前采用三视图'}).locator('[aria-current="page"]').textContent(),'遮面版');
  const expectedRef=purpose=>{const image=sample.details[0].images.find(image=>image.adopted && image.purpose===purpose);return `${image.resource}@${image.version}`;};
  assert.ok((await page.getByRole('heading',{name:/^正面面部图/}).textContent()).includes(expectedRef('正面面部')));
  assert.ok((await page.getByRole('heading',{name:/^基础全身三视图/}).textContent()).includes(expectedRef('全身三视图遮面版')));
  await page.getByRole('navigation',{name:'当前采用三视图'}).getByRole('button',{name:'原图',exact:true}).click();
  await page.getByRole('heading',{name:'基础全身三视图 · '+expectedRef('全身三视图原图'),exact:true}).waitFor();
  assert.equal(await page.getByRole('region',{name:'基础全身三视图',exact:true}).getByText('其他版本',{exact:true}).count(),0);
  await page.reload();
  await page.getByRole('heading',{name:/^基础全身三视图/}).waitFor();
  assert.match(page.url(),/modelTab=images/);
  assert.match(page.url(),/view=original/);
  const detailTabs=page.getByRole('navigation',{name:'模特详情分类'});
  assert.deepEqual(await detailTabs.getByRole('button').allTextContents(),['模特信息','模特图片','造型']);
  const tabRect=await detailTabs.boundingBox(),crumbRect=await page.locator('.breadcrumbs').boundingBox(),contentRect=await page.locator('.chloe-model-images').boundingBox();
  assert.ok(tabRect.y-(crumbRect.y+crumbRect.height)>contentRect.y-(tabRect.y+tabRect.height));
  assert.equal(await page.getByText('不应显示的来源文字',{exact:true}).count(),0);
  assert.equal(await page.getByRole('heading',{name:'资产身份',exact:true}).count(),0);
  const faceColumn=page.getByRole('region',{name:'正面面部图',exact:true});
  const bodyColumn=page.getByRole('region',{name:'基础全身三视图',exact:true});
  assert.equal(await page.getByRole('heading',{name:'当前采用',exact:true}).count(),0);
  const faceView=faceColumn.getByRole('navigation',{name:'正面面部图视图'});
  assert.deepEqual(await faceView.getByRole('button').allTextContents(),['原图']);
  assert.equal(await faceView.locator('[aria-current="page"]').textContent(),'原图');
  const faceBox=await faceColumn.boundingBox(),bodyBox=await bodyColumn.boundingBox();
  assert.ok(faceBox.x+faceBox.width<bodyBox.x && Math.abs(faceBox.y-bodyBox.y)<1,'面部和三视图同页左右排列');
  assert.ok(bodyBox.x+bodyBox.width<=width+1);
  await page.screenshot({path:output+`/${width}-images.png`,fullPage:true});
  for (const selector of [':scope > h2',':scope > div > nav',':scope > div > .asset-media-card',':scope > div > .asset-media-card .cover']) {
    const left=await faceColumn.locator(selector).boundingBox(),right=await bodyColumn.locator(selector).boundingBox();
    assert.ok(Math.abs(left.y-right.y)<1,`左右对齐：${selector}`);
  }
  assert.equal(await page.locator('.chloe-model-image-column > div > .asset-media-card h3').count(),0);
  const refs=faceColumn.locator(':scope > div > details');
  assert.equal(await refs.getAttribute('open'),null);
  await refs.locator(':scope > summary').click();
  await refs.locator('.asset-media-card').nth(3).waitFor();
  assert.equal(await refs.locator('.asset-media-card').count(),4);
  const versions=await refs.locator('.asset-media-card h3').allTextContents();
  assert.deepEqual(versions.map(title=>title.split('@')[1]),['V005','V004','V003','V002']);
  const scroll=await refs.locator('.chloe-model-versions').evaluate(el=>({height:el.clientHeight,full:el.scrollHeight,overflow:getComputedStyle(el).overflowY}));
  assert.ok(scroll.height<=1050 && scroll.full>scroll.height);
  assert.equal(scroll.overflow,'auto');
  await refs.locator('.cover').last().click();
  await page.getByRole('dialog').waitFor(); assert.match(page.url(),/ref=/);
  await page.reload(); await page.getByRole('dialog').waitFor();
  assert.equal(await page.getByRole('dialog').locator('img').count(),1);
  assert.equal(await page.getByRole('dialog').getAttribute('class'),'dialog-fullscreen');
  await page.getByRole('dialog').getByRole('button',{name:'退出全屏看图',exact:true}).click();
  await page.getByRole('dialog').waitFor({state:'detached'});
  assert.doesNotMatch(page.url(),/ref=/);
  await faceColumn.locator(':scope > div > .asset-media-card .cover').click();
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({state:'detached'});
  assert.doesNotMatch(page.url(),/ref=/);

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
  await page.getByRole('heading',{name:'造型信息',exact:true}).waitFor();
  assert.equal(await page.locator('.breadcrumbs [aria-current="page"]').textContent(),'L001 · 通勤造型');
  assert.equal(await page.getByRole('navigation',{name:'造型详情分类'}).count(),0);
  const lookInfo=page.getByRole('region',{name:'造型信息',exact:true});
  const [navRect,backRect,rowRect]=await page.locator('.breadcrumbs').evaluate(el=>[...el.children,el].map(node=>{const r=node.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}));
  assert.ok(Math.abs(backRect.y+backRect.height/2-navRect.y-navRect.height/2)<1,JSON.stringify({backRect,navRect,rowRect}));
  assert.ok(Math.abs(backRect.x+backRect.width-rowRect.x-rowRect.width)<1);
  assert.equal(await lookInfo.locator('dl > div').filter({has:page.getByText('造型说明',{exact:true})}).locator('dd').textContent(),'无');
  assert.equal(await lookInfo.getByText('服装来源类型',{exact:true}).count(),0);
  const layout=await page.locator('.chloe-look-detail').evaluate(el=>Array.from(el.children).map(c=>{const r=c.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width}}));
  assert.equal(layout[0].y,layout[1].y);
  assert.ok(Math.abs(layout[0].width/layout[1].width-2/3)<0.01);
  const clothing=lookInfo.getByRole('region',{name:'服装参考图',exact:true});
  assert.equal(await clothing.locator('.asset-media-card').count(),2);
  assert.equal(await lookInfo.locator(':scope > :last-child').getAttribute('aria-label'),'服装参考图');
  await clothing.locator('.cover').first().click();
  await page.getByRole('dialog').waitFor();
  assert.ok((await page.getByRole('dialog').locator('img').getAttribute('src')).includes(sample.details[0].looks[0].clothing[0].reference.split('@')[0]));
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({state:'detached'});
  const lookPanel=page.getByRole('region',{name:'全身定装三视图',exact:true});
  const lookMasked=sample.details[0].looks[0].images.find(image=>image.adopted && image.purpose==='全身三视图遮面版');
  await page.getByRole('heading',{name:`全身定装三视图 · ${lookMasked.resource}@${lookMasked.version}`,exact:true}).waitFor();
  await lookPanel.locator(':scope > div > .asset-media-card .cover').click();
  await page.getByRole('dialog').waitFor();
  assert.ok((await page.getByRole('dialog').locator('img').getAttribute('src')).includes(lookMasked.resource));
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({state:'detached'});
  await lookPanel.getByText('其他版本',{exact:true}).click();
  const lookRefs=lookPanel.locator('.chloe-model-versions');
  assert.equal(await lookRefs.locator('.asset-media-card').count(),4);
  assert.deepEqual((await lookRefs.locator('h3').allTextContents()).map(title=>title.split('@')[1]),['V005','V004','V003','V002']);
  const lookScroll=await lookRefs.evaluate(el=>({height:el.clientHeight,full:el.scrollHeight}));
  assert.ok(lookScroll.height<=1050 && lookScroll.full>lookScroll.height);
  await page.getByRole('navigation',{name:'当前采用三视图'}).getByRole('button',{name:'原图',exact:true}).click();
  const lookOriginal=sample.details[0].looks[0].images.find(image=>image.adopted && image.purpose==='全身三视图原图');
  await page.getByRole('heading',{name:`全身定装三视图 · ${lookOriginal.resource}@${lookOriginal.version}`,exact:true}).waitFor();
  await page.reload();
  await page.getByRole('heading',{name:`全身定装三视图 · ${lookOriginal.resource}@${lookOriginal.version}`,exact:true}).waitFor();
  await page.screenshot({path:output+`/${width}-look.png`,fullPage:true});
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
    await page.getByRole('heading',{name:/^基础全身三视图/}).waitFor();
    assert.equal(await page.getByRole('navigation',{name:'模特详情分类'}).locator('[aria-current="page"]').textContent(),'模特图片');
    await page.getByRole('heading',{name:/^正面面部图/}).waitFor();
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
  await page.getByRole('link',{name:'O001 · 示例外套',exact:true}).waitFor();
  assert.equal(await page.locator('.asset-media-card').count(),2);
  await page.getByRole('link',{name:'O001 · 示例外套',exact:true}).click();
  const clothingInfo=page.getByRole('region',{name:'服装信息',exact:true});
  await clothingInfo.getByText('无',{exact:true}).waitFor();
  assert.equal(await page.getByText('不显示的服装来源',{exact:true}).count(),0);
  assert.equal(await page.locator('.breadcrumbs [aria-current="page"]').textContent(),'O001 · 示例外套');
  assert.equal(await page.locator('.breadcrumb-actions').textContent(),'返回服装列表');
  const headerRows=await page.locator('.page-heading').evaluate(el=>['h1','.page-actions','.breadcrumbs > div:first-child','.breadcrumb-actions','.breadcrumbs'].map(selector=>{const r=el.querySelector(selector).getBoundingClientRect();return {y:r.y,height:r.height,right:r.right}}));
  assert.ok(Math.abs(headerRows[0].y+headerRows[0].height/2-headerRows[1].y-headerRows[1].height/2)<=5,JSON.stringify(headerRows));
  assert.ok(headerRows[2].y>headerRows[0].y+headerRows[0].height);
  assert.ok(Math.abs(headerRows[2].y+headerRows[2].height/2-headerRows[3].y-headerRows[3].height/2)<1);
  assert.ok(Math.abs(headerRows[3].right-headerRows[4].right)<1);

  const clothingImages=page.getByRole('region',{name:'服装图片',exact:true});
  const clothingTabs=page.getByRole('navigation',{name:'服装图片用途'});
  assert.deepEqual(await clothingTabs.getByRole('button').allTextContents(),['正面','侧面','背面','细节']);
  const front=sample.clothes[0].images.find(image=>image.purpose==='正面'&&image.adopted);
  await clothingImages.getByRole('heading',{name:`正面 · ${front.resource}@${front.version}`,exact:true}).waitFor();
  await clothingImages.locator('.cover').first().click();
  await page.getByRole('dialog').waitFor();
  assert.ok((await page.getByRole('dialog').locator('img').getAttribute('src')).includes(front.resource));
  await page.getByRole('dialog').locator('img').click();
  await page.getByRole('dialog').waitFor({state:'detached'});
  await clothingImages.getByText('其他版本',{exact:true}).click();
  const garmentVersions=page.locator('[aria-label="服装其他版本"]');
  assert.deepEqual((await garmentVersions.locator('h3').allTextContents()).map(text=>text.split('@')[1]),['V005','V004','V003','V002']);
  const garmentScroll=await garmentVersions.evaluate(el=>({height:el.clientHeight,full:el.scrollHeight}));
  assert.ok(garmentScroll.height<=1050 && garmentScroll.full>garmentScroll.height);
  await clothingTabs.getByRole('button',{name:'侧面',exact:true}).click();
  await page.getByText('尚未采用侧面图',{exact:true}).waitFor();
  await clothingTabs.getByRole('button',{name:'细节',exact:true}).click();
  await clothingImages.getByRole('heading',{name:/^细节\/纽扣/}).waitFor();
  await page.reload();
  await clothingImages.getByRole('heading',{name:/^细节\/纽扣/}).waitFor();
  assert.match(page.url(),/purpose=/);
  const clothingLayout=await page.locator('.chloe-look-detail').evaluate(el=>Array.from(el.children).map(child=>{const r=child.getBoundingClientRect();return {width:r.width,y:r.y}}));
  assert.equal(clothingLayout[0].y,clothingLayout[1].y);
  assert.ok(Math.abs(clothingLayout[0].width/clothingLayout[1].width-2/3)<0.01);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.getByText('资料与制作记录',{exact:true}).click();
  assert.deepEqual(await page.locator('.chloe-model-detail > details > details > summary').allTextContents(),['关联资料','采用依据与时间','采用变更','执行记录']);
  await page.screenshot({path:output+`/${width}-clothing.png`,fullPage:true});
  await page.getByRole('link',{name:'返回服装列表',exact:true}).click();
  await page.getByRole('link',{name:'O002 · 未选图服装',exact:true}).click();
  await page.getByText('尚未采用正面图',{exact:true}).waitFor();
  assert.equal(await page.getByText('其他版本',{exact:true}).count(),0);
  await page.getByRole('navigation',{name:'当前位置',exact:true}).getByRole('link',{name:'共用资产',exact:true}).click();
  await page.getByRole('heading',{name:'M001 · 示例模特甲',exact:true}).waitFor();
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await page.close();
 }
 console.log('Chloe model cards passed: document-based fixtures, one card per model, adopted/empty portraits, entry metadata hidden/image preview, breadcrumbs, long content and retry; screenshots '+output);
}finally{await browser.close();await server.close();}
