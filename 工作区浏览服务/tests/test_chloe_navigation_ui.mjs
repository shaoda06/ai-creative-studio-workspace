import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { mkdtemp, readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(require.resolve('vite'));
const react = (await import(require.resolve('@vitejs/plugin-react'))).default;
const frontend = fileURLToPath(new URL('../frontend/', import.meta.url));
const version = JSON.parse(await readFile(frontend+'package.json', 'utf8')).version;
const tool = fileURLToPath(new URL('../', import.meta.url));
const emptyOverview = JSON.parse(execFileSync(tool+'.venv/bin/python', ['-c', 'import json; from backend.chloe_overview import example_overview; print(json.dumps(example_overview("new")))'], {cwd:tool,encoding:'utf8'}));
const output = await mkdtemp('/private/tmp/chloe-navigation-');
const server = await createServer({configFile:false,root:frontend,plugins:[react()],
  define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser = await chromium.launch({channel:'chrome',headless:true});
const labels = ['账号概况','选品与商品','共用资产','视频制作','成片与发布','运营复盘','资源库'];
try {
  for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
    const page = await browser.newPage({viewport:{width,height}});
    const errors = [], unexpected = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('**/api/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (route.request().method() !== 'GET') unexpected.push(route.request().method()+' '+path);
      if (path === '/api/workspaces/account-demo/account-overview') return route.fulfill({json:emptyOverview});
      if (path === '/api/service') return route.fulfill({json:{version,ready:true}});
      if (path === '/api/task-monitor') return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
      if (path === '/api/workspaces') return route.fulfill({json:[
        {id:'account-demo',name:'Chloe AI视频带货',view:'chloe-commerce',projects:[]},
        {id:'other',name:'普通资料区',view:'files',projects:[]} ]});
      unexpected.push(path); return route.fulfill({status:404,json:{detail:'unexpected isolated request'}});
    });
    await page.goto(server.resolvedUrls.local[0]+'#/spaces/account-demo');
    const nav = page.getByRole('navigation',{name:'Chloe栏目'});
    await nav.waitFor();
    assert.deepEqual(await nav.getByRole('button').allTextContents(), labels);
    for (const label of labels) {
      await nav.getByRole('button',{name:label,exact:true}).click();
      await page.getByRole('region',{name:label,exact:true}).waitFor();
      assert.equal(await nav.locator('[aria-current="page"]').textContent(),label);
      const bounds = await nav.getByRole('button',{name:label,exact:true}).boundingBox();
      assert.ok(bounds.x >= 0 && bounds.x+bounds.width <= width+1);
    }
    await page.reload(); await nav.waitFor();
    assert.equal(await nav.locator('[aria-current="page"]').textContent(),'资源库');
    await page.goBack();
    await page.getByRole('region',{name:'运营复盘',exact:true}).waitFor();
    await nav.getByRole('button',{name:'账号概况',exact:true}).focus();
    await page.keyboard.press('Enter');
    await page.getByRole('region',{name:'账号概况',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),true);
    await page.screenshot({path:output+`/${width}.png`,fullPage:true});
    await page.getByRole('link',{name:'返回工作区',exact:true}).click();
    await nav.waitFor({state:'detached'});
    assert.equal(await page.getByRole('navigation',{name:'Chloe栏目'}).count(),0);
    await page.getByRole('link',{name:/普通资料区/}).click();
    await page.getByText('暂无项目。',{exact:true}).waitFor();
    assert.equal(await page.getByRole('navigation',{name:'Chloe栏目'}).count(),0);
    assert.deepEqual(errors,[]); assert.deepEqual(unexpected,[]);
    await page.close();
  }
  console.log('Chloe navigation passed: three desktop sizes, seven tabs, URL refresh/back, keyboard and space isolation. Screenshots: '+output);
} finally { await browser.close(); await server.close(); }
