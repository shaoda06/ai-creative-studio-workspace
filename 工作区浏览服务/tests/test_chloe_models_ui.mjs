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
from backend.chloe_models import model_cards
from chloe_init import initialize_workspace,initialize_asset
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
 text=path.read_text().replace('| 资产用途 | 待确定 |','| 资产用途 | 隔离布局示例 |')
 start=text.index('## 当前采用')
 end=text.index('\\n\\n',text.index('| ---',start))
 row='\\n| 正面面部 | [共用:'+ref['resource_id']+'@'+ref['version']+'](<'+os.path.relpath(target,model)+'>) | 隔离示例采用 | 2026-11-07T12:00:00+08:00 |'
 path.write_text(text[:end]+row+text[end:])
 print(json.dumps({'cards':model_cards(root,'/api/workspaces/chloe'),'image':base64.b64encode(image.read_bytes()).decode()}))
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
    if(long){cards[0].name='LongModelName'.repeat(30);cards[0].identity['资产用途']='较长的模特用途说明。'.repeat(35);}
    return route.fulfill({json:cards});
   }
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
  const blankBox=await placeholder.boundingBox(), imageBox=await page.locator('.asset-media-card button.cover').boundingBox();
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
  await page.getByRole('button',{name:'示例模特甲 · 正面面部',exact:true}).click();
  await page.getByRole('dialog').waitFor();
  assert.equal(await page.getByRole('dialog').locator('img').count(),1);
  await page.keyboard.press('Escape');
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
