import { chloeAssetResponse } from './chloe_asset_fixtures.mjs';
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
const assetLabels = ['AI 模特','发型','服装','配饰','场景','声音','姿态','参考视频','装配'];
const fixtureImage = name => ({kind:'image',name,key:name,url:'/api/assembly-fixture/'+name});
const fixtureAsset = (id,name,status='可用') => ({id,name,status,media:fixtureImage(id)});
const fixtureModels = [fixtureAsset('M001','模特甲'),fixtureAsset('M002','模特乙'),fixtureAsset('M003','制作中模特','制作中')];
const fixtureClothingAsset = (id,name,clothingForm,bodyArea,status) => ({
  ...fixtureAsset(id,name,status), clothingForm, bodyArea, reference:{resource:`IMG-${id}`,version:'V002'},
  ...(clothingForm === '套装' ? {outfitStyles:['未分类']} : {}),
});
const fixtureGarments = ['组合','裤装','裙装','上装','外套','连身装'].map((area,index) =>
  fixtureClothingAsset(`O00${index+3}`,`单件样例${index+1}`,'单件',area));
const fixtureClothing = [
  fixtureClothingAsset('O001','套装甲','套装',null),
  fixtureClothingAsset('O002','制作中套装','套装',null,'制作中'),
  ...fixtureGarments,
  fixtureClothingAsset('O009','制作中单件','单件','上装','制作中'),
  fixtureAsset('O010','旧服装'),
];
const fixtureHair = [fixtureAsset('H001','发型甲'),fixtureAsset('H002','制作中发型','制作中')];
const fixturePoses = ['站姿','坐姿'].flatMap(type => Array.from({length:type==='站姿' ? 16 : 1},(_,index)=>{
  const id = `${type}-${String(index+1).padStart(3,'0')}`;
  const name = `${id}样例`;
  const media = {...fixtureImage(name), url:'/api/assembly-fixture/pose-image',thumbnailUrl:'/api/assembly-fixture/pose-thumb'};
  return {id,name,type,category:type,status:'可用',media,description:'双脚平放，躯干直立。'.repeat(index===1 ? 500 : 1)};
}));
const fixtureScenes = [fixtureAsset('S001','背景甲'),fixtureAsset('S002','制作中背景','制作中')];
const fixtureVideo = {id:'RV001',name:'参考视频甲',status:'可用',coverUrl:fixtureImage('RV001').url,videoUrl:'/component-samples/video.webm'};
const draftVideo = {id:'RV002',name:'待登记参考视频',status:'制作中',coverUrl:fixtureImage('RV002').url};
const fixtureLooks = [
  {id:'L001',name:'造型甲',status:'可用',media:fixtureImage('L001-adopted'),images:[
    {purpose:'全身三视图原图',adopted:false,resource:'IMG-look',version:'V004',media:fixtureImage('L001-candidate')},
    {purpose:'全身三视图原图',adopted:true,resource:'IMG-look',version:'V002',media:fixtureImage('L001-adopted')},
    {purpose:'造型面部三视图',adopted:false,resource:'IMG-look-face',version:'V004',media:fixtureImage('L001-face-candidate')},
    {purpose:'造型面部三视图',adopted:true,resource:'IMG-look-face',version:'V002',media:fixtureImage('L001-face')},
    {purpose:'全身三视图遮面版',adopted:true,resource:'IMG-look-masked',version:'V003',media:fixtureImage('L001-masked')},
  ]},
  {id:'L002',name:'制作中造型',status:'制作中',media:fixtureImage('L002-adopted'),images:[
    {purpose:'造型面部三视图',adopted:true,resource:'IMG-look-draft-face',version:'V001',media:fixtureImage('L002-face')},
    {purpose:'全身三视图遮面版',adopted:true,resource:'IMG-look-draft-masked',version:'V001',media:fixtureImage('L002-masked')},
  ]},
];
const fixtureAccessories = Array.from({length:6},(_,i)=>({
  ...fixtureAsset(`C00${i+1}`,`配饰样例${i+1}`), type:i%2 === 0 ? '帽饰' : '包袋',
}));
fixtureAccessories.push({...fixtureAsset('C007','制作中配饰','制作中'), type:'首饰'});
const moreAccessories = Array.from({length:19}, (_, i) => ({
  ...fixtureAsset(`C${String(i+8).padStart(3,'0')}`, `分页配饰${i+8}`),
  type:i===5 ? '手表' : '帽饰',
}));
const moreVideos = Array.from({length:12}, (_, i) => ({
  ...fixtureVideo, id:`RV${String(i+3).padStart(3,'0')}`, name:`分页视频${i+3}`,
}));
try {
  for (const [width,height] of [[1280,640],[1366,768],[1920,1080]]) {
    const page = await browser.newPage({viewport:{width,height},permissions:['clipboard-read','clipboard-write']});
    const errors = [], unexpected = [];
    let showAssemblyFixtures = false;
    let testPaging = false;
    let unavailable = '';
    const clothing = fixtureClothing.map(card => ({...card}));
    const outfitStyles = ['未分类', ...Array.from({length:7}, (_, i)=>`备选${i+1}`)];
    let outfitWrites = 0;
    let rejectSimpleStyle = true;
    const refreshedAssets = new Map();
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('**/api/**', async route => {
      const url = route.request().url();
      const path = new URL(url).pathname;
      const assets = cards => route.fulfill({json:chloeAssetResponse(url, cards)});
      const method = route.request().method();
      if (path === '/api/workspaces/account-demo/shared-asset-search') {
        const prefix = new URL(url).searchParams.get('q');
        const matches = [
          {id:'O001',name:'套装甲',category:'套装',previewUrl:'/api/assembly-fixture/O001?hover=1',params:{asset:'clothing',clothingTab:'outfits',clothing:'O001'}},
          {id:'O003',name:'单件样例1',category:'单件',previewUrl:'/api/assembly-fixture/O003?hover=1',params:{asset:'clothing',clothingTab:'garments',clothing:'O003'}},
          {id:'O010',name:'旧服装',category:'单件',previewUrl:null,params:{asset:'clothing',clothingTab:'garments',clothing:'O010'}},
          {id:'RV001',name:'参考视频甲',category:'参考视频',params:{asset:'reference-videos',referenceVideo:'RV001'}},
          {id:'站姿-016',name:'站姿-016样例',category:'姿态',params:{asset:'poses',pose:'站姿-016'}},
          ...moreAccessories.map(({id,name,media})=>({
            id,name,category:'配饰',previewUrl:media.url,params:{asset:'accessories',accessory:id},
          })),
        ];
        return route.fulfill({json:matches.filter(({id})=>id.toLowerCase().startsWith(prefix))});
      }
      if (path === '/api/workspaces/account-demo/shared-clothing/styles') {
        if (method === 'POST') {
          const { style } = route.request().postDataJSON();
          if (style === '简约' && rejectSimpleStyle) {
            rejectSimpleStyle = false;
            return route.fulfill({status:503,json:{detail:'暂时无法新建风格'}});
          }
          outfitStyles.push(style);
        }
        if (method === 'PATCH' || method === 'DELETE') {
          const { style, name } = route.request().postDataJSON();
          if (name && outfitStyles.includes(name)) return route.fulfill({status:409,json:{detail:'该风格已存在'}});
          outfitStyles.splice(outfitStyles.indexOf(style),1,...(name ? [name] : []));
          for (const card of clothing) {
            if (!card.outfitStyles?.includes(style)) continue;
            const next = card.outfitStyles.flatMap(value => value !== style ? [value] : name ? [name] : []);
            card.outfitStyles = next.length ? next : ['未分类'];
          }
        }
        return route.fulfill({json:outfitStyles,status:method === 'POST' ? 201 : 200});
      }
      if (path === '/api/workspaces/account-demo/shared-clothing/O001/style' && method === 'PUT') {
        outfitWrites++;
        clothing[0].outfitStyles = route.request().postDataJSON().styles;
        return route.fulfill({json:{outfitStyles:clothing[0].outfitStyles}});
      }
      if (route.request().method() !== 'GET') unexpected.push(route.request().method()+' '+path);
      if (refreshedAssets.has(path)) return assets(await refreshedAssets.get(path));
      if (['/api/workspaces/account-demo/production-videos','/api/workspaces/account-demo/publication-videos'].includes(path)) return route.fulfill({json:[]});
      if (path === '/api/workspaces/account-demo/reviews') return route.fulfill({json:{videos:[],conclusions:[],trials:[]}});
      if (path === '/api/workspaces/account-demo/resource-library') return route.fulfill({json:{items:[],owners:[],total:0,page:1,page_size:12}});
      if (path.startsWith('/api/assembly-fixture/')) {
        const width = path.endsWith('-front') ? 90 : 120;
        const height = /\/pose-(thumb|image)$/.test(path) ? 160 : /\/(O001|C003)$/.test(path) ? 240 : /-(front|body)$/.test(path) ? 120
          : path.endsWith('/O006') ? 150 : /\/O00[3-8]$/.test(path) ? 90 : 100;
        return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#edf5ef"/></svg>`});
      }
      if (path === '/api/workspaces/account-demo/shared-models') return assets(showAssemblyFixtures ? fixtureModels : []);
      if (path === '/api/workspaces/account-demo/shared-models/M002/assembly-looks') return assets((testPaging
        ? [...fixtureLooks, ...Array.from({length:12}, (_, i)=>({...fixtureLooks[0],
          id:`L${String(i+3).padStart(3,'0')}`,name:`分页造型${i+3}`,
        }))] : fixtureLooks).filter(look=>look.status==='可用').map(look=>({...look,
          face:look.images.find(image=>image.adopted && image.purpose==='造型面部三视图'),
          masked:look.images.find(image=>image.adopted && image.purpose==='全身三视图遮面版'),
        })));
      if (path === '/api/workspaces/account-demo/shared-models/M002') return route.fulfill({json:{id:'M002',name:'模特乙',images:[
        {purpose:'正面面部',adopted:true,resource:'IMG-M002-face',version:'V003',media:fixtureImage('M002-front')},
        {purpose:'全身三视图原图',adopted:false,resource:'IMG-M002-body',version:'V004',media:fixtureImage('M002-candidate')},
        {purpose:'全身三视图原图',adopted:true,resource:'IMG-M002-body',version:'V002',media:fixtureImage('M002-body')},
      ],looks:fixtureLooks}});
      if (path === '/api/workspaces/account-demo/shared-reference-videos') return assets(testPaging
        ? [fixtureVideo,draftVideo,...moreVideos] : showAssemblyFixtures ? [fixtureVideo,draftVideo] : []);
      const video = [fixtureVideo,moreVideos.at(-1)].find(item=>path===`/api/workspaces/account-demo/shared-reference-videos/${item.id}`);
      if (video) return route.fulfill({json:{
        ...video,media:{kind:'video',name:video.name,key:'资源/参考视频原件.webm',url:'/component-samples/video.webm'},
      }});
      if (path === '/api/workspaces/account-demo/shared-scenes') return assets(showAssemblyFixtures ? fixtureScenes : []);
      if (path === '/api/workspaces/account-demo/shared-voices') return assets([]);
      if (path === '/api/workspaces/account-demo/shared-poses') return assets(fixturePoses);
      if (path === '/api/workspaces/account-demo/shared-hair') return assets(showAssemblyFixtures ? fixtureHair : []);
      if (path === '/api/workspaces/account-demo/shared-accessories') return assets(testPaging
        ? [...fixtureAccessories,...moreAccessories].map(item=>item.id===unavailable ? {...item,status:'制作中'} : item)
        : showAssemblyFixtures ? fixtureAccessories : []);
      if (path === '/api/workspaces/account-demo/shared-accessories/C024') return route.fulfill({json:{
        id:'C024',name:'分页配饰24',description:'分页回退验证',type:'帽饰',images:[],
        sections:['关联资料','当前采用','采用变更','执行记录','输入记录','输出记录','审阅记录','返修记录']
          .map(heading=>({heading,empty:true})),
      }});
      if (path === '/api/workspaces/account-demo/shared-clothing') return assets(showAssemblyFixtures ? clothing : []);
      if (path === '/api/workspaces/account-demo/shared-clothing/O001') return route.fulfill({json:{
        id:'O001',name:'套装甲',description:'隔离测试套装',clothingForm:'套装',outfitSource:'合成',outfitStyles:clothing[0].outfitStyles,composition:'开衫叠穿上衣',images:[],
        sections:['关联资料','当前采用','采用变更','执行记录','输入记录','输出记录','审阅记录','返修记录'].map(heading=>({heading,empty:true})),
      }});
      if (path === '/api/workspaces/account-demo/shared-clothing/O003') return route.fulfill({json:{
        ...clothing.find(card=>card.id==='O003'),description:'隔离测试单件',images:[],
        sections:['关联资料','当前采用','采用变更','执行记录','输入记录','输出记录','审阅记录','返修记录'].map(heading=>({heading,empty:true})),
      }});
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
    await page.getByRole('heading',{name:'单件选择 0/5',exact:true}).waitFor();
    assert.ok(page.url().endsWith('section=assets&asset=assembly'));
    await page.reload(); await assetNav.waitFor();
    assert.equal(await assetNav.locator('[aria-current="page"]').textContent(),'装配');
    await page.getByRole('heading',{name:'单件选择 0/5',exact:true}).waitFor();
    await page.goBack();
    await page.waitForFunction(()=>document.querySelector('.breadcrumbs [aria-current="page"]')?.textContent==='参考视频');
    await page.getByText('暂无参考视频。', {exact:true}).waitFor();
    assert.equal(await assetNav.locator('[aria-current="page"]').textContent(),'参考视频');
    await assetNav.getByRole('button',{name:'姿态',exact:true}).click();
    const poseFilters = page.getByRole('group',{name:'按分类筛选',exact:true});
    const firstPose = page.getByRole('link',{name:'站姿-001 · 站姿-001样例',exact:true});
    await firstPose.waitFor();
    const poseGrid = page.locator('.chloe-pose-grid');
    assert.equal(await poseGrid.getByRole('link').count(),15);
    const rowTops = await poseGrid.getByRole('link').evaluateAll(cards=>cards.slice(0,6).map(card=>card.getBoundingClientRect().top));
    assert.ok(rowTops.slice(0,5).every(top=>top===rowTops[0]) && rowTops[5]>rowTops[0]);
    const poseImage = firstPose.getByRole('img');
    assert.equal(await poseImage.getAttribute('src'),'/api/assembly-fixture/pose-thumb');
    await firstPose.click();
    const poseDetails = page.getByRole('dialog',{name:'站姿-001 · 站姿-001样例',exact:true});
    await poseDetails.waitFor();
    const poseInfo = poseDetails.getByRole('region',{name:'姿态信息',exact:true});
    const poseText = poseDetails.getByRole('region',{name:'定姿文字',exact:true});
    assert.deepEqual(await poseInfo.locator('dd').allTextContents(),['站姿-001','站姿-001样例','站姿']);
    assert.equal(await poseText.locator('.chloe-pose-text').innerText(),'双脚平放，躯干直立。');
    const centeredPose = poseDetails.getByRole('img',{name:'站姿-001样例',exact:true});
    await centeredPose.evaluate(image=>image.decode());
    const [left, middle, right] = await Promise.all([poseInfo.boundingBox(),centeredPose.boundingBox(),poseText.boundingBox()]);
    assert.ok(left.x+left.width <= middle.x && middle.x+middle.width <= right.x && right.x+right.width <= width+1);
    assert.ok(Math.abs(left.width-right.width)<1);
    assert.ok(Math.abs(left.height-right.height)<1 && Math.abs(left.height-middle.height)<1);
    assert.ok(Math.abs(middle.width/middle.height-3/4)<0.01);
    assert.ok(Math.abs((middle.x+middle.width/2)-(left.x+right.x+right.width)/2)<1);
    assert.equal(await poseDetails.evaluate(dialog => {
      const fits = element => element.scrollHeight <= element.clientHeight+1;
      return fits(dialog) && [...dialog.querySelectorAll('.chloe-pose-detail>*,.chloe-pose-text')].every(fits);
    }),true);
    await poseText.getByRole('button',{name:'复制',exact:true}).click();
    await page.waitForFunction(async()=>await navigator.clipboard.readText()==='双脚平放，躯干直立。');
    await centeredPose.click();
    const posePreview = page.getByRole('dialog',{name:'站姿-001样例',exact:true});
    assert.equal(await posePreview.getByRole('img').getAttribute('src'),'/api/assembly-fixture/pose-image');
    await page.keyboard.press('Escape');
    await posePreview.waitFor({state:'hidden'});
    await poseDetails.waitFor();
    await page.keyboard.press('Escape');
    await poseDetails.waitFor({state:'hidden'});
    await page.getByRole('link',{name:'站姿-002 · 站姿-002样例',exact:true}).click();
    const longPose = page.getByRole('dialog',{name:'站姿-002 · 站姿-002样例',exact:true});
    await longPose.waitFor();
    assert.equal(await longPose.evaluate(dialog => {
      const text = dialog.querySelector('.chloe-pose-text');
      text.scrollTop = 120;
      const image = dialog.querySelector('.chloe-pose-picture');
      return text.scrollTop>0 && dialog.scrollHeight<=dialog.clientHeight+1 && image.scrollHeight<=image.clientHeight+1;
    }),true);
    await longPose.getByRole('button',{name:'关闭',exact:true}).click();
    const nextPosePage = page.getByRole('button',{name:'下一页',exact:true});
    await nextPosePage.click();
    await page.getByRole('heading',{name:'站姿-016 · 站姿-016样例',exact:true}).waitFor();
    await poseFilters.getByRole('checkbox',{name:'坐姿',exact:true}).check();
    await page.getByRole('heading',{name:'坐姿-001 · 坐姿-001样例',exact:true}).waitFor();
    assert.equal(await firstPose.count(),0);
    assert.equal(await nextPosePage.count(),0);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
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
    await assetNav.getByRole('button',{name:'服装',exact:true}).click();
    const clothingNav = page.getByRole('navigation',{name:'服装分类',exact:true});
    const outfitTab = clothingNav.getByRole('button',{name:'套装',exact:true});
    const garmentsTab = clothingNav.getByRole('button',{name:'单件',exact:true});
    const styleFilter = page.getByRole('group',{name:'按风格筛选',exact:true});
    await styleFilter.getByRole('checkbox',{name:'备选7',exact:true}).waitFor();
    assert.deepEqual(await styleFilter.locator('label').allTextContents(),outfitStyles);
    assert.deepEqual(await styleFilter.locator('.status-badge').allTextContents(),outfitStyles);
    assert.equal(await styleFilter.locator('.status-gray').textContent(),'未分类');
    assert.equal(await outfitTab.getAttribute('aria-current'),'page');
    const searchField = assetNav.getByRole('searchbox',{name:'搜索共用资产编号',exact:true});
    const searchResults = page.getByRole('region',{name:'资产搜索结果',exact:true});
    const referenceVideoBounds = await assetNav.getByRole('button',{name:'参考视频',exact:true}).boundingBox();
    const searchBounds = await searchField.boundingBox();
    assert.ok(searchBounds.x >= referenceVideoBounds.x + referenceVideoBounds.width &&
      searchBounds.x - (referenceVideoBounds.x + referenceVideoBounds.width) <= 28 &&
      Math.abs(searchBounds.y - referenceVideoBounds.y) < 14);
    await searchField.fill('套装甲');
    await searchResults.getByText('未找到匹配的资产编号。',{exact:true}).waitFor();
    await searchField.fill(' o00 ');
    const garmentResult = searchResults.getByRole('link',{name:/^O003 · 单件样例1/});
    await garmentResult.waitFor();
    assert.equal(await searchResults.getByRole('link').count(),2);
    const hoverPreview = page.locator('.chloe-asset-search-preview');
    assert.equal(await hoverPreview.count(),0);
    for (const [result, assetId] of [[searchResults.getByRole('link',{name:/^O001 · 套装甲/}),'O001'],[garmentResult,'O003']]) {
      await result.hover();
      await hoverPreview.evaluate(image=>image.decode());
      assert.equal(await hoverPreview.getAttribute('src'),`/api/assembly-fixture/${assetId}?hover=1`);
      const [row, popup, preview] = await Promise.all([result.boundingBox(),searchResults.boundingBox(),hoverPreview.boundingBox()]);
      assert.ok(Math.abs(preview.y-row.y)<=1 && preview.x>popup.x+popup.width && preview.x+preview.width<=width+1);
      assert.ok(Math.abs(searchBounds.width-popup.width)<=1 && Math.abs(preview.width-popup.width)<=1);
      const ratio = await hoverPreview.evaluate(image=>image.naturalWidth/image.naturalHeight);
      assert.ok(Math.abs(preview.height-preview.width/ratio)<=1);
    }
    await searchField.hover();
    await hoverPreview.waitFor({state:'detached'});
    await searchField.fill('O010');
    const noCoverResult = searchResults.getByRole('link',{name:/^O010 · 旧服装/});
    await noCoverResult.hover();
    assert.equal(await hoverPreview.count(),0);
    await searchField.fill('C0');
    const scrolledResult = searchResults.getByRole('link',{name:/^C024 ·/});
    await scrolledResult.hover();
    await hoverPreview.evaluate(image=>image.decode());
    assert.ok(await searchResults.evaluate(list=>list.scrollTop>0));
    assert.ok(Math.abs((await hoverPreview.boundingBox()).y-(await scrolledResult.boundingBox()).y)<=1);
    await searchField.fill('O003');
    await garmentResult.click();
    await page.getByText('隔离测试单件',{exact:true}).waitFor();
    await page.getByRole('link',{name:'返回服装列表',exact:true}).click();
    const libraryFilter = page.getByRole('group',{name:'按部位筛选',exact:true});
    const clothingLinks = page.locator('.chloe-assets-content').getByRole('link',{name:/^O\d+ ·/});
    await libraryFilter.waitFor();
    assert.deepEqual(await clothingNav.getByRole('button').allTextContents(),['套装','单件']);
    assert.equal(await garmentsTab.getAttribute('aria-current'),'page');
    assert.equal(await clothingLinks.count(),8);
    assert.equal(await clothingLinks.getByText('O010 · 旧服装',{exact:true}).count(),1);
    await libraryFilter.getByRole('checkbox',{name:'组合',exact:true}).check();
    assert.deepEqual(await clothingLinks.getAttribute('aria-label'),'O003 · 单件样例1');
    await libraryFilter.getByRole('checkbox',{name:'裤装',exact:true}).check();
    await clothingLinks.nth(1).waitFor();
    assert.equal(await clothingLinks.count(),2);
    await outfitTab.click();
    await libraryFilter.waitFor({state:'detached'});
    const selectStyle = page.getByRole('button',{name:'修改 O001 的风格',exact:true});
    const styleCard = page.locator('article.asset-media-card').filter({has:selectStyle});
    const currentStyle = styleCard.locator('.chloe-outfit-style-current .status-badge');
    const styleMenu = page.getByRole('group',{name:'修改 O001 的风格',exact:true});
    const findStyle = styleMenu.getByRole('searchbox',{name:'输入风格名称',exact:true});
    await currentStyle.filter({hasText:/^未分类$/}).waitFor();
    assert.equal(await page.getByRole('button',{name:'新增风格',exact:true}).count(),0);
    assert.equal(await clothingLinks.count(),2);
    assert.equal(await selectStyle.evaluate(control=>{
      const card = control.closest('article.asset-media-card');
      const current = card.querySelector('.chloe-outfit-style-current').getBoundingClientRect();
      return Boolean(card.querySelector('h3 a')) && current.top >= card.querySelector('.cover').getBoundingClientRect().bottom &&
        control.getBoundingClientRect().top > current.bottom;
    }),true);
    const unused = styleFilter.getByRole('checkbox',{name:'备选2',exact:true});
    await unused.check();
    await page.getByText('暂无符合所选风格的套装。',{exact:true}).waitFor();
    await unused.uncheck();
    await selectStyle.click();
    const [styleCover, styleTrigger, stylePopup] = await Promise.all([
      styleCard.locator('.cover').boundingBox(), selectStyle.boundingBox(), styleMenu.boundingBox(),
    ]);
    assert.ok([styleTrigger, stylePopup].every(box =>
      Math.abs(box.width - styleCover.width) <= 1 && Math.abs(box.x - styleCover.x) <= 1));
    const applyStyles = styleMenu.getByRole('button',{name:'应用',exact:true});
    const createStyle = styleMenu.getByRole('button',{name:'新建',exact:true});
    assert.equal(await applyStyles.isDisabled(),true);
    await findStyle.fill('通勤');
    await createStyle.click();
    const chooseCommute = styleMenu.getByRole('checkbox',{name:'通勤',exact:true});
    await chooseCommute.waitFor();
    assert.ok(await chooseCommute.isChecked());
    assert.equal(await currentStyle.textContent(),'未分类');
    assert.equal(outfitWrites,0);
    await findStyle.press('Escape');
    await styleMenu.waitFor({state:'hidden'});
    const commute = styleFilter.getByRole('checkbox',{name:'通勤',exact:true});
    const unclassified = styleFilter.getByRole('checkbox',{name:'未分类',exact:true});
    await commute.waitFor();
    await selectStyle.click();
    await findStyle.fill('通勤');
    assert.equal(await styleMenu.getByRole('checkbox').count(),1);
    assert.equal(await styleMenu.getByRole('button',{name:/^新建/}).count(),0);
    assert.equal(await applyStyles.isDisabled(),true);
    assert.equal(await chooseCommute.isChecked(),false);
    await chooseCommute.check();
    await findStyle.fill('备选1');
    await styleMenu.getByRole('checkbox',{name:'备选1',exact:true}).check();
    await findStyle.fill('简约');
    assert.equal(await styleMenu.getByRole('checkbox').count(),0);
    await createStyle.click();
    const createStyleError = page.getByRole('alert').filter({hasText:'暂时无法新建风格'});
    await createStyleError.waitFor();
    assert.equal(await findStyle.inputValue(),'简约');
    assert.equal(outfitWrites,0);
    await createStyle.click();
    const chooseSimple = styleMenu.getByRole('checkbox',{name:'简约',exact:true});
    await chooseSimple.waitFor();
    assert.ok(await chooseSimple.isChecked());
    assert.equal(await currentStyle.textContent(),'未分类');
    assert.equal(outfitWrites,0);
    await applyStyles.click();
    await currentStyle.filter({hasText:/^简约$/}).waitFor();
    assert.deepEqual(await currentStyle.allTextContents(),['备选1','通勤','简约']);
    assert.deepEqual(await styleFilter.locator('label').allTextContents(),outfitStyles);
    assert.equal(outfitWrites,1);
    await createStyleError.getByRole('button',{name:'关闭通知'}).click();
    assert.equal(await currentStyle.filter({hasText:/^简约$/}).getAttribute('class'),
      await currentStyle.filter({hasText:/^备选1$/}).getAttribute('class'));
    assert.notEqual(await currentStyle.filter({hasText:/^简约$/}).getAttribute('class'),
      await currentStyle.filter({hasText:/^通勤$/}).getAttribute('class'));
    const simple = styleFilter.getByRole('checkbox',{name:'简约',exact:true});
    await styleFilter.getByText('简约',{exact:true}).click();
    assert.ok(await simple.isChecked());
    await clothingLinks.nth(1).waitFor({state:'detached'});
    assert.equal(await clothingLinks.getAttribute('aria-label'),'O001 · 套装甲');
    await simple.uncheck();
    await selectStyle.click();
    assert.deepEqual(await styleMenu.locator('label').allTextContents(),outfitStyles);
    assert.equal(await findStyle.evaluate(el => document.activeElement === el &&
      parseFloat(getComputedStyle(el).outlineOffset) < 0),true);
    for (const name of ['通勤','备选1','简约']) {
      const badgeClass = await currentStyle.filter({hasText:name}).getAttribute('class');
      for (const group of [styleMenu,styleFilter]) {
        assert.equal(await group.locator('.status-badge').filter({hasText:name}).getAttribute('class'),badgeClass);
      }
    }
    await styleMenu.getByRole('checkbox',{name:'备选1',exact:true}).uncheck();
    await styleMenu.getByRole('checkbox',{name:'简约',exact:true}).uncheck();
    await styleMenu.getByRole('button',{name:'应用',exact:true}).click();
    await currentStyle.filter({hasText:/^简约$/}).waitFor({state:'detached'});
    await commute.check();
    await clothingLinks.nth(1).waitFor({state:'detached'});
    assert.equal(await clothingLinks.getAttribute('aria-label'),'O001 · 套装甲');
    await unclassified.check();
    await clothingLinks.nth(1).waitFor();
    await commute.uncheck();
    await unclassified.uncheck();
    await clothingLinks.nth(1).waitFor();
    await page.getByRole('link',{name:'O001 · 套装甲',exact:true}).click();
    await page.getByText('隔离测试套装',{exact:true}).waitFor();
    const clothingInfo = page.getByRole('region',{name:'服装信息',exact:true});
    assert.deepEqual(await clothingInfo.locator('dt').allTextContents(),['服装名称','服装形态','套装来源','风格','服装说明','组成与穿法']);
    assert.deepEqual(await clothingInfo.locator('dd').allTextContents(),['套装甲','套装','合成','通勤','隔离测试套装','开衫叠穿上衣']);
    await page.getByRole('link',{name:'返回服装列表',exact:true}).click();
    assert.ok(page.url().endsWith('asset=clothing&clothingTab=outfits'));
    await outfitTab.waitFor();
    assert.equal(await outfitTab.getAttribute('aria-current'),'page');
    await page.reload();
    await outfitTab.waitFor();
    await currentStyle.filter({hasText:/^通勤$/}).waitFor();
    assert.equal(await currentStyle.textContent(),'通勤');
    assert.equal(await outfitTab.getAttribute('aria-current'),'page');
    await garmentsTab.click();
    await libraryFilter.waitFor();
    assert.equal(await clothingLinks.count(),8);
    await searchField.fill('站姿-016');
    await searchResults.getByRole('link',{name:/^站姿-016 · 站姿-016样例/}).click();
    const offPagePose = page.getByRole('dialog',{name:'站姿-016 · 站姿-016样例',exact:true});
    await offPagePose.waitFor();
    await offPagePose.getByRole('button',{name:/关闭/}).click();
    await searchField.fill('RV001');
    await searchResults.getByRole('link',{name:/^RV001 · 参考视频甲/}).click();
    await page.getByRole('link',{name:'返回参考视频列表',exact:true}).waitFor();
    await page.goto(server.resolvedUrls.local[0]+'#/spaces/account-demo?section=assets&asset=assembly');
    await page.reload();
    const summary = page.getByRole('region',{name:'当前选择',exact:true});
    const choose = name => page.getByRole('button',{name,exact:true});
    const dialog = page.getByRole('dialog');
    const confirm = dialog.getByRole('button',{name:'确认选择',exact:true});
    const assemblyNav = page.getByRole('navigation',{name:'装配分类',exact:true});
    const assemblyNavigation = page.locator('.chloe-assembly-navigation');
    const reset = assemblyNavigation.getByRole('button',{name:'重置',exact:true});
    const exportArea = page.getByRole('region',{name:'导出',exact:true});
    const generateHandoff = exportArea.getByRole('button',{name:'生成',exact:true});
    const copyHandoff = exportArea.getByRole('button',{name:'复制',exact:true});
    const handoff = exportArea.locator('.chloe-assembly-export-template');
    const outfitInfo = page.getByRole('region',{name:'导出信息',exact:true});
    const outfitExport = page.getByRole('region',{name:'导出文字',exact:true});
    const outfitGenerate = outfitExport.getByRole('button',{name:'生成',exact:true});
    const outfitHandoff = outfitExport.locator('.chloe-assembly-export-template');
    await assemblyNav.waitFor();
    assert.deepEqual(await assemblyNav.getByRole('button').allTextContents(),['套装装配','造型装配','姿态装配','视频装配']);
    assert.equal(await assemblyNav.locator('[aria-current="page"]').textContent(),'套装装配');
    const [resetBox, lastTabBox, navBox] = await Promise.all([
      reset.boundingBox(), assemblyNav.getByRole('button',{name:'视频装配',exact:true}).boundingBox(), assemblyNavigation.boundingBox(),
    ]);
    assert.ok(lastTabBox.x+lastTabBox.width<resetBox.x);
    assert.ok(Math.abs(resetBox.x+resetBox.width-navBox.x-navBox.width)<=1);
    assert.ok(Math.abs(resetBox.y+resetBox.height/2-lastTabBox.y-lastTabBox.height/2)<=2);
    const garmentCount = count => page.getByRole('heading',{name:`单件选择 ${count}/5`,exact:true});
    const pickerCount = (label,count,limit=1) => page.getByRole('dialog',{name:`选择${label} ${count}/${limit}`,exact:true});
    await garmentCount(0).waitFor();
    assert.ok(await outfitGenerate.isDisabled());
    assert.equal(await outfitInfo.locator('dd').textContent(),'未选择');
    const emptyExportHeight = (await outfitHandoff.boundingBox()).height;
    assert.equal(emptyExportHeight,520);
    const addGarment = choose('添加单件');
    assert.equal(await addGarment.textContent(),'+添加单件');
    const emptyAdd = await addGarment.boundingBox();
    await addGarment.click();
    const garmentOptions = fixtureGarments.map(asset =>
      dialog.getByRole('button',{name:`选择${asset.id} · ${asset.name}（${asset.bodyArea}）`,exact:true}));
    await garmentOptions[0].waitFor();
    await pickerCount('单件',0,5).waitFor();
    for (const label of ['套装甲','制作中单件','旧服装']) {
      assert.equal(await dialog.getByText(label,{exact:false}).count(),0);
    }
    await garmentOptions[0].click();
    await pickerCount('单件',1,5).waitFor();
    const garmentFilter = dialog.locator('header').getByRole('group',{name:'按部位筛选',exact:true});
    const trousers = garmentFilter.getByRole('checkbox',{name:'裤装',exact:true});
    await trousers.check();
    assert.equal(await garmentOptions[0].count(),0);
    await garmentOptions[1].waitFor();
    await pickerCount('单件',1,5).waitFor();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await garmentCount(1).waitFor();
    assert.equal(await outfitInfo.locator('dd').textContent(),'O003 · 单件样例1（组合）');
    const firstGarmentImage = page.locator('.chloe-assembly-garments img').first();
    await firstGarmentImage.evaluate(image => { image.loading = 'eager'; return image.decode(); });
    const firstImage = await firstGarmentImage.boundingBox();
    const firstCover = await page.locator('.chloe-assembly-garments .cover').first().boundingBox();
    assert.ok(Math.abs(firstImage.width - firstCover.width) <= 1 && Math.abs(firstImage.width / firstImage.height - 4/3) < 0.01);
    const nextAdd = await addGarment.boundingBox();
    const firstSelectedGarment = page.locator('.chloe-assembly-garments .asset-media-card').first();
    const firstCard = await firstSelectedGarment.boundingBox();
    const garmentRemove = choose('移除O003 · 单件样例1');
    const garmentRemoveBox = await garmentRemove.boundingBox();
    assert.ok(nextAdd.x > emptyAdd.x && Math.abs(nextAdd.height-firstCard.height) <= 2);
    assert.ok(garmentRemoveBox.y < firstCard.y && garmentRemoveBox.y+garmentRemoveBox.height > firstCard.y);
    assert.ok(garmentRemoveBox.x < firstCard.x+firstCard.width && garmentRemoveBox.x+garmentRemoveBox.width > firstCard.x+firstCard.width);
    assert.equal(await garmentRemove.textContent(),'×');
    assert.match(await garmentRemove.getAttribute('class'),/\bdanger-button\b/);
    await outfitGenerate.click();
    assert.match(await outfitHandoff.textContent(),/^1\. O003 · 单件样例1$/m);
    assert.match(await outfitHandoff.textContent(),/按编号和标题找到各单件正式采用的服装展示图。生成前先逐张打开并查看/);
    assert.doesNotMatch(await outfitHandoff.textContent(),/IMG-|@V\d+|（组合）/);
    assert.equal((await outfitHandoff.boundingBox()).height,emptyExportHeight);
    await addGarment.click();
    await garmentOptions[0].waitFor();
    for (const option of garmentOptions.slice(1,5)) await option.click();
    await pickerCount('单件',5,5).waitFor();
    assert.ok(await garmentOptions[5].isDisabled());
    await garmentOptions[4].click();
    await garmentOptions[5].click();
    await page.keyboard.press('Escape');
    await garmentCount(1).waitFor();
    await addGarment.click();
    for (const option of garmentOptions.slice(1,5)) await option.click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await garmentCount(5).waitFor();
    assert.ok(await outfitExport.getByRole('button',{name:'复制',exact:true}).isDisabled());
    await outfitGenerate.click();
    assert.match(await outfitHandoff.textContent(),/5\. O007/);
    assert.equal((await outfitHandoff.boundingBox()).height,emptyExportHeight);
    await page.locator('.chloe-assembly-garments img').evaluateAll(images=>Promise.all(images.map(image=>{
      image.loading='eager';
      return image.decode();
    })));
    const editGarments = choose('编辑单件');
    const [cards, edit, info, exported] = await Promise.all([
      page.locator('.chloe-assembly-garments .asset-media-card').evaluateAll(nodes=>nodes.map(node=>node.getBoundingClientRect().toJSON())),
      editGarments.boundingBox(), outfitInfo.boundingBox(), outfitExport.boundingBox(),
    ]);
    assert.equal(cards.length,5);
    assert.ok(cards.slice(0,3).every(card=>Math.abs(card.y-cards[0].y)<=1 && Math.abs(card.width-edit.width)<=1));
    assert.ok(cards.slice(3).every(card=>Math.abs(card.y-edit.y)<=1));
    assert.ok(Math.abs(edit.x-cards[2].x)<=1 && edit.y>cards[0].bottom);
    assert.ok(cards[3].height>cards[0].height);
    assert.equal(info.y,exported.y);
    assert.ok(info.x+info.width<exported.x && info.y>edit.y+edit.height);
    assert.ok(Math.abs(info.width-exported.width)<=1);
    assert.equal(exported.x-info.x-info.width,32);
    await editGarments.click();
    await garmentOptions[0].waitFor();
    await pickerCount('单件',5,5).waitFor();
    assert.ok(await garmentOptions[5].isDisabled());
    await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),true);
    await page.screenshot({path:output+`/${width}-outfit.png`,fullPage:true});
    await garmentRemove.click();
    await garmentCount(4).waitFor();
    assert.equal(await outfitInfo.getByText('O003 · 单件样例1（组合）',{exact:true}).count(),0);
    assert.ok(await outfitExport.getByRole('button',{name:'复制',exact:true}).isDisabled());
    await outfitGenerate.click();
    assert.match(await outfitHandoff.textContent(),/^1\. O004 · 单件样例2$/m);
    assert.doesNotMatch(await outfitHandoff.textContent(),/O003/);
    await reset.click();
    await garmentCount(0).waitFor();
    assert.ok(await outfitGenerate.isDisabled());
    assert.equal(await outfitInfo.locator('dd').textContent(),'未选择');

    await assemblyNav.getByRole('button',{name:'姿态装配',exact:true}).click();
    assert.match(page.url(),/assemblyTab=poses/);
    await choose('添加姿态').click();
    const poseChoice = index => {
      const {id,name} = fixturePoses[index];
      return dialog.getByRole('button',{name:`选择${id} · ${name}`,exact:true});
    };
    await poseChoice(0).waitFor();
    assert.equal(await dialog.locator('.asset-media-card').count(),15);
    const pickerRows = await dialog.locator('.asset-media-card').evaluateAll(cards=>cards.slice(0,7).map(card=>card.getBoundingClientRect().top));
    assert.ok(pickerRows.slice(0,6).every(top=>top===pickerRows[0]) && pickerRows[6]>pickerRows[0]);
    const chosenPoses = [0,2,3,4,5,6,15];
    for (const index of chosenPoses.slice(0,6)) await poseChoice(index).click();
    await dialog.getByRole('checkbox',{name:'坐姿',exact:true}).check();
    await poseChoice(16).waitFor();
    await dialog.getByRole('heading',{name:'选择姿态 6 项',exact:true}).waitFor();
    await dialog.getByRole('checkbox',{name:'坐姿',exact:true}).uncheck();
    await dialog.getByRole('button',{name:'下一页',exact:true}).click();
    await poseChoice(15).click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    const poseSelection = page.getByRole('region',{name:'姿态选择',exact:true});
    await poseSelection.getByRole('heading',{name:'姿态选择 7 项',exact:true}).waitFor();
    const selectedPoseRows = await poseSelection.locator('.asset-media-card').evaluateAll(cards=>cards.map(card=>card.getBoundingClientRect().top));
    assert.equal(selectedPoseRows.length,7);
    assert.ok(selectedPoseRows.slice(0,6).every(top=>top===selectedPoseRows[0]) && selectedPoseRows[6]>selectedPoseRows[0]);
    await outfitGenerate.click();
    const poseExportText = chosenPoses.map(index => {
      const {id,name} = fixturePoses[index];
      return `${id} · ${name}`;
    }).join('\n');
    assert.equal(await outfitHandoff.textContent(),poseExportText);
    const poseCards = poseSelection.locator('.chloe-assembly-selected-card');
    const poseRemove = poseSelection.getByRole('button',{name:'移除站姿-001 · 站姿-001样例',exact:true});
    const [poseCardBox, poseRemoveBox] = await Promise.all([poseCards.first().boundingBox(),poseRemove.boundingBox()]);
    assert.ok(poseRemoveBox.y < poseCardBox.y && poseRemoveBox.y+poseRemoveBox.height > poseCardBox.y);
    assert.ok(poseRemoveBox.x < poseCardBox.x+poseCardBox.width && poseRemoveBox.x+poseRemoveBox.width > poseCardBox.x+poseCardBox.width);
    assert.equal(await poseRemove.textContent(),'×');
    await poseCards.first().getByRole('img').dragTo(poseCards.last(), {targetPosition:{x:24,y:55}});
    const draggedPoseTitles = poseExportText.split('\n');
    draggedPoseTitles.push(draggedPoseTitles.shift());
    assert.deepEqual(await poseCards.getByRole('heading',{level:3}).allTextContents(),draggedPoseTitles);
    assert.ok(await outfitExport.getByRole('button',{name:'复制',exact:true}).isDisabled());
    await outfitGenerate.click();
    assert.equal(await outfitHandoff.textContent(),draggedPoseTitles.join('\n'));
    await poseSelection.getByRole('img',{name:'站姿-001样例',exact:true}).click();
    assert.equal(await dialog.getByRole('img').getAttribute('src'),'/api/assembly-fixture/pose-image');
    await page.keyboard.press('Escape');
    await dialog.waitFor({state:'hidden'});
    await poseRemove.click();
    await poseSelection.getByRole('heading',{name:'姿态选择 6 项',exact:true}).waitFor();
    assert.ok(await outfitExport.getByRole('button',{name:'复制',exact:true}).isDisabled());
    await outfitGenerate.click();
    assert.equal(await outfitHandoff.textContent(),draggedPoseTitles.slice(0,-1).join('\n'));

    const poseCategory = poseSelection.getByRole('combobox',{name:'姿态分类',exact:true});
    const poseQuantity = poseSelection.getByRole('spinbutton',{name:'随机姿态数量',exact:true});
    const selectRandom = poseSelection.getByRole('button',{name:'随机选择',exact:true});
    const shufflePoses = poseSelection.getByRole('button',{name:'随机排序',exact:true});
    const selectedPoseTitles = () => poseSelection.getByRole('heading',{level:3}).allTextContents();
    assert.equal(await poseCategory.textContent(),'全部');
    await poseQuantity.fill('-1');
    assert.ok(await selectRandom.isDisabled());
    await poseQuantity.fill('1.5');
    assert.ok(await selectRandom.isDisabled());
    await poseQuantity.fill('20');
    await selectRandom.click();
    await poseSelection.getByRole('heading',{name:'姿态选择 17 项',exact:true}).waitFor();
    const allPoses = await selectedPoseTitles();
    assert.equal(new Set(allPoses).size,17);
    await poseCategory.click();
    await page.getByRole('option',{name:'站姿',exact:true}).click();
    await poseQuantity.fill('3');
    await selectRandom.click();
    await poseSelection.getByRole('heading',{name:'姿态选择 3 项',exact:true}).waitFor();
    const originalOrder = await selectedPoseTitles();
    assert.ok(originalOrder.every(title=>title.startsWith('站姿-')));
    await outfitGenerate.click();
    await shufflePoses.click();
    const shuffledOrder = await selectedPoseTitles();
    assert.notDeepEqual(shuffledOrder,originalOrder);
    assert.deepEqual([...shuffledOrder].sort(),[...originalOrder].sort());
    assert.ok(await outfitExport.getByRole('button',{name:'复制',exact:true}).isDisabled());
    await outfitGenerate.click();
    assert.equal(await outfitHandoff.textContent(),shuffledOrder.join('\n'));
    await poseCategory.click();
    await page.getByRole('option',{name:'坐姿',exact:true}).click();
    await selectRandom.click();
    await poseSelection.getByRole('heading',{name:'姿态选择 1 项',exact:true}).waitFor();
    assert.deepEqual(await selectedPoseTitles(),['坐姿-001 · 坐姿-001样例']);
    assert.ok(await shufflePoses.isDisabled());
    assert.equal(await poseCards.first().getAttribute('draggable'),null);
    await poseQuantity.fill('0');
    await selectRandom.click();
    await poseSelection.getByRole('heading',{name:'姿态选择 0 项',exact:true}).waitFor();
    assert.ok(await outfitGenerate.isDisabled());
    await reset.click();
    assert.equal(await poseCategory.textContent(),'全部');
    assert.equal(await poseQuantity.inputValue(),'1');
    assert.equal(await assemblyNav.locator('[aria-current="page"]').textContent(),'姿态装配');

    const randomPoseUrl = /\/shared-poses\?available=true&require_media=true$/;
    await page.route(randomPoseUrl, route=>route.fulfill({status:503,json:{detail:'隔离测试读取失败'}}), {times:1});
    await selectRandom.click();
    const randomReadError = page.getByRole('alert').filter({hasText:'无法读取可用姿态，请重试。'});
    await randomReadError.getByRole('button',{name:'关闭通知',exact:true}).click();
    const lateRead = Promise.withResolvers();
    await page.route(randomPoseUrl, async route => {
      await lateRead.promise;
      await route.fulfill({status:503,json:{detail:'隔离测试读取失败'}});
    }, {times:1});
    const queuedRandomRead = page.waitForRequest(request=>randomPoseUrl.test(request.url()));
    await selectRandom.click();
    await queuedRandomRead;
    await reset.click();
    const failedRandomRead = page.waitForResponse(response=>randomPoseUrl.test(response.url()) && response.status()===503);
    lateRead.resolve();
    await (await failedRandomRead).finished();
    await assert.rejects(randomReadError.waitFor({timeout:650}),{name:'TimeoutError'});
    assert.ok(await poseSelection.getByRole('heading',{name:'姿态选择 0 项',exact:true}).isVisible());

    await assemblyNav.getByRole('button',{name:'造型装配',exact:true}).click();
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
    await summary.waitFor();
    assert.deepEqual(await summary.locator('dd').allTextContents(),['未选择','未选择','未选择','未选择']);
    assert.ok(await reset.isEnabled());
    await handoff.waitFor();
    assert.equal((await handoff.boundingBox()).height,emptyExportHeight);
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
    await pickerCount('模特',0).waitFor();
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
    await pickerCount('模特',1).waitFor();
    assert.equal(await modelA.getAttribute('aria-pressed'),'false');
    assert.equal(await modelB.getAttribute('aria-pressed'),'true');
    assert.equal(await summary.locator('dd').first().textContent(),'未选择');
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await page.getByRole('heading',{name:'模特选择 1/1',exact:true}).waitFor();
    assert.notEqual(await page.evaluate(()=>getComputedStyle(document.documentElement).overflowY),'hidden');
    assert.deepEqual(await assetNav.getByRole('button').allTextContents(),assetLabels);
    await page.getByRole('img',{name:'基础三视图',exact:true}).waitFor();
    assert.equal(await page.getByRole('img',{name:'正面基础图',exact:true}).getAttribute('src'),'/api/assembly-fixture/M002-front');
    assert.equal(await page.getByRole('img',{name:'基础三视图',exact:true}).getAttribute('src'),'/api/assembly-fixture/M002-body');
    await choose('选择套装').click();
    const clothingA = dialog.getByRole('button',{name:'选择O001 · 套装甲',exact:true});
    await pickerCount('套装',0).waitFor();
    const pickerStyles = dialog.getByRole('group',{name:'按风格筛选',exact:true});
    await pickerStyles.getByRole('checkbox',{name:'备选7',exact:true}).waitFor();
    assert.deepEqual(await pickerStyles.locator('label').allTextContents(),outfitStyles);
    assert.deepEqual(await pickerStyles.locator('.status-badge').allTextContents(),outfitStyles);
    assert.equal(await pickerStyles.locator('.status-gray').textContent(),'未分类');
    const pickerUnclassified = pickerStyles.getByRole('checkbox',{name:'未分类',exact:true});
    await pickerUnclassified.check();
    await dialog.getByText('暂无符合所选风格的可用套装。',{exact:true}).waitFor();
    await pickerStyles.getByRole('checkbox',{name:'通勤',exact:true}).check();
    await clothingA.waitFor();
    await pickerUnclassified.uncheck();
    await clothingA.click();
    await pickerCount('套装',1).waitFor();
    for (const label of ['制作中套装','单件样例1','旧服装']) {
      assert.equal(await dialog.getByText(label,{exact:false}).count(),0);
    }
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await page.getByRole('heading',{name:'套装选择 1/1',exact:true}).waitFor();
    const clothingImage = page.getByRole('img',{name:'套装图',exact:true});
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
      `正面基础图和套装图上下对齐：${JSON.stringify(frames)}`);
    assert.ok(Math.abs(bodyFrame.top-hairSection.top)<=1 && Math.abs(bodyFrame.bottom-hairSection.bottom)<=1,
      `基础三视图和整个发型区上下对齐：${JSON.stringify(frames)}`);
    const modelWidth=faceFrame.right-faceFrame.left, clothingWidth=clothingFrame.right-clothingFrame.left;
    assert.ok(Math.abs(modelWidth/(modelWidth+clothingWidth)-0.3)<0.002);
    assert.ok(faceFrame.bottom-faceFrame.top > bodyFrame.bottom-bodyFrame.top);
    const [summaryBox, exportBox] = await Promise.all([summary.boundingBox(),exportArea.boundingBox()]);
    assert.ok(Math.abs(summaryBox.width-modelWidth)<=1 && Math.abs(exportBox.width-clothingWidth)<=1);
    for (const [label, src] of [['正面基础图','M002-front'],['基础三视图','M002-body'],['套装图','O001']]) {
      await choose(`查看${label}大图`).click();
      await zoom.waitFor();
      assert.equal(await zoom.getByRole('img').getAttribute('src'),`/api/assembly-fixture/${src}`);
      await page.keyboard.press('Escape');
      await zoom.waitFor({state:'hidden'});
    }
    await choose('选择套装').click();
    assert.equal(await clothingA.getAttribute('aria-pressed'),'true');
    await clothingA.click();
    assert.equal(await clothingA.getAttribute('aria-pressed'),'false');
    assert.ok(await confirm.isEnabled());
    await dialog.getByRole('button',{name:'关闭',exact:true}).click();
    assert.equal(await summary.locator('dd').nth(1).textContent(),'O001 · 套装甲');
    await choose('选择套装').click();
    await clothingA.click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    assert.equal(await summary.locator('dd').nth(1).textContent(),'未选择');
    assert.equal(await page.getByRole('img',{name:'套装图',exact:true}).count(),0);
    assert.ok(await generateHandoff.isDisabled());
    await choose('选择套装').click();
    await clothingA.click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await generateHandoff.click();
    assert.doesNotMatch(await handoff.textContent(), /^(发型|配饰)：/m);
    assert.equal((await handoff.boundingBox()).height,emptyExportHeight);
    await choose('选择发型').click();
    const hairChoice = dialog.getByRole('button',{name:'选择H001 · 发型甲',exact:true});
    await hairChoice.click();
    assert.equal(await dialog.getByText('H002 · 制作中发型',{exact:true}).count(),0);
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
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
    await dialog.waitFor({state:'hidden'});
    assert.equal(await summary.locator('dd').nth(2).textContent(),'未选择');
    assert.equal(await page.getByRole('img',{name:'发型图',exact:true}).count(),0);
    await choose('选择发型').click();
    await hairChoice.click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
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
    const [filterBox, confirmBox, closeBox] = await Promise.all([
      filters.boundingBox(),confirm.boundingBox(),dialog.getByRole('button',{name:'关闭',exact:true}).boundingBox(),
    ]);
    assert.ok(confirmBox.x+confirmBox.width<closeBox.x && closeBox.y+closeBox.height<filterBox.y);
    assert.ok(filterBox.y+filterBox.height<shortCard.y);
    assert.equal(await dialog.getByRole('button',{name:'筛选',exact:true}).count(),0);
    if (height === 640) {
      const scroll = await dialog.evaluate(element => {
        const filterBox = element.querySelector('fieldset');
        const card = element.querySelector('article');
        element.scrollTop = 0;
        const filterTop = filterBox.getBoundingClientRect().top;
        const cardTop = card.getBoundingClientRect().top;
        element.scrollTop = 90;
        return {filterShift:filterBox.getBoundingClientRect().top-filterTop, cardShift:card.getBoundingClientRect().top-cardTop};
      });
      assert.ok(Math.abs(scroll.filterShift)<1 && scroll.cardShift<0);
    }
    await accessoryChoice(0).click();
    const bagFilter = filters.getByRole('checkbox',{name:'包袋',exact:true});
    const hatFilter = filters.getByRole('checkbox',{name:'帽饰',exact:true});
    assert.equal(await dialog.locator('header').getByRole('group',{name:'按类型筛选',exact:true}).count(),1);
    assert.equal(await filters.getByRole('checkbox',{name:'首饰',exact:true}).count(),0);
    await bagFilter.check();
    await accessoryChoice(1).waitFor();
    assert.equal(await accessoryChoice(0).count(),0);
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择配饰 1/5');
    await hatFilter.check();
    await accessoryChoice(0).waitFor();
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
    await dialog.waitFor({state:'hidden'});
    assert.equal(await accessories.getByRole('heading',{level:2}).textContent(),'配饰选择 5/5');
    assert.equal(await choose('添加配饰').count(),0);
    assert.deepEqual(await summary.locator('dt').allTextContents(),['模特','套装','发型','配饰 1','配饰 2','配饰 3','配饰 4','配饰 5']);
    assert.deepEqual(await summary.locator('dd').allTextContents(),['M002 · 模特乙','O001 · 套装甲','H001 · 发型甲',...[0,1,2,3,5].map(i=>`${fixtureAccessories[i].id} · ${fixtureAccessories[i].name}`)]);
    assert.equal(await handoff.textContent(),'点击「生成」，整理当前选择的造型制作交接词。');
    assert.ok(await copyHandoff.isDisabled());
    const emptyHandoffHeight = (await handoff.boundingBox()).height;
    await generateHandoff.click();
    const text = await handoff.textContent();
    for (const value of ['Chloe AI视频带货','模特：M002 · 模特乙','套装：O001 · 套装甲','发型：H001 · 发型甲',
      '按对象编号和标题查找各自正式采用的参考图','造型面部三视图','全身定装三视图原图','遮面版']) assert.ok(text.includes(value),value);
    for (const i of [0,1,2,3,5]) assert.ok(text.includes(`${fixtureAccessories[i].id} · ${fixtureAccessories[i].name}`));
    assert.match(text,/^套装：O001 · 套装甲$/m);
    assert.doesNotMatch(text,/IMG-|@V\d+|文件：|正面基础图|基础全身三视图|C005/);
    const textBox = await handoff.evaluate(element => ({
      height:element.getBoundingClientRect().height, border:getComputedStyle(element).borderTopWidth,
      fits:element.scrollHeight <= element.clientHeight && element.scrollWidth <= element.clientWidth,
    }));
    assert.equal(textBox.height,emptyHandoffHeight);
    assert.ok(textBox.fits);
    assert.equal(textBox.border,'1px');
    await copyHandoff.click();
    await page.waitForFunction(async expected => await navigator.clipboard.readText() === expected,text);
    await accessories.getByRole('img',{name:'C001',exact:true}).click();
    await zoom.waitFor();
    assert.equal(await zoom.getByRole('img').getAttribute('src'),'/api/assembly-fixture/C001');
    await page.keyboard.press('Escape');
    await zoom.waitFor({state:'hidden'});
    const accessoryRemove = accessories.getByRole('button',{name:'移除C001 · 配饰样例1',exact:true});
    const accessoryCard = accessories.locator('.asset-media-card').filter({has:page.getByRole('img',{name:'C001',exact:true})});
    const [accessoryCardBox, accessoryRemoveBox] = await Promise.all([accessoryCard.boundingBox(),accessoryRemove.boundingBox()]);
    assert.ok(accessoryRemoveBox.y < accessoryCardBox.y && accessoryRemoveBox.y+accessoryRemoveBox.height > accessoryCardBox.y);
    assert.ok(accessoryRemoveBox.x < accessoryCardBox.x+accessoryCardBox.width && accessoryRemoveBox.x+accessoryRemoveBox.width > accessoryCardBox.x+accessoryCardBox.width);
    assert.equal(await accessoryRemove.textContent(),'×');
    assert.match(await accessoryRemove.getAttribute('class'),/\bdanger-button\b/);
    await accessoryRemove.click();
    await accessories.getByRole('heading',{name:'配饰选择 4/5',exact:true}).waitFor();
    assert.equal(await choose('添加配饰').count(),1);
    assert.equal(await summary.getByText('C001 · 配饰样例1',{exact:true}).count(),0);
    assert.ok(await copyHandoff.isDisabled());
    await generateHandoff.click();
    assert.doesNotMatch(await handoff.textContent(),/C001/);
    assert.match(await handoff.textContent(),/^1\. C002 · 配饰样例2$/m);
    await choose('编辑配饰').click();
    assert.equal(await accessoryChoice(0).getAttribute('aria-pressed'),'false');
    await accessoryChoice(0).click();
    await dialog.getByRole('button',{name:'关闭',exact:true}).click();
    assert.equal(await accessories.getByRole('heading',{level:2}).textContent(),'配饰选择 4/5');
    await choose('编辑配饰').click();
    for (const index of [1,2,3,5]) await accessoryChoice(index).click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    assert.equal(await accessories.getByRole('heading',{level:2}).textContent(),'配饰选择 0/5');
    assert.equal(await choose('添加配饰').count(),1);
    await reset.click();
    assert.equal(await handoff.textContent(),'选定模特和套装后可生成交接词，发型和配饰可选。');
    assert.ok(await copyHandoff.isDisabled());
    assert.deepEqual(await summary.locator('dd').allTextContents(),['未选择','未选择','未选择','未选择']);
    assert.equal(await page.locator('.chloe-assembly-main img').count(),0);
    assert.deepEqual(await accessories.getByRole('button').allTextContents(),['+添加配饰']);
    assert.ok(await reset.isEnabled());
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),true);
    await checkRefreshedPicker('shared-clothing','选择套装','O001 · 套装甲','暂无可用套装。',fixtureClothing);

    await choose('选择模特').click();
    await dialog.getByRole('button',{name:'选择M002 · 模特乙',exact:true}).click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await assemblyNav.getByRole('button',{name:'视频装配'}).click();
    assert.ok(page.url().endsWith('asset=assembly&assemblyTab=video'));
    const videoAssembly = page.locator('.chloe-video-assembly');
    await videoAssembly.waitFor();
    assert.ok(await generateHandoff.isDisabled());
    assert.equal((await handoff.boundingBox()).height,emptyExportHeight);
    const previewTitles = ['参考视频','造型面部三视图','全身定装三视图遮面版','背景图'];
    assert.deepEqual(await videoAssembly.locator('figcaption').allTextContents(),previewTitles);
    const emptyLookFrames = videoAssembly.locator('.chloe-video-assembly-look-images figure');
    await emptyLookFrames.first().waitFor({state:'visible'});
    await emptyLookFrames.nth(1).waitFor({state:'visible'});
    const emptyFrameBounds = await emptyLookFrames.evaluateAll(frames =>
      frames.map(frame => {
        const {top,bottom,height} = frame.getBoundingClientRect();
        return {top,bottom,height};
      }));
    assert.equal(emptyFrameBounds.length,2);
    assert.ok(emptyFrameBounds.every(frame=>frame.height>0));
    assert.ok(emptyFrameBounds[0].bottom<emptyFrameBounds[1].top);
    await choose('选择参考视频').click();
    const videoPicker = page.getByRole('dialog',{name:/^选择参考视频 \d\/1$/});
    const videoOption = videoPicker.getByRole('button',{name:'选择RV001 · 参考视频甲',exact:true});
    await videoOption.waitFor();
    await pickerCount('参考视频',0).waitFor();
    const header = videoPicker.locator('header');
    assert.deepEqual(await header.getByRole('button').allTextContents(),['确认选择','关闭 ×']);
    assert.equal(await header.getByRole('group',{name:'按类型筛选',exact:true}).count(),0);
    assert.equal(await dialog.getByText('待登记参考视频',{exact:false}).count(),0);
    await videoPicker.getByRole('button',{name:'全屏播放RV001 · 参考视频甲',exact:true}).click();
    const fullVideo = page.getByRole('dialog',{name:'RV001 · 参考视频甲',exact:true});
    const fullVideoPlayer = fullVideo.locator('video[controls]');
    assert.equal(await fullVideoPlayer.getAttribute('src'),fixtureVideo.videoUrl);
    await fullVideoPlayer.evaluate(video=>video.play());
    await page.keyboard.press('Escape');
    await fullVideo.waitFor({state:'detached'});
    assert.equal(await videoOption.getAttribute('aria-pressed'),'false');
    assert.ok(await confirm.isDisabled());
    await videoOption.click();
    await pickerCount('参考视频',1).waitFor();
    assert.equal(await videoOption.getAttribute('aria-pressed'),'true');
    await videoOption.click();
    assert.equal(await videoOption.getAttribute('aria-pressed'),'false');
    assert.ok(await confirm.isDisabled());
    await videoOption.click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    const player = page.locator('video[aria-label="参考视频甲"]');
    await player.waitFor();
    await page.getByRole('heading',{name:'参考视频 1/1',exact:true}).waitFor();
    await page.waitForFunction(()=>document.querySelector('video[aria-label="参考视频甲"]')?.readyState>=1);
    await choose('选择参考视频').click();
    assert.equal(await videoOption.getAttribute('aria-pressed'),'true');
    await videoOption.click();
    assert.ok(await confirm.isEnabled());
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await player.waitFor({state:'detached'});
    await choose('选择参考视频').click();
    await videoOption.click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await player.waitFor();
    await choose('选择造型图').click();
    await pickerCount('模特',0).waitFor();
    await dialog.getByRole('button',{name:'选择M002 · 模特乙',exact:true}).waitFor();
    assert.equal(await dialog.getByText('制作中模特',{exact:false}).count(),0);
    await dialog.getByRole('button',{name:'选择M002 · 模特乙',exact:true}).click();
    await dialog.getByRole('button',{name:'选择L001 · 造型甲',exact:true}).waitFor();
    await page.getByRole('dialog',{name:'选择造型图 0/1 · M002 · 模特乙',exact:true}).waitFor();
    assert.equal(await dialog.getByText('制作中造型',{exact:false}).count(),0);
    await dialog.getByRole('button',{name:'选择L001 · 造型甲',exact:true}).click();
    await page.getByRole('dialog',{name:'选择造型图 1/1 · M002 · 模特乙',exact:true}).waitFor();
    await page.keyboard.press('Escape');
    assert.ok(await generateHandoff.isDisabled());
    await choose('选择造型图').click();
    await dialog.getByRole('button',{name:'选择M002 · 模特乙',exact:true}).click();
    await dialog.getByRole('button',{name:'选择L001 · 造型甲',exact:true}).click();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await page.getByRole('heading',{name:'造型图 1/1',exact:true}).waitFor();
    const lookPreviews = page.getByRole('region',{name:'造型图选择'});
    const previewBounds = [];
    for (const [label,src] of [['造型面部三视图','L001-face'],['全身定装三视图遮面版','L001-masked']]) {
      const image = lookPreviews.getByRole('img',{name:label,exact:true});
      assert.equal(await image.getAttribute('src'),fixtureImage(src).url);
      previewBounds.push(await image.boundingBox());
      await lookPreviews.getByRole('button',{name:`查看${label}大图`,exact:true}).click();
      assert.equal(await dialog.getByRole('img',{name:label,exact:true}).getAttribute('src'),fixtureImage(src).url);
      await page.keyboard.press('Escape');
    }
    assert.equal(await lookPreviews.getByRole('img').count(),2);
    assert.deepEqual(await videoAssembly.locator('figcaption').allTextContents(),previewTitles);
    assert.ok(previewBounds[0].y+previewBounds[0].height<previewBounds[1].y);
    await generateHandoff.click();
    assert.match(await handoff.textContent(),/背景：沿用参考视频的场景/);
    await choose('选择背景').click();
    await pickerCount('背景',0).waitFor();
    await dialog.getByRole('button',{name:'选择S001 · 背景甲',exact:true}).waitFor();
    assert.equal(await dialog.getByText('制作中背景',{exact:false}).count(),0);
    await dialog.getByRole('button',{name:'选择S001 · 背景甲',exact:true}).click();
    await pickerCount('背景',1).waitFor();
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await page.getByRole('heading',{name:'背景 1/1 可选',exact:true}).waitFor();
    const requirements = page.getByRole('textbox',{name:'额外要求（可选）'});
    await requirements.fill('保持开场构图和节奏。\n'.repeat(60));
    await generateHandoff.click();
    assert.equal((await handoff.boundingBox()).height,emptyExportHeight);
    assert.ok(await handoff.evaluate(text=>text.scrollHeight>text.clientHeight));
    await requirements.fill('保留开场动作。\n镜头稍慢。');
    assert.ok(await copyHandoff.isDisabled());
    await generateHandoff.click();
    const videoPrompt = await handoff.textContent();
    for (const text of ['RV001 · 参考视频甲','M002 · 模特乙','L001 · 造型甲','S001 · 背景甲','保留开场动作。\n镜头稍慢。','已登记播放版本','正式采用的造型面部三视图和全身定装三视图遮面版','正式采用的场景展示图']) {
      assert.ok(videoPrompt.includes(text), text);
    }
    assert.doesNotMatch(videoPrompt,/IMG-|L001-(adopted|face|masked)|\.webm|文件：/);
    await copyHandoff.click();
    assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replaceAll('\r\n','\n'),videoPrompt);
    const [videoBox, lookBox, sceneBox, requirementsBox, promptBox] = await Promise.all([
      page.getByRole('region',{name:'参考视频选择'}).boundingBox(),page.getByRole('region',{name:'造型图选择'}).boundingBox(),
      page.getByRole('region',{name:'背景选择'}).boundingBox(),page.getByRole('region',{name:'额外要求',exact:true}).boundingBox(),
      exportArea.boundingBox(),
    ]);
    assert.equal(videoBox.y,lookBox.y);
    assert.equal(videoBox.y,sceneBox.y);
    assert.equal(videoBox.height,lookBox.height);
    assert.equal(videoBox.height,sceneBox.height);
    assert.ok(videoBox.x+videoBox.width<lookBox.x && lookBox.x+lookBox.width<sceneBox.x);
    const columnUnit = (videoBox.width+lookBox.width+sceneBox.width)/10;
    assert.ok(Math.abs(videoBox.width-3*columnUnit)<1 && Math.abs(lookBox.width-4*columnUnit)<1 && Math.abs(sceneBox.width-3*columnUnit)<1);
    assert.equal(requirementsBox.y,promptBox.y);
    assert.equal(requirementsBox.width,promptBox.width);
    assert.equal(requirementsBox.x,videoBox.x);
    assert.equal(promptBox.x-requirementsBox.x-requirementsBox.width,32);
    assert.ok(sceneBox.y+sceneBox.height<promptBox.y);
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
    await assemblyNav.getByRole('button',{name:'造型装配',exact:true}).click();
    assert.equal(await summary.locator('dd').first().textContent(),'M002 · 模特乙');
    await assemblyNav.getByRole('button',{name:'视频装配',exact:true}).click();
    assert.ok(await generateHandoff.isDisabled());
    await checkRefreshedPicker('shared-scenes','选择背景','S001 · 背景甲','暂无可选背景。',fixtureScenes);
    await page.reload();
    await assemblyNav.getByRole('button',{name:'视频装配'}).waitFor();
    assert.equal(await assemblyNav.locator('[aria-current="page"]').textContent(),'视频装配');

    testPaging = true;
    await assetNav.getByRole('button',{name:'配饰',exact:true}).click();
    const firstPageCard = page.getByRole('link',{name:'C001 · 配饰样例1',exact:true});
    const secondPageCard = page.getByRole('link',{name:'C013 · 分页配饰13',exact:true});
    await firstPageCard.waitFor();
    assert.equal(await page.locator('.chloe-accessory-columns .asset-media-card').count(),12);
    assert.equal(await page.getByRole('checkbox',{name:'手表',exact:true}).count(),1);
    await page.getByRole('button',{name:'下一页',exact:true}).click();
    await secondPageCard.waitFor();
    assert.match(page.url(),/assetPage=2/);
    const lastPageCard = page.getByRole('link',{name:'C024 · 分页配饰24',exact:true});
    await lastPageCard.scrollIntoViewIfNeeded();
    const listScroll = await page.evaluate(()=>window.scrollY);
    assert.ok(listScroll>0);
    await lastPageCard.click();
    const backToAccessories = page.getByRole('link',{name:'返回配饰列表',exact:true});
    await backToAccessories.click();
    await secondPageCard.waitFor();
    assert.match(page.url(),/assetPage=2/);
    await page.waitForFunction(top=>Math.abs(window.scrollY-top)<5,listScroll);
    await page.getByRole('checkbox',{name:'手表',exact:true}).check();
    await secondPageCard.waitFor();
    assert.doesNotMatch(page.url(),/assetPage=/);
    assert.equal(await page.getByRole('button',{name:'下一页',exact:true}).count(),0);

    await assetNav.getByRole('button',{name:'装配',exact:true}).click();
    await assemblyNav.getByRole('button',{name:'造型装配',exact:true}).click();
    await choose('添加配饰').click();
    await accessoryChoice(0).click();
    await dialog.getByRole('button',{name:'下一页',exact:true}).click();
    const extraChoice = dialog.getByRole('button',{name:'选择C014 · 分页配饰14',exact:true});
    await extraChoice.click();
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择配饰 2/5');
    await dialog.getByRole('button',{name:'上一页',exact:true}).click();
    assert.equal(await accessoryChoice(0).getAttribute('aria-pressed'),'true');
    await accessoryChoice(0).click();
    await accessoryChoice(1).click();
    unavailable = 'C014';
    await confirm.click();
    await dialog.getByText('部分已选资料已不可用，请重新确认选择。',{exact:true}).waitFor();
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择配饰 1/5');
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    await choose('编辑配饰').waitFor();
    assert.ok((await summary.textContent()).includes('C002 · 配饰样例2'));
    assert.ok(!(await summary.textContent()).includes('C014'));

    await assemblyNav.getByRole('button',{name:'视频装配',exact:true}).click();
    await choose('选择参考视频').click();
    await dialog.getByRole('button',{name:'下一页',exact:true}).click();
    await dialog.getByRole('button',{name:'选择RV014 · 分页视频14',exact:true}).click();
    await dialog.getByRole('button',{name:'上一页',exact:true}).click();
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择参考视频 1/1');
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    assert.equal(await choose('选择参考视频').textContent(),'RV014 · 分页视频14');
    await choose('选择造型图').click();
    await dialog.getByRole('button',{name:'选择M002 · 模特乙',exact:true}).click();
    await dialog.getByRole('button',{name:'下一页',exact:true}).click();
    await dialog.getByRole('button',{name:'选择L014 · 分页造型14',exact:true}).click();
    await dialog.getByRole('button',{name:'上一页',exact:true}).click();
    assert.equal(await dialog.getByRole('heading',{level:2}).textContent(),'选择造型图 1/1 · M002 · 模特乙');
    await confirm.click();
    await dialog.waitFor({state:'hidden'});
    assert.equal(await choose('选择造型图').textContent(),'M002 · 模特乙 / L014 · 分页造型14');

    refreshedAssets.delete('/api/workspaces/account-demo/shared-clothing');
    await assetNav.getByRole('button',{name:'服装',exact:true}).click();
    await commute.check();
    await currentStyle.filter({hasText:/^通勤$/}).waitFor();
    const manageStyles = styleFilter.getByRole('button',{name:'管理',exact:true});
    const [legendBox, manageBox, styleFilterBounds] = await Promise.all([
      styleFilter.locator('legend').boundingBox(), manageStyles.boundingBox(), styleFilter.boundingBox(),
    ]);
    assert.ok(Math.abs(manageBox.y - legendBox.y) < 3 && styleFilterBounds.x + styleFilterBounds.width - manageBox.x - manageBox.width < 28);
    await manageStyles.click();
    const styleManager = page.getByRole('dialog',{name:'管理套装风格',exact:true});
    assert.equal(await styleManager.getByRole('button',{name:'删除 未分类',exact:true}).count(),0);
    await styleManager.getByRole('button',{name:'重命名 通勤',exact:true}).click();
    const nameInput = styleManager.getByRole('textbox',{name:'风格名称',exact:true});
    const saveName = styleManager.getByRole('button',{name:'保存名称',exact:true});
    assert.ok(await saveName.isDisabled());
    await nameInput.fill('简约');
    await saveName.click();
    const namingError = styleManager.getByRole('alert').filter({hasText:'该风格已存在'});
    await namingError.getByRole('button',{name:'关闭通知'}).click();
    await nameInput.fill('都市');
    await saveName.click();
    const removeStyle = styleManager.getByRole('button',{name:'删除 都市',exact:true});
    await removeStyle.waitFor();
    const selectedFilter = url => new URLSearchParams(url.hash.split('?')[1]).get('assetType');
    await page.waitForURL(url => selectedFilter(url) === '都市');
    await styleManager.getByRole('button',{name:'关闭',exact:true}).click();
    await currentStyle.filter({hasText:/^都市$/}).waitFor();
    assert.ok(await styleFilter.getByRole('checkbox',{name:'都市',exact:true}).isChecked());
    await manageStyles.click();
    await removeStyle.click();
    await styleManager.getByRole('button',{name:'取消',exact:true}).click();
    await removeStyle.click();
    await styleManager.getByRole('button',{name:'确认删除',exact:true}).click();
    await removeStyle.waitFor({state:'detached'});
    await page.waitForURL(url => !selectedFilter(url));
    await styleManager.getByRole('button',{name:'关闭',exact:true}).click();
    await currentStyle.filter({hasText:/^未分类$/}).waitFor();
    assert.equal(await styleFilter.getByRole('checkbox',{name:'都市',exact:true}).count(),0);

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
