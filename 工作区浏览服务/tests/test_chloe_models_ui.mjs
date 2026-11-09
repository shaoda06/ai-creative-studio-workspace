import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { mkdtemp, readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(pathToFileURL(require.resolve('vite')).href);
const react = (await import(pathToFileURL(require.resolve('@vitejs/plugin-react')).href)).default;
const tool = fileURLToPath(new URL('../', import.meta.url));
const frontend = tool+'frontend/';
const version = JSON.parse(await readFile(frontend+'package.json', 'utf8')).version;
const python = join(tool, process.platform==='win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const sample = JSON.parse(execFileSync(python,['-X','utf8','-c',`
import base64,json,os,tempfile
from pathlib import Path
from PIL import Image
from backend.chloe_models import model_cards,model_detail
from backend.chloe_clothing import clothing_cards,clothing_detail
from backend.chloe_reference_assets import HAIR,SCENES,asset_cards,asset_detail
from chloe_init import initialize_workspace,initialize_project,initialize_asset,SKILLS
import sys
sys.path.insert(0,str(SKILLS/'chloe-assets/scripts'))
from chloe_resources import import_media
import project_resources as resources
with tempfile.TemporaryDirectory(dir=SKILLS.parents[1] if os.name=='nt' else None) as tmp:
 workspace=initialize_workspace(Path(tmp)/'Chloe Workspace')
 root=initialize_project(workspace,'示例账号')
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
 for purpose,color,size,key in [('正面面部','#95aabb',(200,300),'face2'),('正面面部','#95aacc',(200,300),'face3'),('正面面部','#95aadd',(200,300),'face4'),('正面面部','#95aaee',(200,300),'face5'),('全身三视图原图','#bbaabb',(600,600),'views'),('全身三视图原图','#aabbaa',(600,600),'views2')]:
  source=Path(tmp)/(key+'.png');Image.new('RGB',size,color).save(source)
  result=import_media(root,source,key,resource_id=ref['resource_id'] if key.startswith('face') else None)
  reference=label(Path(result['absolute_file']),result['resource_id'],result['version'])
  append('参考版本',[purpose,reference,first,'不适用'])
  if key=='views':append('当前采用',[purpose,reference,'隔离采用','2026-11-07T12:00:00+08:00'])
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
 for index,color in enumerate(['#cfcbbe','#e1e5ca']):
  source=Path(tmp)/f'look-face-{index}.png';Image.new('RGB',(640,352),color).save(source)
  result=import_media(root,source,source.stem,resource_id=look_face_resource if index else None)
  look_face_resource=result['resource_id']
  reference='[共用:'+look_face_resource+'@'+result['version']+'](<'+os.path.relpath(result['absolute_file'],look.parent)+'>)'
  append('参考版本',['造型面部三视图',reference,'用户提供','不适用'])
  if index==1:append('当前采用',['造型面部三视图',reference,'隔离采用','2026-11-07T12:00:00+08:00'])
 append('执行记录',['E001','图片生成','不适用','隔离测试','测试','不适用','隔离测试','未取得','未取得','未取得','准备中','未取得'])
 for index,color in enumerate(['#ee9a70','#336688','#86a173','#b68163','#67618b','#ceba86'],1):
  slot=str(index)
  source=Path(tmp)/('clothing'+slot+'.png');Image.new('RGB',(320,160),color).save(source)
  result=import_media(root,source,'clothing'+slot)
  reference=label(Path(result['absolute_file']),result['resource_id'],result['version']).replace(os.path.relpath(Path(result['absolute_file']),model),os.path.relpath(Path(result['absolute_file']),look.parent))
  append('输入记录',['E001',slot,'服装参考','不适用',reference])
 clothing=initialize_asset(root,'服装','O001','示例外套')
 initialize_asset(root,'服装','O002','未选图服装')
 path=clothing/'服装说明.md'
 path.write_text(path.read_text().replace('| 来源说明 | 待核实 |','| 来源说明 | 不显示的服装来源 |'))
 for index,purpose in enumerate(['服装展示图']*5+['服装参考图']*2):
  source=Path(tmp)/('garment'+str(index)+'.png');Image.new('RGB',(240,320),(80+index*15,130,90)).save(source)
  result=import_media(root,source,'garment'+str(index),resource_id=garment_resource if 0<index<5 else None)
  if index==0:garment_resource=result['resource_id']
  reference='[共用:'+result['resource_id']+'@'+result['version']+'](<'+os.path.relpath(result['absolute_file'],clothing)+'>)'
  append('参考版本',[purpose,reference,'用户提供','不适用'])
  if index==0:append('当前采用',[purpose,reference,'隔离采用','2026-11-07T12:00:00+08:00'])
 clothes=[clothing_detail(root,id,'/api/workspaces/chloe') for id in ['O001','O002']]
 references={}
 for kind, name, size in [(HAIR,'示例盘发',(640,360)),(SCENES,'示例庭院',(360,640))]:
  folder=initialize_asset(root,kind.label,kind.prefix+'001',name)
  initialize_asset(root,kind.label,kind.prefix+'002','未选图'+kind.label)
  path=folder/(kind.label+'说明.md')
  path.write_text(path.read_text().replace('| 来源说明 | 待核实 |','| 来源说明 | 不显示的'+kind.label+'来源 |'))
  for index,purpose in enumerate([kind.label+'展示图']*5+[kind.label+'参考图']*2):
   key=kind.prefix+str(index)
   source=Path(tmp)/(key+'.png');Image.new('RGB',size,(80+index*15,130,90)).save(source)
   result=import_media(root,source,key,resource_id=display_resource if 0<index<5 else None)
   if index==0:display_resource=result['resource_id']
   reference='[共用:'+result['resource_id']+'@'+result['version']+'](<'+os.path.relpath(result['absolute_file'],folder)+'>)'
   append('参考版本',[purpose,reference,'用户提供','不适用'])
   if index==0:append('当前采用',[purpose,reference,'隔离采用','2026-11-07T12:00:00+08:00'])
  references[kind.label]=[asset_detail(root,kind.prefix+suffix,'/api/workspaces/chloe',kind) for suffix in ('001','002')]
 hair,scenes=references['发型'],references['场景']
 detail=model_detail(root,'M001' ,'/api/workspaces/chloe')
 media={item['media']['url']:base64.b64encode((root/item['media']['key']).read_bytes()).decode() for item in detail['images']+[image for look in detail['looks'] for image in look['images']+look['clothing']]+[image for item in hair+clothes+scenes for image in item['images']]}
 print(json.dumps({'hairCards':asset_cards(root,'/api/workspaces/chloe',HAIR),'hair':hair,'sceneCards':asset_cards(root,'/api/workspaces/chloe',SCENES),'scenes':scenes,'clothingCards':clothing_cards(root,'/api/workspaces/chloe'),'clothes':clothes,'cards':model_cards(root,'/api/workspaces/chloe'),'details':[detail,model_detail(root,'M002','/api/workspaces/chloe')],'media':media,'image':base64.b64encode(image.read_bytes()).decode()}))
`],{cwd:tool,encoding:'utf8'}));
const output = await mkdtemp(join(tmpdir(),'chloe-models-'));
const server = await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true});

async function assertNaturalImage(cover, description) {
  const image = await cover.locator('img').evaluate(async img => {
    await img.decode();
    const box = img.getBoundingClientRect();
    const cover = img.parentElement.getBoundingClientRect();
    return {width:box.width,height:box.height,coverWidth:cover.width,coverHeight:cover.height,
      availableWidth:img.parentElement.parentElement.clientWidth,naturalRatio:img.naturalWidth/img.naturalHeight};
  });
  assert.ok(Math.abs(image.width-image.availableWidth)<1 && Math.abs(image.width-image.coverWidth)<1, description+'铺满图片区域');
  assert.ok(Math.abs(image.height-image.coverHeight)<1 && Math.abs(image.width/image.height-image.naturalRatio)<.01, description+'按原图比例调整高度');
}

try {
 for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
  const page=await browser.newPage({viewport:{width,height}}), errors=[], unexpected=[];
  let fail=false, long=false, emptyScenes=false, emptyHair=false, manyLookReferences=false;
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   const path=new URL(route.request().url()).pathname;
   if(route.request().method()!=='GET') unexpected.push(path);
   if(path==='/api/service')return route.fulfill({json:{version,ready:true}});
   if(path==='/api/workspaces')return route.fulfill({json:[{id:'chloe',name:'Chloe AI视频带货',view:'chloe-commerce',projects:[]}]});
   if(path==='/api/task-monitor')return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path==='/api/workspaces/chloe/shared-voices') return route.fulfill({json:[{id:'A001',name:'声音甲',description:'无',models:['M001'],media:{kind:'audio',name:'声音甲',key:'sample.wav',url:'/component-samples/tone.wav'},reference:{resource:'AUD-SAMPLE',version:'V001',duration:4}}]});
   if(path==='/api/workspaces/chloe/shared-models') {
    if(fail)return route.fulfill({status:409,json:{detail:'isolated invalid document'}});
    const cards=structuredClone(sample.cards);
    if(long){cards[0].name='LongModelName'.repeat(30);}
    return route.fulfill({json:cards});
   }
   if(path==='/api/workspaces/chloe/shared-hair')return route.fulfill({json:emptyHair ? [] : sample.hairCards});
   const hairstyle=sample.hair.find(item=>path===`/api/workspaces/chloe/shared-hair/${item.id}`);
   if(hairstyle)return route.fulfill({json:hairstyle});
   if(path==='/api/workspaces/chloe/shared-clothing')return route.fulfill({json:sample.clothingCards});
   if(path==='/api/workspaces/chloe/shared-scenes')return route.fulfill(fail ? {status:409,json:{detail:'isolated invalid scene'}} : {json:emptyScenes ? [] : sample.sceneCards});
   const scene=sample.scenes.find(item=>path===`/api/workspaces/chloe/shared-scenes/${item.id}`);
   if(scene)return route.fulfill({json:scene});
   const garment=sample.clothes.find(item=>path===`/api/workspaces/chloe/shared-clothing/${item.id}`);
   if(garment)return route.fulfill({json:garment});
   const detail=sample.details.find(item=>path===`/api/workspaces/chloe/shared-models/${item.id}`);
   if(detail)return route.fulfill({json:manyLookReferences ? detail : {...detail,
     looks:detail.looks.map(look=>({...look,clothing:look.clothing.slice(0,2)}))}});
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
  const blankBox=await placeholder.boundingBox(), imageBox=await page.locator('.asset-media-card').first().locator('.cover').boundingBox();
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
  const play=page.getByRole('button',{name:'播放示例模特甲 · 声音甲',exact:true});
  await play.click();
  await page.waitForFunction(()=>document.querySelector('audio')?.currentSrc.includes('tone.wav'));
  assert.ok(page.url().endsWith('section=assets'),'试听不进入模特详情');
  assert.ok(await page.getByRole('button',{name:'示例模特乙暂无音频',exact:true}).isDisabled());
  const card=page.getByRole('link',{name:'M001 · 示例模特甲',exact:true});
  assert.equal(await card.locator('button,a').count(),0);
  await card.focus(); await page.keyboard.press('Enter');
  await page.getByRole('heading',{name:'人物特征',exact:true}).waitFor();
  await page.getByRole('region',{name:'声音信息',exact:true}).getByRole('link',{name:'A001 · 声音甲'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'播放AUD-SAMPLE@V001',exact:true}).count(),1);
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
  const expectedRef=purpose=>{const image=sample.details[0].images.find(image=>image.adopted && image.purpose===purpose);return `${image.resource}@${image.version}`;};
  assert.ok((await page.getByRole('heading',{name:/^正面面部图/}).textContent()).includes(expectedRef('正面面部')));
  await page.getByRole('heading',{name:'基础全身三视图（1:1） · '+expectedRef('全身三视图原图'),exact:true}).waitFor();
  await page.reload();
  await page.getByRole('heading',{name:'基础全身三视图（1:1） · '+expectedRef('全身三视图原图'),exact:true}).waitFor();
  assert.match(page.url(),/modelTab=images/);
  const detailTabs=page.getByRole('navigation',{name:'模特详情分类'});
  assert.deepEqual(await detailTabs.getByRole('button').allTextContents(),['模特信息','模特图片','造型']);
  const tabRect=await detailTabs.boundingBox(),crumbRect=await page.locator('.breadcrumbs').boundingBox(),contentRect=await page.locator('.chloe-model-images').boundingBox();
  assert.ok(tabRect.y-(crumbRect.y+crumbRect.height)>contentRect.y-(tabRect.y+tabRect.height));
  assert.equal(await page.getByText('不应显示的来源文字',{exact:true}).count(),0);
  assert.equal(await page.getByRole('heading',{name:'资产身份',exact:true}).count(),0);
  const faceColumn=page.getByRole('region',{name:'正面面部图',exact:true});
  const bodyColumn=page.getByRole('region',{name:'基础全身三视图',exact:true});
  assert.equal(await page.getByRole('region',{name:'面部三视图',exact:true}).count(),0);
  assert.deepEqual(await bodyColumn.getByRole('navigation').getByRole('button').allTextContents(),['原图']);
  await bodyColumn.locator('.cover').first().click();
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  await bodyColumn.getByText('其他版本',{exact:true}).click();
  assert.equal(await bodyColumn.locator('.chloe-model-versions .asset-media-card').count(),1);
  const shortVersions=bodyColumn.locator('.chloe-model-versions');
  await shortVersions.locator('.cover').hover();
  const pageBeforeWheel=await page.evaluate(()=>scrollY);
  await page.mouse.wheel(0,250);
  await page.waitForFunction(before=>scrollY>before,pageBeforeWheel);

  await bodyColumn.getByText('其他版本',{exact:true}).click();
  assert.equal(await page.getByRole('heading',{name:'当前采用',exact:true}).count(),0);
  const faceView=faceColumn.getByRole('navigation',{name:'正面面部图视图'});
  assert.deepEqual(await faceView.getByRole('button').allTextContents(),['原图']);
  assert.equal(await faceView.locator('[aria-current="page"]').textContent(),'原图');
  const faceBox=await faceColumn.boundingBox(),bodyBox=await bodyColumn.boundingBox();
  assert.ok(faceBox.x+faceBox.width<bodyBox.x && Math.abs(faceBox.y-bodyBox.y)<1,'正面面部图在左，基础全身三视图在右');
  assert.ok(bodyBox.x+bodyBox.width<=width+1);
  const bodyCover=await bodyColumn.locator(':scope > div > .asset-media-card .cover').boundingBox();
  assert.ok(Math.abs(bodyCover.width / bodyCover.height - 1)<.01,'基础全身图区域为1:1');
  const portraitCover=faceColumn.locator(':scope > div > .asset-media-card .cover');
  await assertNaturalImage(portraitCover,'正面面部图');
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
  const longVersions=refs.locator('.chloe-model-versions');
  assert.equal(await longVersions.evaluate(el=>getComputedStyle(el).overscrollBehaviorY),'auto');
  await longVersions.locator('.cover').first().hover();
  await page.mouse.wheel(0,250);
  await page.waitForFunction(()=>document.querySelector('[aria-label="正面面部其他版本"]').scrollTop>0);
  await longVersions.evaluate(el=>el.scrollTop=0);
  await longVersions.locator('.cover').first().hover();
  const boundaryPage=await page.evaluate(()=>scrollY);
  await page.mouse.wheel(0,-250);
  await page.waitForFunction(before=>scrollY<before,boundaryPage);

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
  const lookOriginal=sample.details[0].looks[0].images.find(image=>image.adopted && image.purpose==='全身三视图原图');
  assert.ok((await page.getByRole('link',{name:'L001 · 通勤造型',exact:true}).locator('img').getAttribute('src')).includes(lookOriginal.resource));
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
  const lookFacePanel=page.getByRole('region',{name:'造型面部三视图',exact:true});
  const lookPanel=page.getByRole('region',{name:'全身定装三视图',exact:true});
  const [infoBox,lookFaceBox,lookBodyBox]=await Promise.all([lookInfo.boundingBox(),lookFacePanel.boundingBox(),lookPanel.boundingBox()]);
  assert.equal(infoBox.y,lookFaceBox.y);
  assert.ok(Math.abs(infoBox.width/lookFaceBox.width-2/3)<0.01);
  assert.equal(lookFaceBox.x,lookBodyBox.x);
  assert.equal(lookFaceBox.width,lookBodyBox.width);
  assert.ok(lookFaceBox.y+lookFaceBox.height<lookBodyBox.y);
  assert.ok(Math.abs(infoBox.y+infoBox.height-lookBodyBox.y-lookBodyBox.height)<1);
  const lookFace=sample.details[0].looks[0].images.find(image=>image.adopted && image.purpose==='造型面部三视图');
  const lookFaceHeading=lookFacePanel.getByRole('heading',{name:`造型面部三视图（16:9） · ${lookFace.resource}@${lookFace.version}`,exact:true});
  await lookFaceHeading.waitFor();
  const faceCover=lookFacePanel.locator(':scope > div > .asset-media-card .cover');
  await assertNaturalImage(faceCover,'造型面部三视图');
  await faceCover.click();
  await page.getByRole('dialog').waitFor();
  assert.equal(await page.getByRole('dialog').locator('img').getAttribute('src'),lookFace.media.url);
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({state:'detached'});
  const faceVersions=lookFacePanel.getByText('其他版本',{exact:true});
  await faceVersions.click();
  assert.deepEqual(await lookFacePanel.locator('.chloe-model-versions h3').allTextContents(),[`造型面部三视图 · ${lookFace.resource}@V001`]);
  await faceVersions.click();
  const clothing=lookInfo.getByRole('region',{name:'造型参考图',exact:true});
  const referenceList=clothing.locator('.chloe-look-reference-list');
  assert.equal(await clothing.locator('.asset-media-card').count(),2);
  assert.equal(await lookInfo.locator(':scope > :last-child').getAttribute('aria-label'),'造型参考图');
  for (const cover of await clothing.locator('.cover').all()) await assertNaturalImage(cover,'造型参考图');
  assert.ok(await referenceList.evaluate(el=>el.scrollHeight===el.clientHeight),'参考图放得下时无需滚动');
  await clothing.locator('.cover').first().click();
  await page.getByRole('dialog').waitFor();
  assert.ok((await page.getByRole('dialog').locator('img').getAttribute('src')).includes(sample.details[0].looks[0].clothing[0].reference.split('@')[0]));
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({state:'detached'});
  assert.deepEqual(await lookPanel.locator('.asset-media-card').first().locator('.field-label').allTextContents(),['尺寸：']);
  assert.deepEqual(await page.getByRole('navigation',{name:'当前采用三视图'}).getByRole('button').allTextContents(),['原图','遮面版']);
  await page.getByRole('heading',{name:`全身定装三视图（4:3） · ${lookOriginal.resource}@${lookOriginal.version}`,exact:true}).waitFor();
  const lookBodyCover=lookPanel.locator(':scope > div > .asset-media-card .cover');
  await assertNaturalImage(lookBodyCover,'全身定装三视图原图');
  const noView=new URL(page.url()); noView.hash=noView.hash.replace('&view=original',''); await page.goto(noView.toString());
  await page.getByRole('heading',{name:`全身定装三视图（4:3） · ${lookOriginal.resource}@${lookOriginal.version}`,exact:true}).waitFor();
  await page.getByRole('navigation',{name:'当前采用三视图'}).getByRole('button',{name:'遮面版',exact:true}).click();
  const lookMasked=sample.details[0].looks[0].images.find(image=>image.adopted && image.purpose==='全身三视图遮面版');
  await page.getByRole('heading',{name:`全身定装三视图（4:3） · ${lookMasked.resource}@${lookMasked.version}`,exact:true}).waitFor();
  await lookFaceHeading.waitFor();
  await assertNaturalImage(lookBodyCover,'全身定装三视图遮面版');
  await lookBodyCover.click();
  await page.getByRole('dialog').waitFor();
  assert.ok((await page.getByRole('dialog').locator('img').getAttribute('src')).includes(lookMasked.resource));
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({state:'detached'});
  await lookPanel.getByText('其他版本',{exact:true}).click();
  assert.equal(await lookPanel.getByRole('navigation',{name:'模特图片用途'}).count(),0);
  const lookRefs=lookPanel.locator('.chloe-model-versions');
  await lookRefs.locator('.asset-media-card').first().waitFor();
  assert.equal(await lookRefs.locator('.asset-media-card').count(),4);
  assert.deepEqual((await lookRefs.locator('h3').allTextContents()).map(title=>title.split('@')[1]),['V005','V004','V003','V002']);
  const lookScroll=await lookRefs.evaluate(el=>({height:el.clientHeight,full:el.scrollHeight}));
  assert.ok(lookScroll.height<=1050 && lookScroll.full>lookScroll.height);
  await page.getByRole('navigation',{name:'当前采用三视图'}).getByRole('button',{name:'原图',exact:true}).click();
  await page.getByRole('heading',{name:`全身定装三视图（4:3） · ${lookOriginal.resource}@${lookOriginal.version}`,exact:true}).waitFor();
  assert.equal(await lookPanel.getByText('其他版本',{exact:true}).count(),0);
  await page.reload();
  await page.getByRole('heading',{name:`全身定装三视图（4:3） · ${lookOriginal.resource}@${lookOriginal.version}`,exact:true}).waitFor();
  await page.screenshot({path:output+`/${width}-look.png`,fullPage:true});
  assert.match(page.url(),/look=L001/);
  assert.equal(await page.getByRole('dialog').count(),0);
  manyLookReferences=true;
  await page.reload();
  await referenceList.locator('.asset-media-card').nth(5).waitFor({state:'attached'});
  await Promise.all([assertNaturalImage(faceCover,'面部正式图'),assertNaturalImage(lookBodyCover,'全身正式图')]);
  const [overflowInfoBox,overflowBodyBox]=await Promise.all([lookInfo.boundingBox(),lookPanel.boundingBox()]);
  assert.ok(Math.abs(overflowInfoBox.y+overflowInfoBox.height-overflowBodyBox.y-overflowBodyBox.height)<1,'参考图过多时仍与右侧底边对齐');
  await referenceList.locator('.cover').first().hover();
  const description = lookInfo.locator('dl');
  const descriptionY = (await description.boundingBox()).y;
  const pageScrollY = await page.evaluate(()=>scrollY);
  await page.mouse.wheel(0,200);
  await page.waitForFunction(()=>document.querySelector('.chloe-look-reference-list').scrollTop>0);
  assert.equal((await description.boundingBox()).y,descriptionY,'滚动参考图时造型信息不移动');
  assert.equal(await page.evaluate(()=>scrollY),pageScrollY,'滚轮只滚动参考图');
  manyLookReferences=false;
  await page.reload();
  await page.getByRole('link',{name:'返回造型列表',exact:true}).click();
  await page.getByRole('link',{name:'L001 · 通勤造型',exact:true}).waitFor();
  await page.locator('.breadcrumbs').getByRole('link',{name:'AI 模特',exact:true}).click();
  await page.getByRole('link',{name:'M002 · 示例模特乙',exact:true}).click();
  await page.getByRole('heading',{name:'人物特征',exact:true}).waitFor();
  await page.getByRole('navigation',{name:'模特详情分类'}).getByRole('button',{name:'模特图片',exact:true}).click();
  await page.getByText('尚未采用全身三视图原图',{exact:true}).waitFor();
  await page.getByRole('navigation',{name:'模特详情分类'}).getByRole('button',{name:'造型',exact:true}).click();
  await page.getByText('暂无该模特的造型资料。',{exact:true}).waitFor();
  await page.locator('.breadcrumbs').getByRole('link',{name:'AI 模特',exact:true}).click();
  await page.getByRole('link',{name:'M001 · 示例模特甲',exact:true}).waitFor();
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
  const assetTabs = page.getByRole('navigation',{name:'共用资产分类',exact:true});
  assert.deepEqual(await assetTabs.getByRole('button').allTextContents(),['AI 模特','发型','服装','场景','声音']);
  for (const [kind,label,prefix,title,ratio,details] of [['hair','发型','H','示例盘发','16:9',sample.hair],['clothing','服装','O','示例外套','4:3',sample.clothes],['scenes','场景','S','示例庭院','9:16',sample.scenes]]) {
  await page.getByRole('navigation',{name:'共用资产分类',exact:true}).getByRole('button',{name:label,exact:true}).click();
  await page.waitForFunction(label=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent===label,label);
  await page.getByRole('link',{name:`${prefix}001 · ${title}`,exact:true}).waitFor();
  assert.equal(await page.locator('.asset-media-card').count(),2);
  await page.getByRole('link',{name:`${prefix}001 · ${title}`,exact:true}).click();
  const clothingInfo=page.getByRole('region',{name:label+'信息',exact:true});
  await clothingInfo.getByText('无',{exact:true}).waitFor();
  assert.equal(await page.getByText(`不显示的${label}来源`,{exact:true}).count(),0);
  const referenceLinks=clothingInfo.getByRole('region',{name:label+'参考图',exact:true});
  const referenceImages=details[0].images.filter(image=>image.purpose===label+'参考图');
  assert.equal(await referenceLinks.getByRole('button').count(),2);
  for (const [index,image] of referenceImages.entries()) {
    await referenceLinks.getByRole('button',{name:`参考图 ${index+1} · ${image.resource}@${image.version}`,exact:true}).click();
    await page.getByRole('dialog').waitFor();
    assert.equal(await page.getByRole('dialog').locator('img').getAttribute('src'),image.media.url);
    await page.keyboard.press('Escape');
    await page.getByRole('dialog').waitFor({state:'detached'});
  }

  assert.equal(await page.locator('.breadcrumbs [aria-current="page"]').textContent(),`${prefix}001 · ${title}`);
  assert.equal(await page.locator('.breadcrumb-actions').textContent(),`返回${label}列表`);
  const headerRows=await page.locator('.page-heading').evaluate(el=>['h1','.page-actions','.breadcrumbs > div:first-child','.breadcrumb-actions','.breadcrumbs'].map(selector=>{const r=el.querySelector(selector).getBoundingClientRect();return {y:r.y,height:r.height,right:r.right}}));
  assert.ok(Math.abs(headerRows[0].y+headerRows[0].height/2-headerRows[1].y-headerRows[1].height/2)<=5,JSON.stringify(headerRows));
  assert.ok(headerRows[2].y>headerRows[0].y+headerRows[0].height);
  assert.ok(Math.abs(headerRows[2].y+headerRows[2].height/2-headerRows[3].y-headerRows[3].height/2)<1);
  assert.ok(Math.abs(headerRows[3].right-headerRows[4].right)<1);

  const clothingImages=page.getByRole('region',{name:label+'图片',exact:true});
  await clothingImages.getByRole('heading',{name:`${label}图片（${ratio}）`,exact:true}).waitFor();
  const clothingTabs=page.getByRole('navigation',{name:label+'图片用途'});
  assert.deepEqual(await clothingTabs.getByRole('button').allTextContents(),[label+'展示图']);
  const front=details[0].images.find(image=>image.purpose===label+'展示图'&&image.adopted);
  await clothingImages.getByRole('heading',{name:`${label}展示图 · ${front.resource}@${front.version}`,exact:true}).waitFor();
  const adoptedClothingCard=clothingImages.locator('.asset-media-card').first();
  assert.deepEqual(await adoptedClothingCard.locator('.field-label').allTextContents(),['尺寸：']);
  assert.equal(await adoptedClothingCard.getByText('下载',{exact:true}).count(),0);
  if (kind === 'hair') {
    const cover = await adoptedClothingCard.locator('.cover').boundingBox();
    assert.ok(Math.abs(cover.width / cover.height - 16 / 9) < 0.01);
    await adoptedClothingCard.getByText(/640 × 360/).waitFor();
  }
  await clothingImages.locator('.cover').first().click();
  await page.getByRole('dialog').waitFor();
  assert.ok((await page.getByRole('dialog').locator('img').getAttribute('src')).includes(front.resource));
  await page.getByRole('dialog').locator('img').click();
  await page.getByRole('dialog').waitFor({state:'detached'});
  await clothingImages.getByText('其他版本',{exact:true}).click();
  const garmentVersions=page.locator(`[aria-label="${label}其他版本"]`);
  assert.deepEqual((await garmentVersions.locator('h3').allTextContents()).map(text=>text.split('@')[1]),['V005','V004','V003','V002']);
  const garmentScroll=await garmentVersions.evaluate(el=>({height:el.clientHeight,full:el.scrollHeight}));
  assert.ok(garmentScroll.height<=1050 && garmentScroll.full>garmentScroll.height);
  assert.equal(await clothingImages.getByRole('heading',{name:new RegExp(`^${label}参考图`)}).count(),0);
  await page.goto(page.url().split('&purpose=')[0]+'&purpose='+encodeURIComponent('正面'));
  await page.reload();
  await clothingImages.getByRole('heading',{name:`${label}展示图 · ${front.resource}@${front.version}`,exact:true}).waitFor();
  assert.deepEqual(await clothingTabs.getByRole('button').allTextContents(),[label+'展示图']);
  const clothingLayout=await page.locator('.chloe-look-detail').evaluate(el=>Array.from(el.children).map(child=>{const r=child.getBoundingClientRect();return {width:r.width,y:r.y}}));
  assert.equal(clothingLayout[0].y,clothingLayout[1].y);
  assert.ok(Math.abs(clothingLayout[0].width/clothingLayout[1].width-2/3)<0.01);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.getByText('资料与制作记录',{exact:true}).click();
  assert.deepEqual(await page.locator('.chloe-model-detail > details > details > summary').allTextContents(),['关联资料','采用依据与时间','采用变更','执行记录']);
  await page.screenshot({path:output+`/${width}-${kind}.png`,fullPage:true});
  await page.getByRole('link',{name:`返回${label}列表`,exact:true}).click();
  await page.getByRole('link',{name:`${prefix}002 · 未选图${label}`,exact:true}).click();
  await page.getByText(`尚未采用${label}展示图`,{exact:true}).waitFor();
  await page.getByRole('region',{name:label+'信息',exact:true}).getByRole('region',{name:label+'参考图',exact:true}).getByText('无',{exact:true}).waitFor();
  assert.equal(await page.getByText('其他版本',{exact:true}).count(),0);
  await page.getByRole('navigation',{name:'当前位置',exact:true}).getByRole('link',{name:'共用资产',exact:true}).click();
  await page.getByRole('heading',{name:'M001 · 示例模特甲',exact:true}).waitFor();
  }
  await page.getByRole('navigation',{name:'共用资产分类',exact:true}).getByRole('button',{name:'场景',exact:true}).click();
  await page.getByRole('link',{name:'S001 · 示例庭院',exact:true}).waitFor();
  fail=true;await page.reload();await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  assert.equal(await page.getByText('暂无场景资料。',{exact:true}).count(),0);
  fail=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.getByRole('link',{name:'S001 · 示例庭院',exact:true}).waitFor();
  emptyScenes=true;await page.reload();await page.getByText('暂无场景资料。',{exact:true}).waitFor();
  assert.equal(await page.locator('.asset-media-card').count(),0);
  emptyHair=true;
  await assetTabs.getByRole('button',{name:'发型',exact:true}).click();
  await page.getByText('暂无发型资料。',{exact:true}).waitFor();
  assert.equal(await page.locator('.asset-media-card').count(),0);
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await page.close();
 }
 console.log('Chloe model cards passed: document-based fixtures, one card per model, adopted/empty portraits, entry metadata hidden/image preview, breadcrumbs, long content and retry; screenshots '+output);
}finally{await browser.close();await server.close();}
