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
  'import json; from backend.chloe_overview import example_overview; print(json.dumps({s:example_overview(s) for s in ("new","working")}))'], {cwd:tool,encoding:'utf8'}));
const output = await mkdtemp('/private/tmp/chloe-overview-');
const server = await createServer({configFile:false,root:frontend,plugins:[react()],
  define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser = await chromium.launch({channel:'chrome',headless:true});
try {
  for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
    const page = await browser.newPage({viewport:{width,height}});
    const errors = [], unexpected = [];
    let fail = false, long = false;
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('**/api/**', route => {
      const url = new URL(route.request().url()), path = url.pathname;
      if (route.request().method() !== 'GET') unexpected.push(route.request().method()+' '+path);
      if (path === '/api/service') return route.fulfill({json:{version,ready:true}});
      if (path === '/api/task-monitor') return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
      if (path === '/api/workspaces') return route.fulfill({json:[{id:'chloe',name:'Chloe AI视频带货',view:'chloe-commerce',projects:[]}]});
      if (path === '/api/workspaces/chloe/account-overview') return route.fulfill({json:samples.new});
      if (path === '/api/examples/chloe/overview') {
        if (fail) return route.fulfill({status:503,json:{detail:'isolated example failure'}});
        const data = structuredClone(samples[url.searchParams.get('scenario')]);
        if (long) {
          data.identity['公开账号名'] = '超长账号名称'.repeat(18);
          data.direction['目标人群'] = 'LongUnbrokenExample'.repeat(35);
          data.connection['核对证据'] = '长段核对说明。'.repeat(30);
          data.videos[0].progress['下一步'] = 'VeryLongNextStep'.repeat(30);
        }
        return route.fulfill({json:data});
      }
      unexpected.push(path); return route.fulfill({status:404,json:{detail:'unexpected isolated request'}});
    });
    await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe');
    await page.getByRole('heading',{name:'账号名称待核实'}).waitFor();
    assert.equal(await page.locator('time').count(),1, 'one footer check status');
    assert.deepEqual(await page.locator('.chloe-overview-metrics dd').allTextContents(),['0','0','0','0']);
    assert.deepEqual(await page.locator('.chloe-overview-videos th').allTextContents(),['视频','当前阶段','制作状态','下一步']);
    await page.screenshot({path:output+`/${width}-actual-empty.png`,fullPage:true});
    await page.getByRole('link',{name:'查看账号概况演示'}).click();
    await page.getByRole('heading',{name:'Chloe 的通勤衣橱（演示）',exact:true}).waitFor();
    assert.deepEqual(await page.locator('.chloe-overview-metrics dd').allTextContents(),['3','1','1','0']);
    assert.equal(await page.locator('.chloe-overview-videos tbody tr').count(),3);
    await page.screenshot({path:output+`/${width}-working.png`,fullPage:true});
    await page.getByRole('button',{name:'新账号空白状态',exact:true}).click();
    await page.getByRole('heading',{name:'账号名称待核实'}).waitFor();
    assert.deepEqual(await page.locator('.chloe-overview-metrics dd').allTextContents(),['0','0','0','0']);
    await page.getByText('还没有视频项目。',{exact:false}).waitFor();
    await page.reload(); await page.getByRole('heading',{name:'账号名称待核实'}).waitFor();
    await page.screenshot({path:output+`/${width}-new.png`,fullPage:true});
    await page.getByRole('button',{name:'已有制作的示例',exact:true}).click();
    await page.getByRole('heading',{name:'Chloe 的通勤衣橱（演示）',exact:true}).waitFor();
    long = true; await page.reload();
    await page.getByRole('heading',{name:'超长账号名称'.repeat(18),exact:true}).waitFor();
    for (const label of ['人物、声音与制作约定','连接核对与发布约定']) await page.locator('summary',{hasText:label}).click();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
    for (const element of await page.locator('.chloe-overview, .chloe-overview-fields dd, .chloe-overview-videos').all()) {
      const box = await element.boundingBox(); assert.ok(box.x >= 0 && box.x+box.width <= width+1);
    }
    await page.screenshot({path:output+`/${width}-long.png`,fullPage:true});
    fail = true; await page.reload();
    await page.getByRole('button',{name:'重新读取',exact:true}).waitFor();
    assert.equal(await page.locator('.chloe-overview').count(),0);
    fail = false; long = false;
    await page.getByRole('button',{name:'重新读取',exact:true}).click();
    await page.getByRole('heading',{name:'Chloe 的通勤衣橱（演示）',exact:true}).waitFor();
    await page.getByRole('link',{name:'返回 Chloe',exact:true}).click();
    await page.getByRole('link',{name:'查看账号概况演示'}).waitFor();
    await page.getByRole('heading',{name:'账号名称待核实'}).waitFor();
    assert.deepEqual(await page.locator('.chloe-overview-metrics dd').allTextContents(),['0','0','0','0']);
    assert.deepEqual(errors,[]); assert.deepEqual(unexpected,[]);
    await page.close();
  }
  console.log('Chloe overview passed: template-based samples, empty/working/long/error-retry, desktop sizes, isolated GET-only APIs. Screenshots: '+output);
} finally { await browser.close(); await server.close(); }
