// Shared preview behavior and external download access; static fixtures only.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require=createRequire(new URL('../frontend/package.json',import.meta.url));
const {chromium}=require('playwright');
const {createServer}=await import(require.resolve('vite'));
const react=(await import(require.resolve('@vitejs/plugin-react'))).default;
const server=await createServer({configFile:false,root:fileURLToPath(new URL('../frontend',import.meta.url)),plugins:[react()],server:{host:'127.0.0.1',port:0}});
await server.listen();const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 for(const [width,height] of [[1280,640],[1366,768],[1920,1080]]){
  const page=await browser.newPage({viewport:{width,height}});page.setDefaultTimeout(10000);
  await page.route('**/api/**',route=>{assert.equal(route.request().method(),'GET');return route.fulfill({json:{html:'<p>资料正文</p>'}});});
  await page.route('**/fixture/broken.webm',route=>route.fulfill({status:404,body:'missing'}));
  await page.goto(server.resolvedUrls.local[0]+'tests/file-actions.html');
  const directory=page.getByRole('region',{name:'视频目录'});
  for(const name of ['目录视频.webm','扩展名视频.mov']){
   const row=directory.locator('.file').filter({has:page.getByRole('button',{name,exact:true})});
   const download=page.waitForEvent('download');await row.getByRole('link',{name:'下载',exact:true}).click();
   assert.equal(await (await download).failure(),null);
   await row.getByRole('button',{name,exact:true}).click();const dialog=page.getByRole('dialog');
   assert.equal(await dialog.locator('.file-action-links').count(),0);
   await dialog.locator('video').evaluate(video=>video.play());
   await page.waitForFunction(()=>document.querySelector('dialog video')?.currentTime>0);
   assert.ok(await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;}));
   await dialog.getByRole('button',{name:'关闭',exact:true}).click();
  }
  const prose=page.getByRole('region',{name:'正文视频'});
  assert.equal(await prose.locator('.download-control').count(),1);
  const download=page.waitForEvent('download');await prose.locator('.download-control').click();assert.equal(await (await download).failure(),null);
  await prose.getByRole('link',{name:'正文视频',exact:true}).click();
  assert.equal(await page.getByRole('dialog').locator('.file-action-links').count(),0);await page.keyboard.press('Escape');
  await directory.getByRole('button',{name:'失败视频.webm',exact:true}).click();
  await page.getByText('视频无法加载，请关闭预览后重新打开，或从外层目录、资料详情下载视频查看。',{exact:true}).waitFor();
  assert.equal(await page.getByRole('dialog').locator('.file-action-links').count(),0);await page.keyboard.press('Escape');
  for(const [name,links] of [['声音.wav',2],['图片.svg',1],['人物-资料卡.md',2]]){
   await page.getByRole('button',{name,exact:true}).click();
   assert.equal(await page.getByRole('dialog').locator('.file-action-links a').count(),links);
   await page.keyboard.press('Escape');
  }
  assert.equal(await page.getByRole('dialog').count(),0);await page.close();
 }
 console.log('Video popup, outside downloads, failure guidance and unchanged audio/image/document previews: three desktop sizes passed.');
}finally{await browser.close();await server.close();}
