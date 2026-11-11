// Real Nora page with a read-only, isolated API and generated sample media.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const { createServer } = await import(require.resolve('vite'));
const react = (await import(require.resolve('@vitejs/plugin-react'))).default;
const output = await mkdtemp(join(tmpdir(), 'nora-songssx-'));
const clip = join(output, 'scene.mp4');
execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=0x263a42:s=384x216:r=24:d=33',
  '-vf', "drawbox=x=0:y=0:w=iw:h=ih:color=0x425a4b:t=fill:enable='gte(t,14.375)',drawbox=x=0:y=0:w=iw:h=ih:color=0x514557:t=fill:enable='gte(t,22.375)'",
  '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-movflags', '+faststart', clip]);
const media = await readFile(clip);
const unexpected = [];
const ids = ['P001', 'P002', 'P003'];
const title = 'Nora 制作页示例';
const episodes = [
  { kind: 'group', name: 'EP001', key: 'EP001', title: 'AiMixer 历史制作' },
  { kind: 'group', name: 'EP002', key: 'EP002', title: 'Songssx 场次制作' },
  { kind: 'group', name: 'EP003', key: 'EP003', title: '两套正式记录' },
];
const video = (key, stage, run) => ({ key, stage, run, url: '/sample/' + key + '.mp4', fileRevision: key,
  approved: false, candidateNumber: Number(run.slice(1)), taskStatus: '成功', deliveryStatus: '已取回', checkedAt: '',
  context: { scriptHtml: '<p>隔离分镜</p>', issues: [], shots: [], prompts: {}, references: { common: [], segment: [] } } });
