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
const frontend = fileURLToPath(new URL('../frontend/', import.meta.url));
const version = JSON.parse(await readFile(frontend+'package.json', 'utf8')).version;
const tool = fileURLToPath(new URL('../', import.meta.url));
const python = join(tool, '.venv', ...(process.platform === 'win32' ? ['Scripts', 'python.exe'] : ['bin', 'python']));
const emptyOverview = JSON.parse(execFileSync(python, ['-c', 'import json; from pathlib import Path; from backend.chloe_overview import account_overview; print(json.dumps(account_overview(Path("tests/fixtures/chloe-overview/new"))))'], {cwd:tool,encoding:'utf8'}));
const output = await mkdtemp(join(tmpdir(),'chloe-navigation-'));
const server = await createServer({configFile:false,root:frontend,plugins:[react()],
  define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser = await chromium.launch({channel:'chrome',headless:true});
const labels = ['账号概况','选品与商品','共用资产','视频制作','成片与发布','运营复盘','资源库'];
const assetLabels = ['AI 模特','发型','服装','配饰','场景','声音','装配'];
const fixtureImage = name => ({kind:'image',name,key:name,url:'/api/assembly-fixture/'+name});
const fixtureAsset = (id,name) => ({id,name,media:fixtureImage(id)});
const fixtureModels = [fixtureAsset('M001','模特甲'),fixtureAsset('M002','模特乙'),{id:'M003',name:'无采用图',media:null}];
const fixtureClothing = [fixtureAsset('O001','服装甲')];
const fixtureAccessories = [fixtureAsset('C001','配饰甲'),fixtureAsset('C002','配饰乙')];
try {
  for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
    const page = await browser.newPage({viewport:{width,height}});
    const errors = [], unexpected = [];
    let showAssemblyFixtures = false;
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('**/api/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (route.request().method() !== 'GET') unexpected.push(route.request().method()+' '+path);
      if (['/api/workspaces/account-demo/production-videos','/api/workspaces/account-demo/publication-videos'].includes(path)) return route.fulfill({json:[]});
      if (path === '/api/workspaces/account-demo/reviews') return route.fulfill({json:{videos:[],conclusions:[],trials:[]}});
      if (path === '/api/workspaces/account-demo/resource-library') return route.fulfill({json:{items:[],owners:[],total:0,page:1,page_size:12}});
      if (path.startsWith('/api/assembly-fixture/')) return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100"><rect width="120" height="100" fill="#edf5ef"/></svg>'});
      if (path === '/api/workspaces/account-demo/shared-models') return route.fulfill({json:showAssemblyFixtures ? fixtureModels : []});
      if (path === '/api/workspaces/account-demo/shared-models/M002') return route.fulfill({json:{id:'M002',name:'模特乙',images:[
        {purpose:'正面面部',adopted:true,media:fixtureImage('M002-front')},
        {purpose:'全身三视图原图',adopted:false,media:fixtureImage('M002-candidate')},
        {purpose:'全身三视图原图',adopted:true,media:fixtureImage('M002-body')},
      ]}});
      if (['/api/workspaces/account-demo/shared-voices','/api/workspaces/account-demo/shared-scenes',
        '/api/workspaces/account-demo/shared-hair'].includes(path)) return route.fulfill({json:[]});
      if (path === '/api/workspaces/account-demo/shared-accessories') return route.fulfill({json:showAssemblyFixtures ? fixtureAccessories : []});
      if (path === '/api/workspaces/account-demo/shared-clothing') return route.fulfill({json:showAssemblyFixtures ? fixtureClothing : []});
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
      const breadcrumb = page.getByRole('navigation',{name:'当前位置',exact:true});
      await breadcrumb.waitFor();
      assert.equal(await breadcrumb.count(),1);
      const expected = label==='共用资产' ? 'AI 模特' : label;
      await page.waitForFunction(expected=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent===expected,expected);
      assert.equal(await breadcrumb.evaluate(el=>getComputedStyle(el).cursor),'pointer');
      assert.equal(await breadcrumb.locator('[aria-current="page"]').evaluate(el=>getComputedStyle(el).cursor),'pointer');
      if (['账号概况','选品与商品','视频制作','成片与发布'].includes(label)) {
        await page.locator('main .panel').first().waitFor();
        const gap = await page.evaluate(()=>document.querySelector('main .panel').getBoundingClientRect().top-document.querySelector('.breadcrumbs').getBoundingClientRect().bottom);
        assert.ok(Math.abs(gap-20)<1, label+' breadcrumb-to-panel spacing is 20px');
      }
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
    assert.deepEqual(await assetNav.getByRole('button').allTextContents(),assetLabels);
    assert.equal(await assetNav.locator('[aria-current="page"]').textContent(),'AI 模特');
    assert.equal(await assetNav.evaluate(bar => {
      const row = bar.getBoundingClientRect();
      const tabs = [...bar.querySelectorAll('button')].map(button => button.getBoundingClientRect());
      const first = tabs[0], previous = tabs.at(-2), last = tabs.at(-1);
      return Math.abs(first.left - row.left) <= 1 && Math.abs(last.right - row.right) <= 1
        && tabs.every(tab => Math.abs(tab.top - first.top) <= 1)
        && last.left - previous.right > parseFloat(getComputedStyle(bar).columnGap) + 1;
    }),true,'装配单独贴右边，其他资产页签同一行靠左');
    for (const label of assetLabels) {
      await assetNav.getByRole('button',{name:label,exact:true}).click();
      await page.waitForFunction(label=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent===label,label);
      const bounds = await assetNav.getByRole('button',{name:label,exact:true}).boundingBox();
      assert.ok(bounds.x >= 0 && bounds.x+bounds.width <= width+1);
    }
    await page.getByRole('region',{name:'当前选择',exact:true}).waitFor();
    assert.ok(page.url().endsWith('section=assets&asset=assembly'));
    await page.reload(); await assetNav.waitFor();
    assert.equal(await assetNav.locator('[aria-current="page"]').textContent(),'装配');
    await page.getByRole('region',{name:'当前选择',exact:true}).waitFor();
    await page.goBack();
    await page.waitForFunction(()=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent==='声音');
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
    showAssemblyFixtures = true;
    await page.goto(server.resolvedUrls.local[0]+'#/spaces/account-demo?section=assets&asset=assembly');
    await page.reload();
    const summary = page.getByRole('region',{name:'当前选择',exact:true});
    const choose = name => page.getByRole('button',{name,exact:true});
    const dialog = page.getByRole('dialog');
    const confirm = dialog.getByRole('button',{name:'确认选择',exact:true});
    const reset = assetNav.getByRole('button',{name:'重置',exact:true});
    await summary.waitFor();
    assert.deepEqual(await summary.locator('dd').allTextContents(),['未选择','未选择','未选择']);
    assert.equal(await reset.count(),0);
    await choose('选择模特').click();
    const modelA = dialog.getByRole('button',{name:'M001 · 模特甲',exact:true});
    const modelB = dialog.getByRole('button',{name:'M002 · 模特乙',exact:true});
    await modelA.waitFor();
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).overflowY),'hidden');
    assert.ok(await confirm.isDisabled());
    assert.ok(await dialog.getByRole('button',{name:'M003 · 无采用图',exact:true}).isDisabled());
    await modelA.click();
    assert.equal(await modelA.getAttribute('aria-pressed'),'true');
    assert.equal(await modelA.locator('span').textContent(),'✓');
    await modelB.click();
    assert.equal(await modelA.getAttribute('aria-pressed'),'false');
    assert.equal(await modelB.getAttribute('aria-pressed'),'true');
    assert.equal(await summary.locator('dd').first().textContent(),'未选择');
    await confirm.click();
    assert.notEqual(await page.evaluate(()=>getComputedStyle(document.documentElement).overflowY),'hidden');
    assert.deepEqual(await assetNav.getByRole('button').allTextContents(),[...assetLabels.slice(0,-1),'重置','装配']);
    await page.getByRole('img',{name:'基础三视图',exact:true}).waitFor();
    assert.equal(await page.getByRole('img',{name:'正面基础图',exact:true}).getAttribute('src'),'/api/assembly-fixture/M002-front');
    assert.equal(await page.getByRole('img',{name:'基础三视图',exact:true}).getAttribute('src'),'/api/assembly-fixture/M002-body');
    await choose('选择服装').click();
    await dialog.getByRole('button',{name:'O001 · 服装甲',exact:true}).click();
    await confirm.click();
    assert.equal(await page.getByRole('img',{name:'服装图',exact:true}).getAttribute('src'),'/api/assembly-fixture/O001');
    const frames = await page.locator('.chloe-assembly-main figure').evaluateAll(items => items.map(item => {
      const rect = item.getBoundingClientRect();
      return {left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom};
    }));
    assert.ok(frames[0].bottom < frames[1].top && frames[0].right < frames[2].left);
    assert.ok(Math.abs(frames[0].top-frames[2].top)<=1 && Math.abs(frames[1].bottom-frames[2].bottom)<=1,
      `模特和服装的预览框上下对齐：${JSON.stringify(frames)}`);
    const modelWidth=frames[0].right-frames[0].left, clothingWidth=frames[2].right-frames[2].left;
    assert.ok(Math.abs(modelWidth/(modelWidth+clothingWidth)-0.3)<0.002);
    assert.ok(Math.abs(frames[2].bottom-frames[2].top-Math.min(480,Math.max(340,height/2)))<=1);
    const accessories = page.getByRole('region',{name:'配饰选择',exact:true});
    for (const asset of fixtureAccessories) {
      await choose('添加配饰').click();
      const card = dialog.getByRole('button',{name:`${asset.id} · ${asset.name}`,exact:true});
      await card.waitFor();
      assert.ok(await confirm.isDisabled());
      await card.click();
      await confirm.click();
      assert.equal(await accessories.getByRole('button').last().getAttribute('aria-label'),'添加配饰');
    }
    assert.deepEqual(await summary.locator('dt').allTextContents(),['模特','服装','配饰 1','配饰 2']);
    assert.deepEqual(await summary.locator('dd').allTextContents(),['M002 · 模特乙','O001 · 服装甲','C001 · 配饰甲','C002 · 配饰乙']);
    await choose('配饰 1 · C001 · 配饰甲').click();
    await dialog.getByRole('button',{name:'C002 · 配饰乙',exact:true}).click();
    await dialog.getByRole('button',{name:'关闭',exact:true}).click();
    assert.equal(await summary.locator('dd').nth(2).textContent(),'C001 · 配饰甲');
    const [resetBox, assemblyBox, tabBar] = await Promise.all([reset.boundingBox(),assetNav.getByRole('button',{name:'装配',exact:true}).boundingBox(),assetNav.boundingBox()]);
    assert.ok(resetBox.x+resetBox.width<assemblyBox.x && Math.abs(assemblyBox.x+assemblyBox.width-tabBar.x-tabBar.width)<=1);
    await reset.click();
    assert.deepEqual(await summary.locator('dd').allTextContents(),['未选择','未选择','未选择']);
    assert.equal(await page.locator('.chloe-assembly-main img').count(),0);
    assert.deepEqual(await accessories.getByRole('button').allTextContents(),['+添加配饰']);
    assert.equal(await reset.count(),0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),true);
    await nav.getByRole('button',{name:'账号概况',exact:true}).click();
    await page.getByRole('heading',{name:'作品进度',exact:true}).waitFor();
    assert.deepEqual(await page.locator('.chloe-overview h2').allTextContents(),['制作概况','账号方向','待处理事项','作品进度']);
    assert.equal(await assetNav.count(),0);
    await page.goto(server.resolvedUrls.local[0]+'#/');
    await nav.waitFor({state:'detached'});
    assert.equal(await page.getByRole('navigation',{name:'Chloe栏目'}).count(),0);
    await page.getByRole('link',{name:/普通资料区/}).click();
    await page.getByText('暂无进行中的项目。',{exact:true}).waitFor();
    assert.equal(await page.getByRole('navigation',{name:'Chloe栏目'}).count(),0);
    assert.deepEqual(errors,[]); assert.deepEqual(unexpected,[]);
    await page.close();
  }
  console.log('Chloe navigation passed: three desktop sizes, asset tabs, assembly selection and cancellation, approved image previews, accessory append, URL refresh/back, keyboard and isolation. Screenshots: '+output);
} finally { await browser.close(); await server.close(); }
