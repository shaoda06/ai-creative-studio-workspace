import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

export async function checkSharedDownloads(page, width) {
  await page.mouse.move(0, 0); // Compare normal styles before the explicit hover checks below.
  const fixture = page.getByTestId('downloads');
  const breadcrumb = fixture.getByTestId('episode-breadcrumb');
  const boundary = await breadcrumb.evaluate(el => {
    const parent = el.getBoundingClientRect();
    return { left: parent.left, right: parent.right, width: el.clientWidth, scroll: el.scrollWidth,
      items: [...el.querySelectorAll('.breadcrumb-actions, .episode-heading-actions, button')].map(child => {
        const r = child.getBoundingClientRect(); return { left: r.left, right: r.right };
      }) };
  });
  assert.ok(boundary.scroll <= boundary.width + 1 && boundary.items.every(r => r.left >= boundary.left - 1 && r.right <= boundary.right + 1),
    `${width}px / 单集路径操作区越界: ${JSON.stringify(boundary)}`);
  assert.equal(await breadcrumb.getByRole('button', { name: '剪映布局检查', exact: true }).isDisabled(), true);
  const episodeSaved = page.waitForEvent('download');
  await breadcrumb.getByRole('button', { name: '本集打包下载', exact: true }).click();
  const episodeFile = await episodeSaved;
  assert.equal(episodeFile.suggestedFilename(), 'episode-layout.txt');
  assert.equal(await readFile(await episodeFile.path(), 'utf8'), '双按钮布局检查');
  const styles = await fixture.locator('.download-control').evaluateAll(elements => elements.slice(2, 6).map(el => {
    const style = getComputedStyle(el);
    return Object.fromEntries(['fontSize', 'fontWeight', 'lineHeight', 'padding', 'borderRadius', 'color', 'backgroundColor', 'borderColor'].map(key => [key, style[key]]));
  }));
  for (const style of styles) assert.deepEqual(style, styles[0], `${width}px / 页面容器不能覆盖下载外观`);
  assert.equal(styles[0].fontSize, '14px');
  const hoverStyles = [];
  for (const control of [fixture.getByRole('button', { name: '下载检查', exact: true }), fixture.locator('.file-action-links .download-control')]) {
    await control.hover();
    hoverStyles.push(await control.evaluate(el => ({ border: getComputedStyle(el).borderColor, background: getComputedStyle(el).backgroundColor })));
  }
  assert.deepEqual(hoverStyles[0], hoverStyles[1], '按钮和原生链接的悬停外观一致');
  await page.mouse.move(0, 0);
  assert.equal(await fixture.getByRole('button', { name: '下载 API 版', exact: true }).isDisabled(), true);
  for (const summary of await fixture.locator('details > summary').all()) await summary.click();
  for (const button of await fixture.locator('.download-control').all()) {
    const bounds = await button.evaluate(el => {
      const r = el.getBoundingClientRect(), p = el.parentElement.getBoundingClientRect();
      return { left: r.left, right: r.right, parentLeft: p.left, parentRight: p.right, overflow: el.scrollWidth > el.clientWidth + 1 };
    });
    assert.ok(bounds.left >= bounds.parentLeft - 1 && bounds.right <= bounds.parentRight + 1 && !bounds.overflow, JSON.stringify(bounds));
  }
  const native = fixture.locator('.file-action-links .download-control');
  const nativeUrl = new URL(await native.getAttribute('href'));
  assert.equal(nativeUrl.searchParams.get('revision'), '7');
  assert.equal(nativeUrl.searchParams.get('download'), 'true');
  assert.equal(nativeUrl.hash, '');
  const nativeSaved = page.waitForEvent('download');
  await native.click();
  const nativeFile = await nativeSaved;
  assert.equal(nativeFile.suggestedFilename(), 'image.svg');
  assert.match(await readFile(await nativeFile.path(), 'utf8'), /<svg/);
  const localSaved = page.waitForEvent('download');
  await fixture.getByRole('button', { name: '下载检查', exact: true }).click();
  const localFile = await localSaved;
  assert.equal(localFile.suggestedFilename(), 'download-local.md');
  assert.equal(await readFile(await localFile.path(), 'utf8'), '本地下载检查');

  let releaseResponse;
  const responseGate = new Promise(resolve => { releaseResponse = resolve; });
  let attempts = 0;
  await page.route('**/component-samples/download-check.txt', async route => {
    attempts++;
    if (attempts === 1) await responseGate;
    await route.fulfill({ status: 200, headers: attempts === 1 ? {} : { 'Content-Disposition': 'attachment; filename="download-pack.txt"' }, body: '打包下载检查' });
  });
  await fixture.getByRole('button', { name: '打包检查', exact: true }).click();
  const busy = fixture.getByRole('button', { name: '正在打包…', exact: true });
  await busy.waitFor();
  assert.equal(await busy.isDisabled(), true);
  assert.equal(await busy.getAttribute('aria-busy'), 'true');
  assert.equal(await busy.locator('.download-control-spinner').count(), 1);
  await page.getByRole('status').filter({ hasText: '模拟资源' }).getByRole('button', { name: '关闭通知' }).click();
  assert.equal(await busy.isDisabled(), true, '关闭提示不取消下载');
  releaseResponse();
  await page.getByRole('alert').filter({ hasText: '下载响应缺少文件名' }).waitFor();
  const retrySaved = page.waitForEvent('download');
  await fixture.getByRole('button', { name: '打包检查', exact: true }).click();
  const retryFile = await retrySaved;
  assert.equal(retryFile.suggestedFilename(), 'download-pack.txt');
  assert.equal(await readFile(await retryFile.path(), 'utf8'), '打包下载检查');
  const closes = page.getByRole('button', { name: '关闭通知', exact: true });
  while (await closes.count()) await closes.first().click();
  await page.unroute('**/component-samples/download-check.txt');
  const packButtons = fixture.getByRole('button', { name: '剪映草稿包', exact: true });
  assert.equal(await packButtons.count(), 3);
  assert.equal(await packButtons.nth(1).isDisabled(), true);
  assert.equal(await packButtons.nth(2).isDisabled(), true);
  await page.route('**/component-samples/native-pack?*', route => {
    const query = new URL(route.request().url()).searchParams;
    assert.equal(query.get('scene'), 'C002');
    assert.equal(query.get('format'), 'jypack');
    return route.fulfill({ headers: { 'Content-Type': 'application/vnd.bytedance.jypack',
      'Content-Disposition': 'attachment; filename="fixture-C002.jypack"' }, body: 'native-container-fixture' });
  });
  const packSaved = page.waitForEvent('download');
  await packButtons.first().click();
  const packFile = await packSaved;
  assert.equal(packFile.suggestedFilename(), 'fixture-C002.jypack');
  assert.equal(await readFile(await packFile.path(), 'utf8'), 'native-container-fixture');
  await page.unroute('**/component-samples/native-pack?*');
  while (await closes.count()) await closes.first().click();
  const manifests = fixture.getByTestId('manifest-downloads');
  let manifestRequests = 0;
  await page.route('**/component-samples/manifest-check?*', route => {
    manifestRequests++;
    const format = new URL(route.request().url()).searchParams.get('format');
    return route.fulfill({ headers: { 'Content-Disposition': `attachment; filename="manifest.${format}"` }, body: 'explicit-manifest-fixture' });
  });
  assert.equal(manifestRequests, 0, '清单展示不打包');
  for (const [label, format] of [['下载剪映包', 'jypack'], ['下载 ZIP', 'zip']]) {
    const buttons = manifests.getByRole('button', { name: label, exact: true });
    assert.equal(await buttons.nth(1).isDisabled(), true);
    const saved = page.waitForEvent('download');
    await buttons.first().click();
    const file = await saved;
    assert.equal(file.suggestedFilename(), `manifest.${format}`);
    assert.equal(await readFile(await file.path(), 'utf8'), 'explicit-manifest-fixture');
  }
  assert.equal(manifestRequests, 2, '一点击一请求');
  await page.unroute('**/component-samples/manifest-check?*');
  for (const stage of ['后处理', '二采', '一采']) {
    const packages = fixture.getByLabel(stage + '交接包', { exact: true });
    const buttons = packages.locator('.stage-download-packages button');
    assert.deepEqual(await buttons.allTextContents(), ['视频 ZIP 包', '剪映草稿包']);
    const boxes = await buttons.evaluateAll(items => items.map(item => { const b = item.getBoundingClientRect(); return { top: b.top, left: b.left, right: b.right }; }));
    assert.equal(boxes[0].top, boxes[1].top, stage + '交接包按钮同行');
    assert(boxes[0].right < boxes[1].left, stage + '视频包在左');
  }
  const canvasGroup = fixture.getByLabel('一采原画布', { exact: true });
  assert.equal(await canvasGroup.getAttribute('open'), '');
  await page.route('**/component-samples/canvas-check', route => route.fulfill({
    headers: { 'Content-Disposition': 'attachment; filename="scene.workflow.json"' }, body: 'original-canvas-fixture',
  }));
  const canvasSaved = page.waitForEvent('download');
  await canvasGroup.getByRole('button', { name: 'scene.workflow.json', exact: true }).click();
  const canvasFile = await canvasSaved;
  assert.equal(canvasFile.suggestedFilename(), 'scene.workflow.json');
  assert.equal(await readFile(await canvasFile.path(), 'utf8'), 'original-canvas-fixture');
  await page.unroute('**/component-samples/canvas-check');
  const showcase = page.getByTestId('showcase');
  await showcase.getByRole('button', { name: '列表与分页', exact: true }).click();
  await page.route('**/api/component-samples/file', route => route.fulfill({
    headers: { 'Content-Disposition': 'inline; filename="component-sample.txt"' }, body: 'fixed sample only',
  }));
  const showcaseButtons = showcase.getByRole('button', { name: '下载剪映包', exact: true });
  assert.equal(await showcaseButtons.nth(1).isDisabled(), true);
  const showcaseSaved = page.waitForEvent('download');
  await showcaseButtons.first().click();
  assert.equal((await showcaseSaved).suggestedFilename(), 'component-sample.txt');
  await page.unroute('**/api/component-samples/file');
  while (await closes.count()) await closes.first().click();
  await fixture.screenshot({ path: join(tmpdir(), `nora-download-${width}.png`) });
  console.log(`下载组件：${width}px统一外观、长文件名、原文件/本地导出/打包保存、禁用、忙碌、错误重试及清单剪映/ZIP、原画布下载与空入口禁用通过。`);
}
