// Standalone browser regression: synthetic project, complete local APIs and synthetic media.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(require.resolve('vite'));
const react = (await import(require.resolve('@vitejs/plugin-react'))).default;
const project = '连续播放示例';
const media = await readFile(new URL('../frontend/public/component-samples/video.webm', import.meta.url));
const out = await mkdtemp(path.join(os.tmpdir(), 'nora-episode-playback-'));
const unexpected = [], writes = [];
const data = { kind: 'group', name: 'EP003', title: '雨天送伞', children: [], script: null };
const video = (scene, id, run, pending = false) => ({ key: `${scene}-${id}-${run}`, stage: '一采', run, url: pending ? '' : `/fixture-${scene}-${id}-${run}.mp4`, approved: false, candidateNumber: Number(run.slice(1)), fileRevision: '', deliveryStatus: pending ? '未取回' : '已取回', taskStatus: pending ? '排队中' : '成功', context: { scriptHtml: '<p>fixture</p>', shots: [], prompts: {}, references: { common: [], segment: [] }, issues: [] } });
  const round = (number, ids, run) => ({ number, issues: [], segments: ids.map(id => ({ id, duration: 1, stage: '一采', run, scriptHtml: '<p>fixture</p>' })), script: null, storyboard: null });
  data.scenes = ['C001', 'C002', 'C003']; data.episodeRounds = []; data.previousEpisode = null; data.productionIssues = []; data.warnings = [];
  data.materials = []; data.directorSheets = {}; data.storyboards = {};
  data.segments = {
    C001: ['P003', 'P001'].map(id => ({ id, duration: 1, videos: [video('C001', id, 'R001')] })),
    C002: [{ id: 'P004', duration: 1, videos: [video('C002', 'P004', 'R001'), video('C002', 'P004', 'R002')] }],
    C003: [{ id: 'P001', duration: 1, videos: [video('C003', 'P001', 'R001')] }],
  };
  data.sceneRounds = { C001: [round(1, ['P003', 'P001'], 'R001')], C002: [round(1, ['P004'], 'R001'), round(2, ['P004'], 'R002')], C003: [round(1, ['P001'], 'R001')] };
const server = await createServer({ configFile: false, root: fileURLToPath(new URL('../frontend', import.meta.url)), cacheDir: path.join(out, 'vite'),
  define: { __APP_VERSION__: JSON.stringify('playback-fixture') }, server: { host: '127.0.0.1', port: 0 },
  plugins: [react(), { name: 'continuous-playback-fixture', configureServer(vite) { vite.middlewares.use((req, res, next) => {
    const url = decodeURIComponent(new URL(req.url, 'http://fixture.invalid').pathname);
    if (url.startsWith('/fixture-')) { res.setHeader('Content-Type', 'video/webm'); return res.end(media); }
    if (!url.startsWith('/api/')) return next();
    if (req.method !== 'GET') { writes.push(url); res.statusCode = 405; return res.end(); }
    let response;
    if (url === '/api/workspaces') response = [{ id: 'nora', name: 'Nora示例空间', view: 'serial-drama', projects: [{ id: project, name: project }] }];
    else if (url === '/api/projects') response = [{ id: project, name: project }];
    else if (url.endsWith('/status')) response = { revision: 1, updating: false, checking: false };
    else if (url.endsWith('/overview')) response = { active: [], warnings: [], directories: [{ name: '00-项目定位', label: '项目定位' }, { name: '09-剧集制作', label: '剧集制作' }] };
    else if (url.endsWith('/sections/00-项目定位')) response = { exists: false, groups: [] };
    else if (url.endsWith('/sections/09-剧集制作')) response = { kind: 'group', statistics: { total: 1, completed: 0, notStarted: 0, running: 1 }, children: [{ kind: 'group', name: 'EP003', title: data.title, key: 'EP003' }] };
    else if (url.endsWith('/episodes/EP003')) response = data;
    else if (url.includes('/revision-notes/')) response = { rounds: {}, notes: {} };
    else { unexpected.push(url); res.statusCode = 404; response = {}; }
    res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(response));
  }); } }],
});
await server.listen();
const base = `http://127.0.0.1:${server.httpServer.address().port}`;
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome', headless: true, args: ['--autoplay-policy=no-user-gesture-required'] });
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.route('**/*', route => {
    assert.equal(new URL(route.request().url()).origin, base, 'no request may leave the isolated server');
    return route.continue();
  });
  await page.goto(base + '/tests/project-switch.html#/projects/' + encodeURIComponent(project));
  await page.getByRole('button', { name: '剧集制作', exact: true }).click();
  await page.getByRole('button').filter({ hasText: 'EP003' }).first().click();
  const scene = id => page.getByRole('button', { name: new RegExp('^场次 ' + id + '(?: ·|$)') });
  const checked = page.getByRole('checkbox', { name: '连续播放', exact: true });
  const selectedScene = id => scene(id).getAttribute('aria-current');
  const chooseRound = async number => {
    await page.getByRole('combobox', { name: '修改轮次', exact: true }).click();
    await page.getByRole('option', { name: new RegExp('^第' + number + '轮') }).click();
  };
  const end = () => page.locator('.segment-video video').dispatchEvent('ended');
  // Remember a historical round in the following scene, then start at C001.
  await scene('C002').click(); await chooseRound(1); await scene('C001').click();
  await checked.check(); await end();
  await page.locator('[aria-label^="分段 P001，"][aria-pressed="true"]').waitFor();
  await end();
  await page.locator('[aria-label="场次 C002 内容"]').waitFor({ timeout: 5000 });
  assert.equal(await checked.isChecked(), true, 'keep continuous playback across remount');
  await page.waitForFunction(() => { const video = document.querySelector('.segment-video video'); return video?.autoplay && !video.paused && video.currentTime > 0; });
  await page.screenshot({ path: path.join(out, 'cross-scene-playing.png') });
  assert.match(await page.getByRole('combobox', { name: '版本切换', exact: true }).getAttribute('data-value'), /R001$/, 'respect selected historical round');
  await end();
  await page.locator('[aria-label="场次 C003 内容"]').waitFor();
  await end();
  assert.equal(await selectedScene('C003'), 'page', 'last scene must not wrap');
  // Manual navigation preserves the playback preference; explicit cancellation stops advancement.
  await scene('C001').click(); await page.getByRole('button', { name: /^分段 P001，/ }).click();
  assert.equal(await checked.isChecked(), true, 'manual navigation preserves the continuous-playback preference');
  await checked.check(); await checked.uncheck(); await end();
  assert.equal(await selectedScene('C001'), 'page');
  // Missing next-scene round or video stops at current scene, without older fallback.
  for (const missing of ['video', 'round']) {
    if (missing === 'video') data.segments.C002[0].videos[0] = video('C002', 'P004', 'R001', true);
    else data.sceneRounds.C002 = [];
    await page.reload();
    await scene('C002').click();
    if (missing === 'video') await chooseRound(1);
    await scene('C001').click(); await page.getByRole('button', { name: /^分段 P001，/ }).click();
    await checked.check(); await end();
    assert.equal(await selectedScene('C001'), 'page');
    await page.getByText(/C002.*连续播放已停止/).waitFor();
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(unexpected, []);
  assert.deepEqual(writes, []);
  await page.screenshot({ path: path.join(out, 'missing-next-scene.png') });
  console.log('PASS: intra-scene order, cross-scene handoff, selected round, preserved checkbox, episode end, cancel, missing media/round; no page errors; temporary fixture files are removed.');
} finally { await browser.close(); await server.close(); await rm(out, { recursive: true, force: true }); }
