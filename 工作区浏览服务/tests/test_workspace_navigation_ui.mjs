// Actual common app, isolated read-only responses; no production API or generation.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(require.resolve('vite'));
const react = (await import(require.resolve('@vitejs/plugin-react'))).default;
const version = JSON.parse(await readFile(new URL('../frontend/package.json', import.meta.url))).version;
const out = await mkdtemp(tmpdir() + '/nora-workspaces-ui-');
const server = await createServer({ configFile: false, root: fileURLToPath(new URL('../frontend', import.meta.url)), plugins: [react()], define: { __APP_VERSION__: JSON.stringify(version) }, server: { host: '127.0.0.1', port: 0 } });
await server.listen();
const origin = `http://127.0.0.1:${server.httpServer.address().port}`;
const browser = await chromium.launch({ channel: 'chrome', headless: true });
let activePage;
const allErrors = [];
const spaces = [{ id: 'nora', name: '短剧空间示例', view: 'serial-drama', projects: [{ id: '同名示例', name: '同名示例' }] },
  { id: 'commercial', name: '商业空间示例', view: 'files', projects: [{ id: '同名示例', name: '同名示例' }] }];
const projectBase = '/api/workspaces/commercial/projects/' + encodeURIComponent('同名示例');
try {
 for (const width of [1362]) {
  const page = activePage = await browser.newPage({ viewport: { width, height: 918 } });
  const errors = [], forbidden = [], requests = [];
  page.on('pageerror', error => (errors.push(error.message), allErrors.push(error.message)));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.route('**/api/**', route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname;
    requests.push(path);
    if (request.method() !== 'GET') { forbidden.push(path); return route.abort(); }
    if (path === '/api/service') return route.fulfill({ json: { version, ready: true } });
    if (path === '/api/workspaces') return route.fulfill({ json: spaces });
    if (path === '/api/task-monitor') return route.fulfill({ json: {
      tasks: [], local_tasks: spaces.map((space,index) => ({ id: space.id+'-fixture', title: index ? '商业空间测试任务' : '短剧空间测试任务', workspace_name: space.name, api_prefix: '/api/workspaces/'+space.id, project: '同名示例', task_type: 'image', status: 'local_queued', queue: 'local', category: 'queued', created_at: '2026-11-01T00:00:00Z', remote_url: 'http://fixture-node' })),
      remote_nodes: [{ url: 'http://fixture-node', name: '隔离节点', connection: 'connected', queue: [], running_count: 0, queued_count: 0, updated_at: '2026-11-01T00:00:00Z' }],
      local_counts: { 'http://fixture-node': { queued: 2, paused: 0, history: 0 } }, history_updated_at: {} } });
    if (path === projectBase) return route.fulfill({ json: { name: '同名示例', files: [
      { kind: 'file', name: 'README.md', key: 'README.md', url: projectBase + '/files/README.md' },
      { kind: 'group', name: '资产', children: [{ kind: 'file', name: '参考.png', key: '资产/参考.png', url: projectBase + '/files/' + encodeURIComponent('资产/参考.png') }] },
      { kind: 'file', name: '样片.webm', key: '样片.webm', url: projectBase + '/files/' + encodeURIComponent('样片.webm') },
    ] } });
    if (path === projectBase + '/document') return route.fulfill({ json: { title: '商业资料', html: '<h1>商业资料隔离正文</h1><p>使用公共浏览能力展示本项目资料。</p>' } });
    if (path.includes('/files/') && path.endsWith('.png')) return route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jLyoAAAAASUVORK5CYII=', 'base64') });
    if (path.includes('/files/') && path.endsWith('.webm')) return route.fulfill({ contentType: 'video/webm', path: fileURLToPath(new URL('../frontend/public/component-samples/video.webm', import.meta.url)) });
    forbidden.push(path); return route.abort();
  });
  await page.goto(origin + '/');
  await page.getByRole('heading', { name: '一级项目空间' }).waitFor();
  assert.equal(await page.title(), 'AI创作工作台');
  await page.getByRole('link', { name: /商业空间示例.*业务项目/ }).waitFor();
  await page.screenshot({ path: `${out}/${width}-home.png` });
  assert.equal(await page.getByRole('link', { name: /资产管理/ }).count(), 1);
  await page.getByRole('button', { name: '展开任务进度', exact: true }).click();
  await page.getByText('短剧空间测试任务', { exact: true }).waitFor();
  await page.getByText('商业空间测试任务', { exact: true }).waitFor();
  await page.getByRole('button', { name: '收起任务进度', exact: true }).click();
  await page.getByRole('link', { name: /商业空间示例.*业务项目/ }).click();
  await page.getByRole('heading', { name: '业务项目' }).waitFor();
  await page.getByRole('link', { name: /同名示例/ }).filter({ hasText: '查看项目资料与素材' }).click();
  await page.getByRole('button', { name: 'README.md', exact: true }).click();
  await page.getByRole('dialog').getByRole('heading', { name: '商业资料隔离正文' }).waitFor();
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click();
  await page.getByText('资产', { exact: true }).click();
  await page.getByRole('button', { name: '参考.png', exact: true }).click();
  await page.getByRole('dialog').locator('img').waitFor();
  await page.getByRole('dialog').locator('img').evaluate(image => image.decode());
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click();
  await page.getByRole('button', { name: '样片.webm', exact: true }).click();
  const video = page.getByRole('dialog').locator('video');
  await video.evaluate(element => element.play());
  await page.waitForFunction(() => document.querySelector('dialog video')?.currentTime > 0);
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click();
  await page.getByRole('button', { name: '展开任务进度', exact: true }).click();
  await page.getByText('商业空间测试任务', { exact: true }).waitFor();
  await page.screenshot({ path: `${out}/${width}-project-tasks.png` });
  await page.getByRole('button', { name: '收起任务进度', exact: true }).click();
  await page.getByRole('link', { name: 'AI创作工作台', exact: true }).click();
  await page.getByRole('link', { name: /短剧空间示例.*业务项目/ }).click();
  const legacy = page.getByRole('link', { name: /同名示例/ }).filter({ hasText: '查看项目资料与素材' });
  assert.equal(await legacy.getAttribute('href'), '#/projects/' + encodeURIComponent('同名示例'));
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${width}: page overflow`);
  assert.deepEqual(errors, []);
  assert.deepEqual(forbidden, []);
  assert.ok(requests.includes(projectBase + '/document'));
  assert.ok(requests.includes('/api/task-monitor'));
  await page.close();
 }
 console.log('PASS: unified entry → space → project → document/image/video; global task visibility across navigation; old project URLs; 1362 desktop; no writes, external requests, errors. Screenshots: ' + out);
} catch (error) { console.error('Page:', activePage?.url(), 'Errors:', allErrors); if (activePage) { console.error((await activePage.locator('body').innerText()).slice(0, 2500)); await activePage.screenshot({path: out + '/failure.png'}); } throw error; } finally { await browser.close(); await server.close(); }
