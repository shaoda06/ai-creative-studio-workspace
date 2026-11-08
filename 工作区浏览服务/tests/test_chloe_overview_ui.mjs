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
// Use the real fixed-document projection, with no parallel hand-written JSON fixture.
const samples = JSON.parse(execFileSync(tool+'.venv/bin/python', ['-c',
  'import json; from pathlib import Path; from backend.chloe_overview import account_overview; print(json.dumps({s:account_overview(Path("tests/fixtures/chloe-overview")/s) for s in ("new","working")}))'], {cwd:tool,encoding:'utf8'}));
const output = await mkdtemp('/private/tmp/chloe-overview-');
const server = await createServer({configFile:false,root:frontend,plugins:[react()],
  define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser = await chromium.launch({channel:'chrome',headless:true});
try {
  for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
    const page = await browser.newPage({viewport:{width,height}});
    const errors = [], unexpected = [];
    let fail = false, long = false, scenario = "new";
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('**/api/**', route => {
      const url = new URL(route.request().url()), path = url.pathname;
      if (route.request().method() !== 'GET') unexpected.push(route.request().method()+' '+path);
      if (path === '/api/service') return route.fulfill({json:{version,ready:true}});
      if (path === '/api/task-monitor') return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
      if (path === '/api/workspaces') return route.fulfill({json:[{id:'chloe',name:'Chloe AI视频带货',view:'chloe-commerce',projects:[]}]});
      if (path === '/api/workspaces/chloe/account-overview') {
        if (fail) return route.fulfill({status:503,json:{detail:'isolated example failure'}});
        const data = structuredClone(samples[scenario]);
        if (long) {
          data.direction['发布平台'] = '抖音、小红书';
          data.direction['目标人群'] = 'LongUnbrokenExample'.repeat(35);
          data.direction['内容风格'] = '较长的内容风格描述。'.repeat(30);
          data.videos[0].progress['当前问题'] = '长问题描述'.repeat(30);
          data.videos[0].progress['下一步'] = 'LongNextStep'.repeat(40);
          data.videos[1].progress['处理状态'] = '受阻';
          data.videos[1].progress['当前问题'] = '人工后期等待补充素材';
          data.videos[2].progress['视频状态'] = '已发布';
        }
        return route.fulfill({json:data});
      }
      unexpected.push(path); return route.fulfill({status:404,json:{detail:'unexpected isolated request'}});
    });
    await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe');
    await page.getByRole('heading',{name:'账号方向',exact:true}).waitFor();
    assert.equal(await page.locator('time').count(),1);
    assert.deepEqual(await page.locator('.chloe-overview-fields dt').allTextContents(),['发布平台','目标人群','内容风格']);
    assert.deepEqual(await page.locator('.chloe-overview-fields dd').allTextContents(),['抖音','待确定','待确定']);
    assert.deepEqual(await page.locator('.chloe-overview h2').allTextContents(),['制作概况','账号方向','待处理事项','定位与当前进度']);
    assert.deepEqual(await page.locator('.chloe-overview-metrics dd').allTextContents(),['0','0','0','0']);
    const metricBoxes = await Promise.all((await page.locator('.chloe-overview-metrics > div').all()).map(el=>el.boundingBox()));
    assert.ok(metricBoxes.every(box=>Math.abs(box.y-metricBoxes[0].y)<1), 'metrics stay in one row');
    await page.getByText('暂无待用户决定或受阻的视频事项。',{exact:true}).waitFor();
    await page.screenshot({path:output+`/${width}-actual-empty.png`,fullPage:true});
    assert.equal(await page.getByRole('link',{name:/演示/}).count(),0);
    scenario = 'working'; await page.reload();
    await page.getByText(samples.working.direction['目标人群'],{exact:true}).waitFor();
    assert.deepEqual(await page.locator('.chloe-overview-metrics dd').allTextContents(),['3','2','1','0']);
    assert.deepEqual(await page.locator('.chloe-overview-metrics dt').allTextContents(),['视频总数','制作中','待发布','已发布']);
    assert.match(await page.locator('.chloe-overview-attention').innerText(),/待用户决定：1 · 受阻：0/);
    assert.deepEqual(await page.locator('.chloe-overview-videos th').allTextContents(),['视频','当前阶段','视频状态','处理状态','下一步']);
    assert.equal(await page.locator('.chloe-overview-task').count(),1);
    const pendingProgress = samples.working.videos.find(item=>item.progress['处理状态']!=='正常').progress;
    const task = page.locator('.chloe-overview-task');
    assert.equal(await task.locator('small').innerText(),[pendingProgress['视频编号'],pendingProgress['视频名称'],pendingProgress['处理状态']].join(' · '));
    assert.equal(await task.locator('p').count(),1);
    assert.equal(await task.locator('h3').innerText(),pendingProgress['当前问题']);
    assert.equal(await task.locator('p').innerText(),'下一步：'+pendingProgress['下一步']);
    assert.equal(await page.locator('.chloe-overview-videos tbody tr').count(),3);
    await page.screenshot({path:output+`/${width}-working.png`,fullPage:true});
    scenario = 'new'; await page.reload();
    await page.waitForFunction(()=>document.querySelector('.chloe-overview-fields')?.textContent.includes('待确定'));
    await page.reload(); await page.getByRole('heading',{name:'账号方向',exact:true}).waitFor();
    assert.deepEqual(await page.locator('.chloe-overview-fields dd').allTextContents(),['抖音','待确定','待确定']);
    scenario = 'working'; await page.reload();
    await page.getByText(samples.working.direction['目标人群'],{exact:true}).waitFor();
    long = true; await page.reload();
    await page.getByText('抖音、小红书',{exact:true}).waitFor();
    assert.deepEqual(await page.locator('.chloe-overview-metrics dd').allTextContents(),['3','2','0','1']);
    assert.equal(await page.locator('.chloe-overview-task').count(),2);
    const pendingBox = await page.locator('.chloe-overview-pending').boundingBox();
    const taskBoxes = await Promise.all((await page.locator('.chloe-overview-task').all()).map(el=>el.boundingBox()));
    assert.ok(taskBoxes.every(box=>Math.abs(box.width-pendingBox.width)<1 && Math.abs(box.x-pendingBox.x)<1));
    assert.ok(taskBoxes[1].y>=taskBoxes[0].y+taskBoxes[0].height,'pending cards each occupy a separate full row');
    assert.match(await page.locator('.chloe-overview-attention').innerText(),/待用户决定：1 · 受阻：1/);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
    for (const element of await page.locator('.chloe-overview, .chloe-overview-fields dd, .chloe-overview-task, .chloe-overview-videos').all()) {
      const box = await element.boundingBox(); assert.ok(box.x >= 0 && box.x+box.width <= width+1);
    }
    await page.screenshot({path:output+`/${width}-long.png`,fullPage:true});
    fail = true; await page.reload();
    await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
    assert.equal(await page.locator('.chloe-overview').count(),0);
    fail = false; long = false;
    await page.getByRole('button',{name:'重新读取',exact:true}).click();
    await page.getByText(samples.working.direction['目标人群'],{exact:true}).waitFor();
    for (const removed of ['overview','voices']) {
      await page.goto(server.resolvedUrls.local[0]+'#/examples/chloe/'+removed);
      await page.getByText('入口不存在。',{exact:false}).waitFor();
    }
    assert.deepEqual(errors,[]); assert.deepEqual(unexpected,[]);
    await page.close();
  }
  console.log('Chloe overview passed: template-based samples, empty/working/long/error-retry, desktop sizes, isolated GET-only APIs. Screenshots: '+output);
} finally { await browser.close(); await server.close(); }