const round = (number, songssx, run) => ({
  number, episodeRound: true, created_at: '2026-11-11T12:00:00+08:00', note: '隔离审阅示例',
  script: null, storyboard: null, issues: [],
  segments: ids.map(id => ({ id, stage: songssx ? '场次生成' : '一采', run, duration: 10,
    scriptHtml: '<p>' + id + ' 的隔离分镜内容</p>' })),
  ...(songssx ? { songssx: { recorded: true, video: video('整场-' + run, '场次生成', run),
    segments: ids.map((id, i) => ({ id, gen: i + 1, start: [0, 14.375, 22.375][i], end: [14.375, 22.375, 32.292][i] })) } } : {}),
});
const detail = episode => {
  const aimixer = episode.name !== 'EP002', songssx = episode.name !== 'EP001';
  const sceneRounds = [...(aimixer ? [round(1, false, 'R001')] : []),
    ...(songssx ? [round(2, true, 'R002'), round(3, true, 'R003')] : [])];
  return { ...episode, scenes: ['C001'], productionWorkflows: [...(aimixer ? ['aimixer'] : []), ...(songssx ? ['songssx'] : [])],
    episodeRounds: sceneRounds.map(item => ({ number: item.number, scenes: ['C001'] })),
    sceneRounds: { C001: sceneRounds },
    segments: { C001: ids.map(id => ({ id, duration: 10, scriptHtml: '<p>' + id + '</p>',
      videos: aimixer ? [video(id + '-R001', '一采', 'R001')] : [] })) },
  };
};
const server = await createServer({
  configFile: false, root: fileURLToPath(new URL('../frontend', import.meta.url)),
  define: { __APP_VERSION__: JSON.stringify('Nora preview') },
  server: { host: '127.0.0.1', port: 0 },
  plugins: [react(), { name: 'nora-songssx-fixture', configureServer(vite) {
    vite.middlewares.use((req, res, next) => {
      const path = decodeURIComponent(new URL(req.url, 'http://fixture.invalid').pathname);
      if (path.startsWith('/sample/')) {
        res.setHeader('Content-Type', 'video/mp4');
        const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range || '');
        if (!range) return res.end(media);
        const start = Number(range[1]), end = range[2] ? Math.min(Number(range[2]), media.length - 1) : media.length - 1;
        res.writeHead(206, { 'Accept-Ranges': 'bytes', 'Content-Range': `bytes ${start}-${end}/${media.length}` });
        return res.end(media.subarray(start, end + 1));
      }
      if (!path.startsWith('/api/')) return next();
      if (req.method !== 'GET') { unexpected.push(req.method + ' ' + path); res.writeHead(405); return res.end(); }
      let value;
      if (path === '/api/workspaces') value = [{ id: 'nora', name: 'Nora 示例空间', view: 'serial-drama', projects: [{ id: title, name: title }] }];
      else if (path === '/api/projects') value = [{ id: title, name: title }];
      else if (path.endsWith('/status')) value = { revision: 1, updating: false, checking: false };
      else if (path.endsWith('/overview')) value = { active: [], warnings: [], directories: [{ name: '00-项目定位', label: '项目定位' }, { name: '09-剧集制作', label: '剧集制作' }] };
      else if (path.endsWith('/sections/00-项目定位')) value = { exists: false, groups: [] };
      else if (path.endsWith('/sections/09-剧集制作')) value = { kind: 'group', statistics: { total: 3, completed: 0, notStarted: 0, running: 3 }, children: episodes };
      else if (path.includes('/episodes/')) value = detail(episodes.find(episode => path.endsWith('/' + episode.name)));
      else if (path.includes('/revision-notes/')) value = { rounds: {}, notes: {} };
      else { unexpected.push(path); res.statusCode = 404; value = {}; }
      res.setHeader('Content-Type', 'application/json');
      return res.end(JSON.stringify(value));
    });
  } }],
});
await server.listen();
const link = `http://127.0.0.1:${server.httpServer.address().port}/tests/project-switch.html#/projects/${encodeURIComponent(title)}`;
console.log(link);
if (process.argv.includes('--preview')) {
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, async () => {
    await server.close();
    await rm(output, { recursive: true, force: true });
    process.exit(0);
  });
} else {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const [width, height] of [[1280, 640], [1366, 768], [1920, 1080]]) {
      const page = await browser.newPage({ viewport: { width, height } });
      page.setDefaultTimeout(10000);
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(link);
      await page.getByRole('button', { name: '剧集制作', exact: true }).click();
      const episode = name => page.locator(`[data-episode="${name}"]`);
      await episode('EP001').waitFor();
      const go = async name => {
        if (!await episode(name).isVisible()) {
          const picker = page.getByRole('combobox', { name: '快速选择制作对象' });
          await picker.click();
          await page.getByRole('option', { name: new RegExp(name) }).click();
        } else await episode(name).click();
      };
      const selector = page.getByRole('combobox', { name: '修改轮次' });
      const chooser = page.getByRole('region', { name: '选择制作记录' });
      const player = page.locator('.segment-video video');
      await go('EP001');
      await player.waitFor();
      assert.equal(await chooser.count(), 0);
      const firstClip = await player.getAttribute('src');
      await page.getByRole('button', { name: /^分段 P002/ }).click();
      assert.equal(await page.getByRole('combobox', { name: '版本切换' }).getAttribute('data-value'), 'P002-R001');
      assert.notEqual(await player.getAttribute('src'), firstClip);
      await go('EP002');
      await player.waitFor();
      assert.equal(await chooser.count(), 0);
      assert.equal(await selector.getAttribute('data-value'), '3');
      const src = await player.getAttribute('src');
      await page.getByRole('button', { name: /^分段 P003/ }).click();
      await page.waitForFunction(() => {
        const video = document.querySelector('.segment-video video');
        return video && !video.paused && video.currentTime >= 22.3 && video.currentTime < 24;
      });
      assert.equal(await player.getAttribute('src'), src);
      assert.equal(await page.getByText('GEN 3 · 22.375–32.292 秒').count(), 1);
      await page.getByRole('button', { name: '宽屏显示' }).click();
      await page.getByRole('button', { name: /^分段 P002/ }).click();
      await page.waitForFunction(() => {
        const video = document.querySelector('.segment-video video');
        return video && !video.paused && video.currentTime >= 14.3 && video.currentTime < 16;
      });
      await selector.click();
      await page.getByRole('option', { name: /^第2轮/ }).click();
      await page.waitForFunction(() => document.querySelector('.segment-video video')?.getAttribute('src')?.includes('R002'));
      await page.getByRole('button', { name: '轮次记录' }).click();
      const records = page.getByRole('dialog', { name: '轮次记录' });
      assert.equal(await records.getByRole('button', { name: '整场视频 · R002' }).count(), 1);
      await page.keyboard.press('Escape');
      await go('EP003');
      await chooser.waitFor();
      assert.equal(await player.count(), 0);
      await chooser.getByRole('button', { name: 'AiMixer 制作记录' }).click();
      await player.waitFor();
      assert.equal(await selector.getAttribute('data-value'), '1');
      await go('EP002');
      await go('EP003');
      await chooser.getByRole('button', { name: 'Songssx 制作记录' }).click();
      await player.waitFor();
      assert.equal(await selector.getAttribute('data-value'), '3');
      assert.equal(await page.getByRole('button', { name: 'AiMixer 制作记录' }).count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []);
      await page.close();
    }
    assert.deepEqual(unexpected, []);
    console.log('Nora single workflow, mixed records, round playback and seeking passed at all three desktop sizes.');
  } finally {
    await browser.close();
    await server.close();
    await rm(output, { recursive: true, force: true });
  }
}
