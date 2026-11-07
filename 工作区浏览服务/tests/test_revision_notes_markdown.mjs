import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const ts = require('typescript');
const source = await readFile(new URL('../frontend/src/revisionNotesMarkdown.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { revisionNotesMarkdown: format } = await import('data:text/javascript;base64,' + Buffer.from(javascript).toString('base64'));
const review = { project: '导出示例', episode: 'EP005', episodeTitle: '雨天送伞', number: 2, history: false, notes: [], rounds: [], combinationHistory: [], legacyRounds: [] };
const note = { scene: 'C001', segment: 'P006', roundNumber: 2, stage: '一采', run: 'R002', text: '', fileRevision: 'fixture', editable: true };
const edit = { shot: 'EP005-C001-SH018', index: 0, speaker: '女主', original: '拿好伞，我们出发。', replacement: '带上伞，慢慢走。' };

test('本轮按场次、分段、类别导出，汇总与场次同级且不重复候选版本', () => {
 const input = { ...review, notes: [{ ...note, dialogueEdits: [edit], text: '00.04.0秒，SH018：递伞的动作再清楚一点。' },
  { ...note, scene: 'C003', segment: 'P001', text: '雨伞保持一致。', run: 'R007', stage: '二采' }], rounds: [{ number: 2, text: '整体自然一点。' }] };
 const original = structuredClone(input);
 assert.equal(format(input), `# EP005｜第2轮修改意见

- 项目：导出示例
- 本集：雨天送伞

## 场次 C001

### 分段 P006

#### 台词修改

##### SH018｜女主

**原台词**：拿好伞，我们出发。

**修改为**：带上伞，慢慢走。

#### 普通修改意见

##### SH018｜00:04.0

递伞的动作再清楚一点。

## 场次 C003

### 分段 P001

#### 普通修改意见

雨伞保持一致。

## 本轮汇总意见

整体自然一点。`);
 assert.deepEqual(input, original, '导出不修改原意见及版本映射');
});

test('镜号和时间排序，多行与无时间前言保持，空类别不输出', () => {
 const text = format({ ...review, notes: [{ ...note, text: '全段意见。\n00.08.0秒，SH019：先看路。\n视线保持。\n00.04.0秒，SH018：动作干脆。\nSH020：' }] });
 assert.ok(text.indexOf('##### SH018｜00:04.0') < text.indexOf('##### SH019｜00:08.0'));
 assert.ok(text.includes('全段意见。') && text.includes('先看路。\n视线保持。'));
 assert.ok(!text.includes('#### 台词修改') && !text.includes('##### SH020') && !text.includes('## 本轮汇总意见'));
});

test('只有台词仍导出，空建议省略，同镜同人重复接话保留句序', () => {
 const text = format({ ...review, notes: [{ ...note, dialogueEdits: [edit, { ...edit, index: 2, original: '我来。', replacement: '让我来。' }, { ...edit, index: 3, replacement: '' }] }, { ...note, segment: 'P008', text: '  ' }] });
 assert.ok(text.includes('##### SH018｜女主｜第1句') && text.includes('##### SH018｜女主｜第3句'));
 assert.ok(!text.includes('#### 普通修改意见') && !text.includes('分段 P008'));
});

test('历史按真实轮次分组，保留阶段R及场次历史归属', () => {
 const text = format({ ...review, history: true, notes: [{ ...note, text: '第二轮意见。' }, { ...note, roundNumber: 1, run: 'R001', text: '第一轮意见。' }, { ...note, roundNumber: 5, editable: false, text: '场次历史意见。' }], rounds: [{ number: 2, text: '第二轮汇总。' }], legacyRounds: [{ scene: 'C001', number: 5, text: '旧整场汇总。' }] });
 assert.ok(text.indexOf('## 第1轮') < text.indexOf('## 第2轮'));
 assert.ok(text.includes('#### 分段 P006（一采 · R001）') && text.includes('### 本轮汇总意见'));
 assert.ok(text.includes('## 场次历史意见') && text.includes('场次第5轮 · 一采 · R002') && text.includes('旧整场汇总。'));
 assert.ok(!text.includes('## 第5轮'), '不把场次历史冒充真实整集轮次');
});

test('旧场次组合显示实际场次轮号，不虚构整集轮次', () => {
 const text = format({ ...review, number: undefined, combination: { scenes: { C002: 7, C001: 5 }, text: '组合总体意见。' }, notes: [{ ...note, editable: false, roundNumber: 5, text: '局部意见。' }] });
 assert.ok(text.startsWith('# EP005｜当前组合修改意见'));
 assert.ok(text.includes('- 场次组合：C001第5轮、C002第7轮'));
 assert.ok(text.endsWith('## 本轮汇总意见\n\n组合总体意见。'));
});
