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
const assetLabels = ['AI 模特','发型','服装','配饰','场景','声音','参考视频','装配'];
const fixtureImage = name => ({kind:'image',name,key:name,url:'/api/assembly-fixture/'+name});
const fixtureAsset = (id,name,status='可用') => ({id,name,status,media:fixtureImage(id)});
const fixtureModels = [fixtureAsset('M001','模特甲'),fixtureAsset('M002','模特乙'),fixtureAsset('M003','制作中模特','制作中')];
const fixtureClothing = [fixtureAsset('O001','服装甲'),fixtureAsset('O002','制作中服装','制作中')];
const fixtureHair = [fixtureAsset('H001','发型甲'),fixtureAsset('H002','制作中发型','制作中')];
const fixtureScenes = [fixtureAsset('S001','背景甲'),fixtureAsset('S002','制作中背景','制作中')];
const fixtureVideo = {id:'RV001',name:'参考视频甲',status:'可用',coverUrl:fixtureImage('RV001').url};
const draftVideo = {id:'RV002',name:'待登记参考视频',status:'制作中',coverUrl:fixtureImage('RV002').url};
const fixtureLooks = [
  {id:'L001',name:'造型甲',status:'可用',images:[
    {purpose:'全身三视图原图',adopted:false,resource:'IMG-look',version:'V004',media:fixtureImage('L001-candidate')},
    {purpose:'全身三视图原图',adopted:true,resource:'IMG-look',version:'V002',media:fixtureImage('L001-adopted')},
  ]},
  {id:'L002',name:'制作中造型',status:'制作中',images:[
    {purpose:'全身三视图原图',adopted:true,resource:'IMG-look-draft',version:'V001',media:fixtureImage('L002-adopted')},
  ]},
];
const fixtureAccessories = Array.from({length:6},(_,i)=>({
  ...fixtureAsset(`C00${i+1}`,`配饰样例${i+1}`), type:i%2 === 0 ? '帽饰' : '包袋',
}));
fixtureAccessories.push({...fixtureAsset('C007','制作中配饰','制作中'), type:'首饰'});
try {
  for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
    const page = await browser.newPage({viewport:{width,height},permissions:['clipboard-read','clipboard-write']});
    const errors = [], unexpected = [];
    let showAssemblyFixtures = false;
    const refreshedAssets = new Map();
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (route.request().method() !== 'GET') unexpected.push(route.request().method()+' '+path);
      if (refreshedAssets.has(path)) return route.fulfill({json:await refreshedAssets.get(path)});
      if (['/api/workspaces/account-demo/production-videos','/api/workspaces/account-demo/publication-videos'].includes(path)) return route.fulfill({json:[]});
      if (path === '/api/workspaces/account-demo/reviews') return route.fulfill({json:{videos:[],conclusions:[],trials:[]}});
      if (path === '/api/workspaces/account-demo/resource-library') return route.fulfill({json:{items:[],owners:[],total:0,page:1,page_size:12}});
      if (path.startsWith('/api/assembly-fixture/')) {
        const width = path.endsWith('-front') ? 90 : 120;
        const height = /\/(O001|C003)$/.test(path) ? 240 : /-(front|body)$/.test(path) ? 120 : 100;
        return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#edf5ef"/></svg>`});
      }
      if (path === '/api/workspaces/account-demo/shared-models') return route.fulfill({json:showAssemblyFixtures ? fixtureModels : []});
      if (path === '/api/workspaces/account-demo/shared-models/M002') return route.fulfill({json:{id:'M002',name:'模特乙',images:[
        {purpose:'正面面部',adopted:true,resource:'IMG-M002-face',version:'V003',media:fixtureImage('M002-front')},
        {purpose:'全身三视图原图',adopted:false,resource:'IMG-M002-body',version:'V004',media:fixtureImage('M002-candidate')},
        {purpose:'全身三视图原图',adopted:true,resource:'IMG-M002-body',version:'V002',media:fixtureImage('M002-body')},
      ],looks:fixtureLooks}});
      if (path === '/api/workspaces/account-demo/shared-reference-videos') return route.fulfill({json:showAssemblyFixtures ? [fixtureVideo,draftVideo] : []});
      if (path === '/api/workspaces/account-demo/shared-reference-videos/RV001') return route.fulfill({json:{
        ...fixtureVideo,media:{kind:'video',name:fixtureVideo.name,key:'资源/参考视频原件.webm',url:'/component-samples/video.webm'},
      }});
      if (path === '/api/workspaces/account-demo/shared-scenes') return route.fulfill({json:showAssemblyFixtures ? fixtureScenes : []});
      if (path === '/api/workspaces/account-demo/shared-voices') return route.fulfill({json:[]});
      if (path === '/api/workspaces/account-demo/shared-hair') return route.fulfill({json:showAssemblyFixtures ? fixtureHair : []});
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
    await page.waitForFunction(()=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent==='参考视频');
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
    const checkRefreshedPicker = async (endpoint, button, name, emptyText, assets) => {
      const path = `/api/workspaces/account-demo/${endpoint}`;
      const refresh = Promise.withResolvers();
      refreshedAssets.set(path, refresh.promise);
      const request = page.waitForRequest(value=>new URL(value.url()).pathname===path);
      try {
        await choose(button).click();
        await dialog.waitFor();
        await request;
        assert.equal(await dialog.getByText(name,{exact:true}).count(),0);
        assert.ok(await confirm.isDisabled());
      } finally {
        refresh.resolve(assets.map(asset=>({...asset,status:'制作中'})));
      }
      await dialog.getByText(emptyText,{exact:true}).waitFor();
      await page.keyboard.press('Escape');
    };
    const reset = assetNav.getByRole('button',{name:'重置',exact:true});
    await summary.waitFor();
    assert.deepEqual(await summary.locator('dd').allTextContents(),['未选择','未选择','未选择','未选择']);
    assert.equal(await reset.count(),0);
    const exportArea = page.getByRole('region',{name:'导出',exact:true});
    const generateHandoff = exportArea.getByRole('button',{name:'生成',exact:true});
    const copyHandoff = exportArea.getByRole('button',{name:'复制',exact:true});
    const handoff = exportArea.locator('.chloe-assembly-export-template');
    await handoff.waitFor();
    assert.ok(await generateHandoff.isDisabled());
    assert.ok(await copyHandoff.isDisabled());
    const previews = page.locator('.chloe-assembly-main figure, .chloe-assembly-hair');
    const emptyPreviews = await previews.evaluateAll(items => items.map(item => {
      const {top,bottom,height} = item.getBoundingClientRect();
      return {top,bottom,height};
    }));
    const [emptyFace, emptyBody, emptyClothing, emptyHair] = emptyPreviews;
    assert.ok(emptyFace.height >= 230 && emptyBody.height >= 230);
    assert.ok(Math.abs(emptyFace.top-emptyClothing.top)<=1 && Math.abs(emptyFace.bottom-emptyClothing.bottom)<=1);
    assert.ok(Math.abs(emptyBody.top-emptyHair.top)<=1 && Math.abs(emptyBody.bottom-emptyHair.bottom)<=1);
    await choose('选择模特').click();
    const modelA = dialog.getByRole('button',{name:'选择M001 · 模特甲',exact:true});
    const modelB = dialog.getByRole('button',{name:'选择M002 · 模特乙',exact:true});
    await modelA.waitFor();
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).overflowY),'hidden');
    assert.ok(await confirm.isDisabled());
    assert.equal(await dialog.getByText('M003 · 制作中模特',{exact:true}).count(),0);
    await modelA.click();
    assert.equal(await modelA.getAttribute('aria-pressed'),'true');
    assert.equal(await modelA.locator('span').textContent(),'✓');
    await modelA.click();
    assert.equal(await modelA.getAttribute('aria-pressed'),'false');
    assert.ok(await confirm.isDisabled());
    await modelA.click();
    await dialog.getByRole('button',{name:'查看M001 · 模特甲大图',exact:true}).click();
    const zoom = page.locator('dialog.dialog-fullscreen');
    await zoom.waitFor();
    assert.equal(await zoom.getByRole('img').getAttribute('src'),'/api/assembly-fixture/M001');
    await page.keyboard.press('Escape');
    await zoom.waitFor({state:'hidden'});
    assert.equal(await modelA.getAttribute('aria-pressed'),'true');
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
    const clothingA = dialog.getByRole('button',{name:'选择O001 · 服装甲',exact:true});
    await clothingA.click();
    assert.equal(await dialog.getByText('O002 · 制作中服装',{exact:true}).count(),0);
    await confirm.click();
    const clothingImage = page.getByRole('img',{name:'服装图',exact:true});
    assert.equal(await clothingImage.getAttribute('src'),'/api/assembly-fixture/O001');
    await clothingImage.scrollIntoViewIfNeeded();
    await clothingImage.evaluate(image => image.decode());
    const modelImages = page.locator('.chloe-assembly-model-images img');
    for (const image of await modelImages.all()) {
      await image.scrollIntoViewIfNeeded();
      const metrics = await image.evaluate(async element => {
        await element.decode();
        const figure = element.closest('figure');
        const {paddingLeft,paddingRight} = getComputedStyle(figure);
        return {width:element.clientWidth,height:element.clientHeight,
          innerWidth:figure.clientWidth-parseFloat(paddingLeft)-parseFloat(paddingRight),
          ratio:element.naturalWidth/element.naturalHeight};
      });
      assert.ok(Math.abs(metrics.width-metrics.innerWidth)<=1);
      assert.ok(Math.abs(metrics.height-metrics.width/metrics.ratio)<=1);
    }
    const frames = await previews.evaluateAll(items => items.map(item => {
      const rect = item.getBoundingClientRect();
      return {left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom};
    }));
    const [faceFrame, bodyFrame, clothingFrame, hairSection] = frames;
    assert.ok(faceFrame.bottom < bodyFrame.top && faceFrame.right < clothingFrame.left);
    assert.ok(Math.abs(faceFrame.top-clothingFrame.top)<=1 && Math.abs(faceFrame.bottom-clothingFrame.bottom)<=1,
      `正面基础图和服装图上下对齐：${JSON.stringify(frames)}`);
    assert.ok(Math.abs(bodyFrame.top-hairSection.top)<=1 && Math.abs(bodyFrame.bottom-hairSection.bottom)<=1,
      `基础三视图和整个发型区上下对齐：${JSON.stringify(frames)}`);
    const modelWidth=faceFrame.right-faceFrame.left, clothingWidth=clothingFrame.right-clothingFrame.left;
    assert.ok(Math.abs(modelWidth/(modelWidth+clothingWidth)-0.3)<0.002);
    assert.ok(faceFrame.bottom-faceFrame.top > bodyFrame.bottom-bodyFrame.top);
    const [summaryBox, exportBox] = await Promise.all([summary.boundingBox(),exportArea.boundingBox()]);
    assert.ok(Math.abs(summaryBox.width-modelWidth)<=1 && Math.abs(exportBox.width-clothingWidth)<=1);
    for (const [label, src] of [['正面基础图','M002-front'],['基础三视图','M002-body'],['服装图','O001']]) {
      await choose(`查看${label}大图`).click();
      await zoom.waitFor();
      assert.equal(await zoom.getByRole('img').getAttribute('src'),`/api/assembly-fixture/${src}`);
      await page.keyboard.press('Escape');
      await zoom.waitFor({state:'hidden'});
    }
    await choose('选择服装').click();
    assert.equal(await clothingA.getAttribute('aria-pressed'),'true');
    await clothingA.click();
    assert.equal(await clothingA.getAttribute('aria-pressed'),'false');
    assert.ok(await confirm.isEnabled());
    await dialog.getByRole('button',{name:'关闭',exact:true}).click();
    assert.equal(await summary.locator('dd').nth(1).textContent(),'O001 · 服装甲');
    await choose('选择服装').click();
    await clothingA.click();
    await confirm.click();
    assert.equal(await summary.locator('dd').nth(1).textContent(),'未选择');
    assert.equal(await page.getByRole('img',{name:'服装图',exact:true}).count(),0);
    assert.ok(await generateHandoff.isDisabled());
    await choose('选择服装').click();
    await clothingA.click();
    await confirm.click();
    await generateHandoff.click();
    assert.doesNotMatch(await handoff.textContent(), /^(发型|配饰)：/m);
    await choose('选择发型').click();
    const hairChoice = dialog.getByRole('button',{name:'选择H001 · 发型甲',exact:true});
    await hairChoice.click();
    assert.equal(await dialog.getByText('H002 · 制作中发型',{exact:true}).count(),0);
    await confirm.click();
    assert.equal(await summary.locator('dd').nth(2).textContent(),'H001 · 发型甲');
    await choose('查看发型图大图').click();
    await zoom.waitFor();
    assert.equal(await zoom.getByRole('img').getAttribute('src'),'/api/assembly-fixture/H001');
    await page.keyboard.press('Escape');
    await zoom.waitFor({state:'hidden'});
    await choose('选择发型').click();
    assert.equal(await hairChoice.getAttribute('aria-pressed'),'true');
    await hairChoice.click();
    await confirm.click();
    assert.equal(await summary.locator('dd').nth(2).textContent(),'未选择');
    assert.equal(await page.getByRole('img',{name:'发型图',exact:true}).count(),0);
    await choose('选择发型').click();
    await hairChoice.click();
    await confirm.click();
    const accessories = page.getByRole('region',{name:'配饰选择',exact:true});
    const accessoryChoice = index => dialog.getByRole('button',{name:`选择${fixtureAccessories[index].id} · ${fixtureAccessories[index].name}`,exact:true});
    assert.equal(await accessories.getByRole('heading',{level:2}).textContent(),'配饰选择 0/5');
    await choose('添加配饰').click();
    await accessoryChoice(0).waitFor();
    assert.equal(await dialog.getByText('C007 · 制作中配饰',{exact:true}).count(),0);
    assert.ok(await confirm.isDisabled());
    await page.waitForFunction(() => Array.from(document.querySelectorAll('.chloe-accessory-columns img')).filter(image => image.naturalWidth > 0).length === 6);
    const [shortCard, tallCard, followingCard] = await Promise.all(['C001','C003','C004'].map(id =>
      dialog.locator('article').filter({has:page.getByRole('img',{name:id,exact:true})}).boundingBox()));
    assert.ok(shortCard.height < tallCard.height && followingCard.y < tallCard.y + tallCard.height);
    const filters = dialog.getByRole('group',{name:'按类型筛选'});
    const [filterBox, confirmBox] = await Promise.all([filters.boundingBox(),confirm.boundingBox()]);
    assert.ok(filterBox.x + filterBox.width <= confirmBox.x &&
      Math.abs(filterBox.y + filterBox.height / 2 - confirmBox.y - confirmBox.height / 2) <= 1);
    assert.equal(await dialog.getByRole('button',{name:'筛选',exact:true}).count(),0);
    if (height === 640) {
      const footerVisibility = await dialog.evaluate(element => {
        const filterBox = element.querySelector('fieldset');
        const visible = () => {
          const dialogBox = element.getBoundingClientRect();
          const bounds = filterBox.getBoundingClientRect();
          return bounds.top >= dialogBox.top && bounds.bottom <= dialogBox.bottom;
        };
        element.scrollTop = 0;
        const before = visible();
        element.scrollTop = 90;
        return {before, after:visible(), scrollTop:element.scrollTop};
      });
      assert.ok(footerVisibility.scrollTop > 0 && footerVisibility.before && footerVisibility.after);
    }
    await accessoryChoice(0).click();
    const bagFilter = filters.getByRole('checkbox',{name:'包袋',exact:true});
    const hatFilter = filters.getByRole('checkbox',{name:'帽饰',exact:true});
    assert.equal(await filters.getByRole('checkbox',{name:'首饰',exact:true}).count(),0);
    await bagFilter.check();
    assert.equal(await accessoryChoice(0).count(),0);
    assert.equal(await accessoryChoice(1).count(),1);
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择配饰 1/5');
    await hatFilter.check();
    assert.equal(await accessoryChoice(0).count(),1);
    await hatFilter.uncheck();
    await bagFilter.uncheck();
    for (let index=1; index<5; index++) {
      await accessoryChoice(index).click();
      assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),`选择配饰 ${index+1}/5`);
    }
    assert.ok(await accessoryChoice(5).isDisabled());
    await dialog.getByRole('button',{name:'查看C006 · 配饰样例6大图',exact:true}).click();
    await zoom.waitFor();
    await page.keyboard.press('Escape');
    await zoom.waitFor({state:'hidden'});
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择配饰 5/5');
    await accessoryChoice(4).click();
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择配饰 4/5');
    await accessoryChoice(5).click();
    await bagFilter.check();
    assert.equal(await accessoryChoice(0).count(),0);
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择配饰 5/5');
    await confirm.click();
    assert.equal(await accessories.getByRole('heading',{level:2}).textContent(),'配饰选择 5/5');
    assert.equal(await choose('添加配饰').count(),0);
    assert.deepEqual(await summary.locator('dt').allTextContents(),['模特','服装','发型','配饰 1','配饰 2','配饰 3','配饰 4','配饰 5']);
    assert.deepEqual(await summary.locator('dd').allTextContents(),['M002 · 模特乙','O001 · 服装甲','H001 · 发型甲',...[0,1,2,3,5].map(i=>`${fixtureAccessories[i].id} · ${fixtureAccessories[i].name}`)]);
    assert.equal(await handoff.textContent(),'点击「生成」，整理当前选择的造型制作交接词。');
    assert.ok(await copyHandoff.isDisabled());
    const emptyHandoffHeight = (await handoff.boundingBox()).height;
    await generateHandoff.click();
    const text = await handoff.textContent();
    for (const value of ['Chloe AI视频带货','模特：M002 · 模特乙','服装：O001 · 服装甲','发型：H001 · 发型甲',
      '按对象编号查找各自正式采用的参考图','造型面部三视图','全身定装三视图原图','遮面版']) assert.ok(text.includes(value),value);
    for (const i of [0,1,2,3,5]) assert.ok(text.includes(`${fixtureAccessories[i].id} · ${fixtureAccessories[i].name}`));
    assert.doesNotMatch(text,/IMG-|@V\d+|正面基础图|基础全身三视图|C005/);
    const textBox = await handoff.evaluate(element => ({
      height:element.getBoundingClientRect().height, border:getComputedStyle(element).borderTopWidth,
      fits:element.scrollHeight <= element.clientHeight && element.scrollWidth <= element.clientWidth,
    }));
    assert.ok(textBox.height > emptyHandoffHeight && textBox.fits);
    assert.equal(textBox.border,'1px');
    await copyHandoff.click();
    await page.waitForFunction(async expected => await navigator.clipboard.readText() === expected,text);
    await accessories.getByRole('img',{name:'C001',exact:true}).click();
    await zoom.waitFor();
    assert.equal(await zoom.getByRole('img').getAttribute('src'),'/api/assembly-fixture/C001');
    await page.keyboard.press('Escape');
    await zoom.waitFor({state:'hidden'});
    await choose('编辑配饰').click();
    await accessoryChoice(0).click();
    await dialog.getByRole('button',{name:'关闭',exact:true}).click();
    assert.equal(await accessories.getByRole('heading',{level:2}).textContent(),'配饰选择 5/5');
    await choose('编辑配饰').click();
    for (const index of [0,1,2,3,5]) await accessoryChoice(index).click();
    await confirm.click();
    assert.equal(await accessories.getByRole('heading',{level:2}).textContent(),'配饰选择 0/5');
    assert.equal(await choose('添加配饰').count(),1);
    const [resetBox, assemblyBox, tabBar] = await Promise.all([reset.boundingBox(),assetNav.getByRole('button',{name:'装配',exact:true}).boundingBox(),assetNav.boundingBox()]);
    assert.ok(resetBox.x+resetBox.width<assemblyBox.x && Math.abs(assemblyBox.x+assemblyBox.width-tabBar.x-tabBar.width)<=1);
    await reset.click();
    assert.equal(await handoff.textContent(),'选定模特和服装后可生成交接词，发型和配饰可选。');
    assert.ok(await copyHandoff.isDisabled());
    assert.deepEqual(await summary.locator('dd').allTextContents(),['未选择','未选择','未选择','未选择']);
    assert.equal(await page.locator('.chloe-assembly-main img').count(),0);
    assert.deepEqual(await accessories.getByRole('button').allTextContents(),['+添加配饰']);
    assert.equal(await reset.count(),0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),true);
    await checkRefreshedPicker('shared-clothing','选择服装','O001 · 服装甲','暂无可用服装。',fixtureClothing);

    const assemblyNav = page.getByRole('navigation',{name:'装配分类',exact:true});
    assert.deepEqual(await assemblyNav.getByRole('button').allTextContents(),['造型装配','视频装配']);
    await choose('选择模特').click();
    await dialog.getByRole('button',{name:'选择M002 · 模特乙',exact:true}).click();
    await confirm.click();
    await assemblyNav.getByRole('button',{name:'视频装配'}).click();
    assert.ok(page.url().endsWith('asset=assembly&assemblyTab=video'));
    assert.ok(await generateHandoff.isDisabled());
    await choose('选择参考视频').click();
    await dialog.getByRole('button',{name:'RV001 · 参考视频甲',exact:true}).waitFor();
    assert.equal(await dialog.getByText('待登记参考视频',{exact:false}).count(),0);
    await dialog.getByRole('button',{name:'RV001 · 参考视频甲',exact:true}).click();
    await confirm.click();
    const player = page.locator('video[aria-label="参考视频甲"]');
    await player.waitFor();
    await page.waitForFunction(()=>document.querySelector('video[aria-label="参考视频甲"]')?.readyState>=1);
    await choose('选择造型图').click();
    await dialog.getByRole('button',{name:'M002 · 模特乙',exact:true}).waitFor();
    assert.equal(await dialog.getByText('制作中模特',{exact:false}).count(),0);
    await dialog.getByRole('button',{name:'M002 · 模特乙',exact:true}).click();
    await dialog.getByRole('button',{name:'选择L001 · 造型甲',exact:true}).waitFor();
    assert.equal(await dialog.getByText('制作中造型',{exact:false}).count(),0);
    await dialog.getByRole('button',{name:'选择L001 · 造型甲',exact:true}).click();
    await page.keyboard.press('Escape');
    assert.ok(await generateHandoff.isDisabled());
    await choose('选择造型图').click();
    await dialog.getByRole('button',{name:'M002 · 模特乙',exact:true}).click();
    await dialog.getByRole('button',{name:'选择L001 · 造型甲',exact:true}).click();
    await confirm.click();
    assert.equal(await page.getByRole('img',{name:'全身定装三视图原图',exact:true}).getAttribute('src'),fixtureImage('L001-adopted').url);
    await generateHandoff.click();
    assert.match(await handoff.textContent(),/背景：沿用参考视频的场景/);
    await choose('选择背景').click();
    await dialog.getByRole('button',{name:'选择S001 · 背景甲',exact:true}).waitFor();
    assert.equal(await dialog.getByText('制作中背景',{exact:false}).count(),0);
    await dialog.getByRole('button',{name:'选择S001 · 背景甲',exact:true}).click();
    await confirm.click();
    await page.getByRole('textbox',{name:'额外要求（可选）'}).fill('保留开场动作。\n镜头稍慢。');
    assert.ok(await copyHandoff.isDisabled());
    await generateHandoff.click();
    const videoPrompt = await handoff.textContent();
    for (const text of ['RV001 · 参考视频甲','资源/参考视频原件.webm','M002 · 模特乙','L001 · 造型甲','IMG-look@V002','S001 · 背景甲','保留开场动作。\n镜头稍慢。']) {
      assert.ok(videoPrompt.includes(text), text);
    }
    await copyHandoff.click();
    assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replaceAll('\r\n','\n'),videoPrompt);
    const [videoBox, lookBox, promptBox, sceneBox] = await Promise.all([
      page.getByRole('region',{name:'参考视频选择'}).boundingBox(),page.getByRole('region',{name:'造型图选择'}).boundingBox(),
      exportArea.boundingBox(),page.getByRole('region',{name:'背景选择'}).boundingBox(),
    ]);
    assert.equal(videoBox.y,lookBox.y);
    assert.equal(promptBox.y,sceneBox.y);
    assert.equal(videoBox.x,promptBox.x);
    assert.equal(lookBox.x,sceneBox.x);
    assert.ok(videoBox.x+videoBox.width<lookBox.x && videoBox.y+videoBox.height<promptBox.y);
    assert.ok(sceneBox.x+sceneBox.width<=width+1);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),true);
    await assemblyNav.getByRole('button',{name:'造型装配'}).click();
    await player.waitFor({state:'detached'});
    assert.equal(await summary.locator('dd').first().textContent(),'M002 · 模特乙');
    await page.goBack();
    await player.waitFor();
    assert.equal(await handoff.textContent(),videoPrompt);
    await choose('清除背景').click();
    assert.ok(await copyHandoff.isDisabled());
    await generateHandoff.click();
    assert.match(await handoff.textContent(),/背景：沿用参考视频的场景/);
    await reset.click();
    assert.ok(await generateHandoff.isDisabled());
    assert.equal(await page.getByRole('textbox',{name:'额外要求（可选）'}).inputValue(),'');
    await checkRefreshedPicker('shared-scenes','选择背景','S001 · 背景甲','暂无可选背景。',fixtureScenes);
    await page.reload();
    await assemblyNav.getByRole('button',{name:'视频装配'}).waitFor();
    assert.equal(await assemblyNav.locator('[aria-current="page"]').textContent(),'视频装配');

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
