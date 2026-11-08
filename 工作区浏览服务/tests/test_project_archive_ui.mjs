// Real application with read-only in-memory API responses; no project or Codex writes.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdtemp, readFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(require.resolve('vite'));
const react = (await import(require.resolve('@vitejs/plugin-react'))).default;
const version = JSON.parse(await readFile(new URL('../frontend/package.json', import.meta.url))).version;
const screenshots = await mkdtemp(path.join(os.tmpdir(), 'studio-project-archive-'));
const server = await createServer({ configFile: false, root: fileURLToPath(new URL('../frontend', import.meta.url)),
  plugins: [react()], define: { __APP_VERSION__: JSON.stringify(version) }, server: { host: '127.0.0.1', port: 0 } });
await server.listen();
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  for (const [width, height] of [[1280, 640], [1366, 768], [1920, 1080]]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [], unexpected = [];
    page.on('pageerror', error => errors.push(String(error)));
    const spaces = [
      { id: 'nora', name: 'Nora 隔离空间', view: 'serial-drama', reasons: ['暂缓制作', '已完成'] },
      { id: 'iris', name: 'Iris 隔离空间', view: 'iris-commercial', reasons: ['停止合作', '已完成'] },
      { id: 'chloe', name: 'Chloe 隔离空间', view: 'chloe-commerce', project_layout: 'nested', reasons: ['暂停运营', '停止运营'] },
    ].map(space => ({ ...space, projects: [
      { id: '进行中的项目', name: '进行中的项目' },
      ...space.reasons.map((reason, index) => ({ id: `归档项目${index + 1}`, name: `归档项目${index + 1}`,
        archive: { status: 'archived', reason, archivedAt: '2026-11-08T12:00:00+08:00', restoredAt: '无' } })),
    ] }));
    let fail = false;
    await page.route('**/api/**', route => {
      const url = decodeURIComponent(new URL(route.request().url()).pathname);
      if (route.request().method() !== 'GET') { unexpected.push(url); return route.abort(); }
      if (url === '/api/service') return route.fulfill({ json: { version, ready: true } });
      if (url === '/api/task-monitor') return route.fulfill({ json: { tasks: [], local_tasks: [], remote_nodes: [], local_counts: {}, history_updated_at: {} } });
      if (url === '/api/workspaces') return route.fulfill(fail ? { status: 409, json: { detail: '隔离项目：归档标记错误' } } : { json: spaces });
      if (url === '/api/project-index') return route.fulfill({ json: { title: '项目总索引', html: '<p>隔离索引</p>' } });
      if (url === '/api/workspaces/iris/projects/归档项目1') return route.fulfill({ json: { name: '归档项目1', files: [] } });
      unexpected.push(url);
      return route.fulfill({ status: 404, json: { detail: 'Unexpected fixture request' } });
    });
    for (const space of spaces) {
      await page.goto(server.resolvedUrls.local[0] + '#/spaces/' + space.id);
      await page.getByRole('button', { name: '进行中（1）', exact: true }).waitFor();
      await page.waitForFunction(count => document.querySelectorAll('.project-card').length === count, 1);
      assert.equal(await page.locator('.project-card').count(), 1);
      assert.match(await page.locator('.project-card').innerText(), /进行中的项目/);
      await page.getByRole('button', { name: '已归档（2）', exact: true }).click();
      await page.waitForFunction(count => document.querySelectorAll('.project-card').length === count, 2);
      assert.equal(await page.locator('.project-card').count(), 2);
      await page.getByRole('combobox', { name: '归档原因', exact: true }).click();
      await page.getByRole('option', { name: space.reasons[0], exact: true }).click();
      await page.waitForFunction(count => document.querySelectorAll('.project-card').length === count, 1);
      assert.equal(await page.locator('.project-card').count(), 1);
      assert.match(await page.locator('.project-card').innerText(), /02-归档项目1/);
      assert.ok((await page.locator('.project-card').innerText()).includes(space.reasons[0]));
      const expected = space.id === 'nora' ? '/projects/归档项目1' : `/spaces/${space.id}/${space.id === 'chloe' ? 'contexts' : 'projects'}/归档项目1`;
      assert.equal(decodeURIComponent(await page.locator('.project-card').getAttribute('href')), '#' + expected);
      await page.reload();
      await page.getByRole('combobox', { name: '归档原因', exact: true }).waitFor();
      await page.waitForFunction(count => document.querySelectorAll('.project-card').length === count, 1);
      assert.equal(await page.locator('.project-card').count(), 1);
      await page.getByRole('combobox', { name: '归档原因', exact: true }).click();
      await page.getByRole('option', { name: '全部原因', exact: true }).click();
      await page.waitForFunction(count => document.querySelectorAll('.project-card').length === count, 2);
      assert.equal(await page.locator('.project-card').count(), 2);
      await page.screenshot({ path: path.join(screenshots, `${space.id}-${width}.png`) });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    }
    await page.goto(server.resolvedUrls.local[0] + '#/spaces/iris?archive=1');
    await page.getByRole('link').filter({ hasText: '02-归档项目1' }).click();
    await page.getByRole('combobox', { name: '切换项目', exact: true }).click();
    await page.getByRole('option', { name: /归档项目1.*已归档.*停止合作/ }).waitFor();
    assert.ok(await page.evaluate(() => [...document.querySelectorAll('[role="listbox"]:popover-open')].every(el => {
      const r = el.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1;
    })));
    await page.keyboard.press('Escape');
    spaces[1].projects = [];
    await page.goto(server.resolvedUrls.local[0] + '#/spaces/iris');
    await page.reload();
    await page.getByText('暂无进行中的项目。', { exact: true }).waitFor();
    await page.getByRole('button', { name: '已归档（0）', exact: true }).click();
    await page.getByText('暂无已归档项目。', { exact: true }).waitFor();
    fail = true;
    await page.reload();
    await page.getByText('资料读取失败，请点击重新读取。', { exact: false }).first().waitFor();
    fail = false;
    await page.getByRole('button', { name: '重新读取', exact: true }).first().click();
    await page.getByText('暂无已归档项目。', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    assert.deepEqual(unexpected, []);
    await page.close();
  }
  console.log('PASS: three spaces, archive reasons, refresh, routes, switcher badges, empty/error recovery and three desktop sizes. Screenshots: ' + screenshots);
} finally { await browser.close(); await server.close(); }
