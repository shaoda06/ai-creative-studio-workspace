// Real Chloe page and adapter output, with isolated HTTP responses only.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(require.resolve('vite'));
const react = (await import(require.resolve('@vitejs/plugin-react'))).default;
const frontend = fileURLToPath(new URL('../frontend/', import.meta.url));
const tool = fileURLToPath(new URL('../', import.meta.url));
const version = JSON.parse(await readFile(frontend+'package.json', 'utf8')).version;
const prepared = JSON.parse(execFileSync(tool+'.venv/bin/python', ['-c', `
import json,base64
from tests.test_chloe_review import ChloeReviewTests, overview
x=ChloeReviewTests();x.setUp()
try:
 x.prepare()
 data=overview(x.root,x.api)
 images={v["cover"]:base64.b64encode((x.root/v["coverKey"]).read_bytes()).decode() for v in data["videos"] if v["cover"]}
 print(json.dumps({"data":data,"images":images}))
finally:x.doCleanups()
`], { cwd: tool, encoding: 'utf8' }));
const fixture=prepared.data;
const images=new Map(Object.entries(prepared.images).map(([url,bytes])=>[decodeURIComponent(url),Buffer.from(bytes,'base64')]));
const media = await readFile(frontend+'public/component-samples/video.webm');
const server = await createServer({ configFile: false, root: frontend, plugins: [react()], define: { __APP_VERSION__: JSON.stringify(version) }, server: { host: '127.0.0.1', port: 0 } });
await server.listen();
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
 for (const [width, height] of [[1280,640],[1366,768],[1920,1080]]) {
  const page = await browser.newPage({ viewport: { width, height } });
  page.setDefaultTimeout(10000);
  const errors = [], unexpected = [], writes = [];
  let fail = true, empty = false;
  page.on('pageerror', e => errors.push(String(e)));
  await page.route('**/api/**', route => {
   const request = route.request(), url = new URL(request.url()), path = decodeURIComponent(url.pathname);
   if (request.method() !== 'GET') writes.push(path);
   if (path === '/api/service') return route.fulfill({ json: { version, ready: true } });
   if (path === '/api/workspaces') return route.fulfill({ json: [{ id: 'chloe', name: 'Chloe AI视频带货', view: 'chloe-commerce', projects: [] }] });
   if (path === '/api/task-monitor') return route.fulfill({ json: { tasks: [], local_tasks: [], remote_nodes: [], local_counts: {}, history_updated_at: {} } });
   if (path.endsWith('/reviews')) return fail ? route.fulfill({ status: 409, json: { detail: '隔离读取失败' } }) : route.fulfill({ json: empty ? { videos: [], conclusions: [], trials: [] } : fixture });
   if (path.endsWith('/reviews/document')) return route.fulfill({ json: { title: '原始数据', text: '平台原始证据' } });
   if (images.has(path)) return route.fulfill({contentType:'image/png',body:images.get(path)});
   if (path.endsWith('.webm')) return route.fulfill({ contentType: 'video/webm', body: media });
   unexpected.push(path);return route.fulfill({ status: 404, body: 'Unexpected isolated request' });
  });
  const base = server.resolvedUrls.local[0]+'#/spaces/chloe?section=review';
  await page.goto(base);
  await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
  fail=false;await page.getByRole('button',{name:'重新读取',exact:true}).click();
  await page.getByRole('button',{name:/V001 · 开场展示/}).waitFor();
  await page.getByRole('button',{name:/V002 · 内容分析/}).click();
  await page.getByText('暂未取得效果数据。',{exact:true}).waitFor();
  await page.getByRole('region',{name:'内容判断'}).getByText('核对展示动作',{exact:false}).waitFor();
  await page.getByRole('button',{name:/V001 · 开场展示/}).click();
  assert(await page.getByAltText('V001 封面').evaluate(img=>img.complete && img.naturalWidth>0));
  const metric = page.getByRole('table',{name:'效果指标'});
  assert.match(await metric.innerText(),/250/);
  await page.getByRole('button',{name:'跨视频结论',exact:true}).click();
  await page.getByRole('heading',{name:'R001 · 跨视频结论'}).waitFor();
  assert.equal(await page.getByRole('region',{name:'视频与证据'}).getByRole('button',{name:'说明',exact:true}).count(),0);
  await page.getByRole('region',{name:'视频与证据'}).getByRole('button',{name:'D002',exact:true}).click();
  await metric.getByText('250',{exact:true}).waitFor();
  await page.getByRole('button',{name:'跨视频结论',exact:true}).click();
  await page.getByRole('region',{name:'视频与证据'}).getByRole('button',{name:'R001',exact:true}).click();
  assert(new URL(page.url()).hash.includes('review=R001'));
  assert.equal(await page.getByRole('region',{name:'成片与发布对象'}).getByRole('button',{name:'调整目标',exact:true}).count(),0);
  await page.getByRole('table',{name:'效果指标'}).getByText('100',{exact:true}).waitFor();
  await page.getByRole('combobox',{name:'采集批次',exact:true}).click();
  await page.getByRole('option',{name:/D002/}).click();
  await metric.getByText('250',{exact:true}).waitFor();
  await metric.getByRole('link',{name:'原数据'}).click();
  await page.getByRole('dialog').getByText('平台原始证据').waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('region',{name:'成片与发布对象'}).getByRole('button',{name:'成片',exact:true}).click();
  await page.getByRole('dialog').locator('video').waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'T001 · 采用',exact:true}).click();
  await page.getByRole('heading',{name:'T001 · 建议验证'}).waitFor();
  await page.getByText('内容调整已落实，效果未取得',{exact:true}).waitFor();
  await page.getByRole('button',{name:'查看 R001 原复盘'}).click();
  await metric.getByText('100',{exact:true}).waitFor();
  await page.getByRole('button',{name:'建议验证',exact:true}).click();
  await page.getByRole('combobox',{name:'采用状态',exact:true}).click();
  await page.getByRole('option',{name:'待决定',exact:true}).click();
  await page.getByRole('heading',{name:'T002 · 建议验证'}).waitFor();
  await page.getByText('未取得验证结果。',{exact:true}).waitFor();
  await page.reload();
  await page.getByRole('heading',{name:'T002 · 建议验证'}).waitFor();
  for (const name of ['单条复盘','跨视频结论','建议验证']) {
   await page.getByRole('button',{name,exact:true}).click();
   await page.locator('.chloe-review-detail').waitFor();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1), `${width}: ${name} 横向越界`);
   const boxes=await page.locator('.chloe-review-list,.chloe-review-detail').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width};}));
   assert(boxes[0].right < boxes[1].left && boxes[1].width > boxes[0].width*2);
   if(width===1366) await page.screenshot({path:`/tmp/chloe-review-${name}.png`,fullPage:true});
  }
  empty=true;await page.reload();
  await page.getByText('暂无建议验证。',{exact:true}).waitFor();
  await page.getByRole('button',{name:'跨视频结论',exact:true}).click();
  await page.getByText('暂无跨视频结论。',{exact:true}).waitFor();
  await page.getByRole('button',{name:'单条复盘',exact:true}).click();
  await page.getByText('暂无视频项目。',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);assert.deepEqual(writes,[]);
  await page.close();
 }
 console.log('Chloe review UI: three desktop sizes, navigation, batches, evidence, preview, filtering, reload, empty/error states passed.');
} finally { await browser.close();await server.close(); }
