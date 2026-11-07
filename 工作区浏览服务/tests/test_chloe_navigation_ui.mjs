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
      if (path === '/api/workspaces/account-demo/shared-models') return route.fulfill({json:[]});
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
    await nav.getByRole('button',{name:'共用资产',exact:true}).click();
    const assetNav = page.getByRole('navigation',{name:'共用资产分类',exact:true});
    await assetNav.waitFor();
    assert.deepEqual(await assetNav.getByRole('button').allTextContents(),['AI 模特','服装','造型','场景','声音']);
    assert.equal(await assetNav.locator('[aria-current="page"]').textContent(),'AI 模特');
    for (const label of ['AI 模特','服装','造型','场景','声音']) {
      await assetNav.getByRole('button',{name:label,exact:true}).click();
      await page.waitForFunction(label=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent===label,label);
      const bounds = await assetNav.getByRole('button',{name:label,exact:true}).boundingBox();
      assert.ok(bounds.x >= 0 && bounds.x+bounds.width <= width+1);
    }
    assert.ok(page.url().endsWith('section=assets&asset=voices'));
    await page.reload(); await assetNav.waitFor();
    assert.equal(await assetNav.locator('[aria-current="page"]').textContent(),'声音');
    await page.goBack();
    await page.waitForFunction(()=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent==='场景');
    await assetNav.getByRole('button',{name:'AI 模特',exact:true}).focus();
    await page.keyboard.press('Enter');
    await page.getByText('暂无模特资料。建立模特资料后，每个模特会在这里显示为一张卡片。',{exact:true}).waitFor();
    assert.equal(await page.locator('.page-heading .breadcrumbs').count(),1);
    assert.equal(await page.locator('section[aria-label="共用资产"] > h2').count(),0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),true);
    await page.screenshot({path:output+`/${width}-assets.png`,fullPage:true});
    assert.equal(await page.getByRole('link',{name:'查看占位模特卡',exact:true}).count(),0);
    await page.goto(server.resolvedUrls.local[0]+'#/spaces/account-demo?section=assets&asset=models&example=model-card');
    await page.getByText('暂无模特资料。建立模特资料后，每个模特会在这里显示为一张卡片。',{exact:true}).waitFor();
    assert.equal(await page.locator('.asset-media-card').count(),0);
    await nav.getByRole('button',{name:'账号概况',exact:true}).click();
    await page.getByRole('heading',{name:'定位与当前进度',exact:true}).waitFor();
    assert.deepEqual(await page.locator('.chloe-overview h2').allTextContents(),['制作概况','账号方向','待处理事项','定位与当前进度']);
    assert.equal(await assetNav.count(),0);
    await page.getByRole('link',{name:'返回工作区',exact:true}).click();
    await nav.waitFor({state:'detached'});
    assert.equal(await page.getByRole('navigation',{name:'Chloe栏目'}).count(),0);
    await page.getByRole('link',{name:/普通资料区/}).click();
    await page.getByText('暂无项目。',{exact:true}).waitFor();
    assert.equal(await page.getByRole('navigation',{name:'Chloe栏目'}).count(),0);
    assert.deepEqual(errors,[]); assert.deepEqual(unexpected,[]);
    await page.close();
  }
  console.log('Chloe navigation passed: three desktop sizes, seven tabs and five asset categories, URL refresh/back, keyboard and space isolation. Screenshots: '+output);
} finally { await browser.close(); await server.close(); }
