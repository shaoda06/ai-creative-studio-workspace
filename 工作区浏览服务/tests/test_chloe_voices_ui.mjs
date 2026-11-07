import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { mkdtemp, readFile } from 'node:fs/promises';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {createServer}=await import(require.resolve('vite'));
const react=(await import(require.resolve('@vitejs/plugin-react'))).default;
const frontend=fileURLToPath(new URL('../frontend/',import.meta.url));
const version=JSON.parse(await readFile(frontend+'package.json','utf8')).version;
const output=await mkdtemp('/private/tmp/chloe-voices-');
const server=await createServer({configFile:false,root:frontend,plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true});
const media={kind:'audio',name:'样本',key:'sample.wav',url:'/component-samples/tone.wav'};
const detail={id:'A001',name:'声音甲',description:'轻柔、自然的普通话声线',models:[],sections:['关联资料','当前采用','采用变更','执行记录','输入记录','输出记录','审阅记录','返修记录'].map(heading=>({heading,html:'',empty:true})),versions:[
 {purpose:'声音原始参考',resource:'AUD-TEST',version:'V001',media,duration:1,adopted:false,execution:'不适用',sourceHtml:'<p>原件</p>'},
 {purpose:'声音原始参考',resource:'VID-TEST',version:'V001',media:{kind:'video',name:'原始视频',key:'sample.webm',url:'/component-samples/video.webm'},duration:1,adopted:false,execution:'不适用',sourceHtml:'<p>原件</p>'},
 ...Array.from({length:8},(_,i)=>({purpose:'声音参考',resource:'AUD-TEST',version:`V00${i+1}`,media,duration:i+1,adopted:i===7,execution:'不适用',sourceHtml:'<p>来源样本</p>'}))
]};
try {
 for(const [width,height] of [[1280,640],[1366,768],[1920,1080]]){
  const page=await browser.newPage({viewport:{width,height}}); const errors=[],unexpected=[];let empty=false,failed=false,noReference=false;
  page.on('pageerror',error=>errors.push(String(error)));
  await page.route('**/api/**',route=>{
   const path=new URL(route.request().url()).pathname;
   if(route.request().method()!=='GET') unexpected.push(route.request().method()+' '+path);
   if(path==='/api/workspaces/test/shared-voices') return failed ? route.fulfill({status:409,json:{detail:'声音资料错误'}}) : route.fulfill({json:empty?[]:[{id:'A001',name:'声音甲',media},{id:'A002',name:'声音乙',media:null}]});
   if(path==='/api/workspaces/test/shared-voices/A001') return route.fulfill({json:noReference ? {...detail,versions:[]} : detail});
   if(path==='/api/workspaces/test/shared-models') return route.fulfill({json:[]});
   if(path==='/api/service') return route.fulfill({json:{version,ready:true}});
   if(path==='/api/task-monitor') return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
   if(path==='/api/workspaces') return route.fulfill({json:[{id:'test',name:'Chloe声音隔离验证',view:'chloe-commerce',projects:[]}]});
   unexpected.push(path);return route.fulfill({status:404,json:{detail:'unexpected'}});
  });
  const url=server.resolvedUrls.local[0]+'#/spaces/test?section=assets&asset=voices';
  await page.goto(url);
  await page.getByRole('button',{name:'A001 · 声音甲',exact:true}).waitFor();
  assert.ok(await page.getByRole('button',{name:'A002 · 声音乙暂无音频'}).isDisabled());
  await page.getByRole('button',{name:'播放A001 · 声音甲'}).click();
  await page.waitForFunction(()=>document.querySelector('audio')?.currentSrc.includes('tone.wav'));
  await page.getByRole('button',{name:'A001 · 声音甲',exact:true}).click();
  await page.getByRole('heading',{name:'声音信息',exact:true}).waitFor();
  assert.equal(await page.getByRole('region',{name:'原始参考'}).getByRole('button').count(),2);
  await page.getByRole('button',{name:'播放AUD-TEST@V008'}).click();
  await page.waitForFunction(()=>document.querySelector('audio')?.currentSrc.includes('tone.wav'));
  await page.getByRole('button',{name:'参考 1 · AUD-TEST@V001'}).click();
  await page.getByRole('dialog').waitFor();
  assert.ok(await page.locator('audio').first().evaluate(node=>node.paused));
  await page.keyboard.press('Escape');
  await page.getByText('其他版本',{exact:true}).click();
  const versions=page.getByRole('region',{name:'声音参考'}).locator('.chloe-model-versions');
  assert.equal(await versions.locator('article').count(),7);
  assert.equal(await versions.locator('h3').first().textContent(),'AUD-TEST@V007');
  assert.ok(await versions.evaluate(node=>node.scrollHeight>node.clientHeight));
  const left=await page.getByRole('region',{name:'声音信息',exact:true}).boundingBox();
  const right=await page.getByRole('region',{name:'声音参考',exact:true}).boundingBox();
  assert.ok(left.x<right.x && Math.abs(left.y-right.y)<2);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.screenshot({path:output+`/${width}.png`,fullPage:true});
  await page.getByRole('link',{name:'返回声音列表'}).click();
  await page.getByRole('button',{name:'A001 · 声音甲',exact:true}).waitFor();
  empty=true;await page.reload();await page.getByText('暂无声音资料。',{exact:true}).waitFor();
  failed=true;await page.reload();await page.getByText('资料读取失败，请点击重新读取。',{exact:false}).waitFor();
  failed=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();await page.getByText('暂无声音资料。',{exact:true}).waitFor();
  assert.equal(await page.getByRole('link',{name:/演示/}).count(),0);
  noReference=true; empty=false; await page.goto(url+'&voice=A001');
  await page.getByText('尚未采用声音参考。',{exact:true}).waitFor();
  assert.equal(await page.getByText('其他版本',{exact:true}).count(),0);
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  await page.close();
 }
 console.log('声音列表、详情、采用、试听切换、空态及错误重试：三档桌面通过。截图：'+output);
}finally{await browser.close();await server.close();}
