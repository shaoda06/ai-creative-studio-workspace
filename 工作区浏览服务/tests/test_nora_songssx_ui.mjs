// Real Nora page with an isolated API, in-memory opinions and generated sample media.
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
const service = fileURLToPath(new URL('../', import.meta.url));
const python = join(service, '.venv', ...(process.platform === 'win32' ? ['Scripts', 'python.exe'] : ['bin', 'python']));
execFileSync(python, ['-B', '-c', `
from pathlib import Path
import sys
from backend.services import episode_downloads

clip, directory = map(Path, sys.argv[1:])
episode_downloads.DOWNLOAD_DIRECTORY = directory
for count in (1, 2):
    files = [(clip, f'C{i:03d}.mp4') for i in range(1, count + 1)]
    for format_ in ('zip', 'jypack'):
        response = episode_downloads.zip_response(files, '本轮视频.zip', format_, videos_only=True)
        Path(response.path).replace(directory / f'{count}.{format_}')
`, clip, output], { cwd: service });
const packages = new Map(await Promise.all(['1.zip', '1.jypack', '2.zip', '2.jypack']
  .map(async key => [key, await readFile(join(output, key))])));
const unexpected = [];
const savedNotes = {};
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
const round = (number, songssx, run, stage = songssx ? '场次生成' : '一采', available = true) => ({
  number, episodeRound: true, created_at: '2026-11-11T12:00:00+08:00', note: '隔离审阅示例',
  script: null, storyboard: null, issues: [],
  segments: ids.map(id => ({ id, stage, run, duration: 10,
    scriptHtml: '<p>' + id + ' 的隔离分镜内容</p>' })),
  ...(songssx ? { songssx: { recorded: true, video: { ...video('整场-' + run, stage, run), ...(!available ? { url: '', taskStatus: '排队中' } : {}) },
    segments: ids.map((id, i) => ({ id, gen: i + 1, start: [0, 14.375, 22.375][i], end: [14.375, 22.375, 32.292][i],
      context: { scriptHtml: '<p>' + id + ' 隔离分镜</p>', issues: [], shotTimingSource: 'plan',
        shots: [{ id: 'SH00' + (i + 1), duration: 10, html: '<p>' + id + ' 当前镜头</p>' }],
        prompts: { english: 'GEN ' + (i + 1) + ' isolated prompt.', chinese: id + ' 中文提示词示例。' },
        references: { common: [], segment: [{ name: id + ' 参考图', label: '<Picture 1>', kind: 'image',
          url: '/component-samples/image.svg?segment=' + id }] },
      } })) } } : {}),
});
const detail = episode => {
  const aimixer = episode.name !== 'EP002', songssx = episode.name !== 'EP001';
  const sceneRounds = [...(aimixer ? [round(1, false, 'R001')] : []),
    ...(songssx ? [round(2, true, 'R002'), round(3, true, 'R003', '后处理')] : [])];
  const scenes = songssx ? ['C001', 'C002'] : ['C001'];
  return { ...episode, scenes, productionWorkflows: [...(aimixer ? ['aimixer'] : []), ...(songssx ? ['songssx'] : [])],
    episodeRounds: sceneRounds.map(item => ({ number: item.number, scenes: item.number === 3 ? scenes : ['C001'] })),
    sceneRounds: { C001: sceneRounds, ...(songssx ? { C002: [round(3, true, 'R004', '后处理', episode.name === 'EP002')] } : {}) },
    segments: Object.fromEntries(scenes.map(scene => [scene, ids.map(id => ({ id, duration: 10, scriptHtml: '<p>' + id + '</p>',
      videos: aimixer && scene === 'C001' ? [video(id + '-R001', '一采', 'R001')] : [] }))])),
  };
};
const server = await createServer({
  configFile: false, root: fileURLToPath(new URL('../frontend', import.meta.url)),
  define: { __APP_VERSION__: JSON.stringify('Nora preview') },
  server: { host: '127.0.0.1', port: 0 },
  plugins: [react(), { name: 'nora-songssx-fixture', configureServer(vite) {
    vite.middlewares.use(async (req, res, next) => {
      const address = new URL(req.url, 'http://fixture.invalid');
      const path = decodeURIComponent(address.pathname);
      if (path.startsWith('/sample/')) {
        res.setHeader('Content-Type', 'video/mp4');
        const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range || '');
        if (!range) return res.end(media);
        const start = Number(range[1]), end = range[2] ? Math.min(Number(range[2]), media.length - 1) : media.length - 1;
        res.writeHead(206, { 'Accept-Ranges': 'bytes', 'Content-Range': `bytes ${start}-${end}/${media.length}` });
        return res.end(media.subarray(start, end + 1));
      }
      if (!path.startsWith('/api/')) return next();
      const download = /\/episodes\/(EP002|EP003)\/rounds\/(2|3)\/download$/.exec(path);
      if (download) {
        const format = address.searchParams.get('format') === 'jypack' ? 'jypack' : 'zip';
        const count = download[1] === 'EP002' && download[2] === '3' ? 2 : 1;
        res.writeHead(200, { 'Content-Type': format === 'zip' ? 'application/zip' : 'application/vnd.bytedance.jypack',
          'Content-Disposition': `attachment; filename="round-${download[2]}-${count}.${format}"` });
        return res.end(packages.get(`${count}.${format}`));
      }
      const noteScene = /\/revision-notes\/(EP\d+)\/(C\d+)$/.exec(path);
      const send = value => { res.setHeader('Content-Type', 'application/json'); return res.end(JSON.stringify(value)); };
      if (noteScene && req.method === 'PUT') {
        const chunks = [];
        for await (const chunk of req) chunks.push(chunk);
        const { expectedText, expectedDialogueEdits, ...note } = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        const sceneNotes = (savedNotes[noteScene[1]] ??= {})[noteScene[2]] ??= { notes: {}, rounds: {} };
        const key = `round/${note.roundNumber}/${note.segment}/${note.stage}/${note.run}`;
        sceneNotes.notes[key] = { ...note, updatedAt: new Date().toISOString() };
        return send(sceneNotes.notes[key]);
      }
      if (req.method !== 'GET') { unexpected.push(req.method + ' ' + path); res.writeHead(405); return res.end(); }
      let value;
      if (path === '/api/workspaces') value = [{ id: 'nora', name: 'Nora 示例空间', view: 'serial-drama', projects: [{ id: title, name: title }] }];
      else if (path === '/api/projects') value = [{ id: title, name: title }];
      else if (path.endsWith('/status')) value = { revision: 1, updating: false, checking: false };
      else if (path.endsWith('/overview')) value = { active: [], warnings: [], directories: [{ name: '00-项目定位', label: '项目定位' }, { name: '09-剧集制作', label: '剧集制作' }] };
      else if (path.endsWith('/sections/00-项目定位')) value = { exists: false, groups: [] };
      else if (path.endsWith('/sections/09-剧集制作')) value = { kind: 'group', statistics: { total: 3, completed: 0, notStarted: 0, running: 3 }, children: episodes };
      else if (path.includes('/episodes/')) value = detail(episodes.find(episode => path.endsWith('/' + episode.name)));
      else if (noteScene) value = savedNotes[noteScene[1]]?.[noteScene[2]] || { rounds: {}, notes: {} };
      else if (path.includes('/revision-notes/')) value = { rounds: {}, scenes: savedNotes[path.split('/').at(-1)] || {} };
      else { unexpected.push(path); res.statusCode = 404; value = {}; }
      return send(value);
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
  const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--autoplay-policy=no-user-gesture-required'] });
  try {
    for (const [width, height] of [[1280, 640], [1366, 768], [1920, 1080]]) {
      const page = await browser.newPage({ viewport: { width, height } });
      delete savedNotes.EP002;
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
      const references = page.getByRole('region', { name: '参考素材区域' });
      await references.getByRole('button', { name: /P001 参考图/ }).waitFor();
      await page.getByRole('button', { name: /^分段 P003/ }).click();
      await page.waitForFunction(() => {
        const video = document.querySelector('.segment-video video');
        return video && !video.paused && video.currentTime >= 22.3 && video.currentTime < 24;
      });
      assert.equal(await player.getAttribute('src'), src);
      assert.equal(await page.getByText('GEN 3 · 22.375–32.292 秒').count(), 1);
      await references.getByRole('button', { name: /P003 参考图/ }).waitFor();
      await page.getByRole('button', { name: '提示词', exact: true }).click();
      await page.locator('.segment-prompt-text').filter({ hasText: 'P003 中文提示词示例。' }).waitFor();
      await page.getByRole('button', { name: '英文', exact: true }).click();
      await page.locator('.segment-prompt-text').filter({ hasText: 'GEN 3 isolated prompt.' }).waitFor();
      await player.evaluate(video => video.pause());
      await page.getByRole('button', { name: '修改意见', exact: true }).click();
      const opinion = page.getByRole('textbox', { name: '修改意见', exact: true });
      await opinion.fill('第三段隔离意见');
      const saved = page.waitForResponse(response => response.request().method() === 'PUT' && response.url().endsWith('/revision-notes/EP002/C001'));
      await opinion.blur();
      assert.equal((await saved).ok(), true);
      assert.equal(savedNotes.EP002.C001.notes['round/3/P003/后处理/R003'].text, '第三段隔离意见');
      await page.getByRole('button', { name: '宽屏显示' }).click();
      await page.getByRole('button', { name: /^分段 P002/ }).click();
      await page.waitForFunction(() => {
        const video = document.querySelector('.segment-video video');
        return video && !video.paused && video.currentTime >= 14.3 && video.currentTime < 16;
      });
      await page.getByRole('button', { name: '恢复布局' }).click();
      await page.getByText('第3轮整场视频已准备 1／1').waitFor();
      assert.equal(await player.getAttribute('controlslist'), 'nodownload');
      assert.equal(await page.getByRole('combobox', { name: '版本切换' }).count(), 0);
      const downloads = page.getByRole('button', { name: '资源下载', exact: true });
      const segmentsTab = page.getByRole('button', { name: '分段制作', exact: true });
      const downloadFile = async (button, name) => {
        const file = page.waitForEvent('download');
        await page.getByRole('button', { name: button, exact: true }).click();
        assert.equal((await file).suggestedFilename(), name);
      };
      await downloads.click();
      assert.deepEqual(await page.getByRole('region', { name: '本轮资源' }).getByRole('button').allTextContents(),
        ['本轮打包下载', '剪映草稿下载']);
      await downloadFile('本轮打包下载', 'round-3-2.zip');
      await downloadFile('剪映草稿下载', 'round-3-2.jypack');
      await segmentsTab.click();
      await page.getByRole('checkbox', { name: '连续播放' }).check();
      await player.evaluate(async video => {
        if (!Number.isFinite(video.duration)) await new Promise(resolve => video.addEventListener('loadedmetadata', resolve, { once: true }));
        video.currentTime = video.duration - 0.1;
        await video.play();
      });
      await page.waitForFunction(() => {
        const video = document.querySelector('.segment-video video');
        return video?.getAttribute('aria-label')?.includes('R004') && !video.paused;
      });
      assert.equal(await selector.getAttribute('data-value'), '3');
      await selector.click();
      await page.getByRole('option', { name: /^第2轮/ }).click();
      await page.waitForFunction(() => document.querySelector('.segment-video video')?.getAttribute('aria-label')?.includes('场次生成 · R002'));
      await downloads.click();
      await downloadFile('本轮打包下载', 'round-2-1.zip');
      await downloadFile('剪映草稿下载', 'round-2-1.jypack');
      await segmentsTab.click();
      await page.getByRole('button', { name: '轮次记录' }).click();
      const records = page.getByRole('dialog', { name: '轮次记录' });
      await records.getByRole('button', { name: '整场视频 · R002' }).click();
      assert.equal(await page.getByRole('dialog', { name: '整场视频 · R002' }).locator('video').getAttribute('controlslist'), 'nodownload');
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
      await page.getByRole('checkbox', { name: '连续播放' }).check();
      await player.evaluate(async video => {
        if (!Number.isFinite(video.duration)) await new Promise(resolve => video.addEventListener('loadedmetadata', resolve, { once: true }));
        video.currentTime = video.duration - 0.1;
        await video.play();
      });
      await page.getByText('C002 本轮整场视频暂不可播。连续播放已停止。').waitFor();
      assert.equal(await page.getByRole('checkbox', { name: '连续播放' }).isChecked(), false);
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
