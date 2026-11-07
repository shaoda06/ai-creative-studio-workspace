// Existing real UI components with isolated responses; never contacts production APIs.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(require.resolve('vite'));
const react = (await import(require.resolve('@vitejs/plugin-react'))).default;
const version = JSON.parse(await readFile(new URL('../frontend/package.json', import.meta.url))).version;
const server = await createServer({configFile:false,root:fileURLToPath(new URL('../frontend',import.meta.url)),plugins:[react()],define:{__APP_VERSION__:JSON.stringify(version)},server:{host:'127.0.0.1',port:0}});
await server.listen();
const browser = await chromium.launch({channel:'chrome',headless:true});
const projects = ['甲项目','乙项目'];
try {
  for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
    const page = await browser.newPage({viewport:{width,height}});
    const errors = [], unexpected = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('**/api/**', route => {
      const path = decodeURIComponent(new URL(route.request().url()).pathname);
      if (route.request().method() !== 'GET') { unexpected.push(path); return route.abort(); }
      if (path === '/api/service') return route.fulfill({json:{version,ready:true}});
      if (path === '/api/task-monitor') return route.fulfill({json:{tasks:[],local_tasks:[],remote_nodes:[],local_counts:{},history_updated_at:{}}});
      if (path === '/api/workspaces') return route.fulfill({json:[{id:'chloe',name:'示例空间',view:'chloe-commerce',project_layout:'nested',projects:projects.map(name=>({id:name,name}))}]});
      const match = /^\/api\/workspaces\/chloe\/contexts\/(甲项目|乙项目)\/(.*)$/.exec(path);
      if (match) {
        const [,name,endpoint] = match;
        if (endpoint === 'account-overview') return route.fulfill({json:{direction:{发布平台:name+'平台',目标人群:'待确定',内容风格:'待确定'},videos:[]}});
        if (endpoint === 'shared-voices' || endpoint === 'production-videos' || endpoint === 'publication-videos') return route.fulfill({json:[]});
        if (endpoint === 'shared-models') return route.fulfill({json:[{id:'M001',name:name+'模特',media:null,version:null,identity:{},features:{}}]});
      }
      unexpected.push(path); return route.fulfill({status:404,json:{detail:'unexpected fixture request'}});
    });
    await page.goto(server.resolvedUrls.local[0]+'#/spaces/chloe');
    await page.getByRole('heading',{name:'业务项目',exact:true}).waitFor();
    assert.equal(await page.getByRole('navigation',{name:'Chloe栏目'}).count(),0);
    await page.getByRole('link',{name:/01-乙项目|02-甲项目|01-甲项目/}).filter({hasText:'甲项目'}).click();
    await page.getByText('甲项目平台',{exact:true}).waitFor();
    await page.getByRole('button',{name:'共用资产',exact:true}).click();
    await page.getByText('M001 · 甲项目模特',{exact:true}).waitFor();
    const first = page.getByRole('link').filter({hasText:'M001 · 甲项目模特'});
    assert.ok(decodeURIComponent(await first.getAttribute('href')).includes('/contexts/甲项目?'));
    await page.getByRole('combobox',{name:'切换项目',exact:true}).click();
    await page.getByRole('option',{name:'乙项目',exact:true}).click();
    await page.getByText('乙项目平台',{exact:true}).waitFor();
    await page.getByRole('button',{name:'共用资产',exact:true}).click();
    await page.getByText('M001 · 乙项目模特',{exact:true}).waitFor();
    assert.equal(await page.getByText('M001 · 甲项目模特',{exact:true}).count(),0);
    await page.getByRole('button',{name:'视频制作',exact:true}).click();
    await page.getByRole('heading',{name:'乙项目',exact:true}).waitFor();
    assert.equal(await page.getByRole('navigation',{name:'Chloe栏目'}).count(),1);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1));
    await page.getByRole('link',{name:'返回项目列表',exact:true}).click();
    await page.getByRole('heading',{name:'业务项目',exact:true}).waitFor();
    assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
    await page.close();
  }
  console.log('PASS: project selection, scoped assets, cache isolation, production and return across three desktop sizes');
} finally { await browser.close(); await server.close(); }
