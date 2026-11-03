import type { NoteInput } from './revisionNotes';

type MarkdownNote = NoteInput & { scene: string; editable?: boolean };
interface Summary { number: number; text: string }
interface Combination { scenes: Record<string, number>; text: string }
export interface MarkdownReview {
  project: string; episode: string; episodeTitle?: string; number?: number; history: boolean;
  notes: MarkdownNote[]; rounds: Summary[];
  combination?: Combination | null; combinationHistory: Combination[];
  legacyRounds: (Summary & { scene: string })[];
}

const heading = (level: number, text: string) => '#'.repeat(level) + ' ' + text;
const combinationName = (scenes: Record<string, number>) => Object.keys(scenes).sort().map(scene => `${scene}第${scenes[scene]}轮`).join('、');

function ordinaryMarkdown(text: string, level: number): string {
  const marker = /^(?:(\d{2})[.:](\d{2})[.:](\d)秒[，,]\s*)?(SH\d+)\s*[：:][ \t]*/gm;
  const matches = [...text.matchAll(marker)];
  if (!matches.length) return text.trim();
  const prefix = text.slice(0, matches[0].index).trim();
  const blocks = matches.map((match, index) => ({
    shot: match[4], time: match[1] ? `${match[1]}:${match[2]}.${match[3]}` : '',
    body: text.slice(match.index! + match[0].length, matches[index + 1]?.index ?? text.length).trim(),
  })).filter(item => item.body).sort((a, b) => Number(a.shot.slice(2)) - Number(b.shot.slice(2)) || a.time.localeCompare(b.time));
  return [prefix, ...blocks.map(item => `${heading(level, item.shot + (item.time ? '｜' + item.time : ''))}\n\n${item.body}`)].filter(Boolean).join('\n\n');
}

function scenesMarkdown(notes: MarkdownNote[], level: number, historical = false, legacy = false): string {
  return [...new Set(notes.map(note => note.scene))].sort().map(scene => {
    const segments = notes.filter(note => note.scene === scene).sort((a, b) => a.segment.localeCompare(b.segment)
      || (a.roundNumber ?? 0) - (b.roundNumber ?? 0) || a.stage.localeCompare(b.stage) || a.run.localeCompare(b.run));
    const blocks = segments.map(note => {
      const edits = (note.dialogueEdits ?? []).filter(edit => edit.replacement.trim()).sort((a, b) => a.shot.localeCompare(b.shot) || a.index - b.index);
      const dialogue = edits.map(edit => {
        const repeated = edits.filter(other => other.shot === edit.shot && other.speaker === edit.speaker).length > 1;
        const label = `${edit.shot.match(/SH\d+$/)?.[0] || edit.shot}｜${edit.speaker || '未标注说话人'}${repeated || edit.index > 0 ? `｜第${edit.index + 1}句` : ''}`;
        return `${heading(level + 3, label)}\n\n**原台词**：${edit.original}\n\n**修改为**：${edit.replacement}`;
      }).join('\n\n');
      const ordinary = ordinaryMarkdown(note.text, level + 3);
      const categories = [dialogue && `${heading(level + 2, '台词修改')}\n\n${dialogue}`,
        ordinary && `${heading(level + 2, '普通修改意见')}\n\n${ordinary}`].filter(Boolean);
      if (!categories.length) return '';
      const provenance = historical ? `（${legacy ? (note.roundNumber ? `场次第${note.roundNumber}轮 · ` : '未标注轮次 · ') : ''}${note.stage} · ${note.run}）` : '';
      return `${heading(level + 1, '分段 ' + note.segment + provenance)}\n\n${categories.join('\n\n')}`;
    }).filter(Boolean);
    return blocks.length ? `${heading(level, '场次 ' + scene)}\n\n${blocks.join('\n\n')}` : '';
  }).filter(Boolean).join('\n\n');
}

export function revisionNotesMarkdown(review: MarkdownReview): string {
  const label = review.history ? '全部历史修改意见' : review.number ? `第${review.number}轮修改意见` : '当前组合修改意见';
  const header = [`# ${review.episode}｜${label}`, `- 项目：${review.project}${review.episodeTitle ? '\n- 本集：' + review.episodeTitle : ''}`];
  if (!review.history) {
    if (review.combination) header.push(`- 场次组合：${combinationName(review.combination.scenes)}`);
    const body = scenesMarkdown(review.notes, 2);
    const summary = review.combination?.text || review.rounds.find(item => item.number === review.number)?.text || '';
    return [...header, body, summary.trim() && `## 本轮汇总意见\n\n${summary}`].filter(Boolean).join('\n\n');
  }
  const recorded = review.notes.filter(note => note.editable !== false && note.roundNumber != null);
  const numbers = [...new Set([...recorded.map(note => note.roundNumber!), ...review.rounds.map(item => item.number)])].sort((a, b) => a - b);
  const rounds = numbers.map(number => {
    const body = scenesMarkdown(recorded.filter(note => note.roundNumber === number), 3, true);
    const summary = review.rounds.find(item => item.number === number)?.text || '';
    return body || summary.trim() ? `## 第${number}轮\n\n${[body, summary.trim() && `### 本轮汇总意见\n\n${summary}`].filter(Boolean).join('\n\n')}` : '';
  });
  const legacy = scenesMarkdown(review.notes.filter(note => note.editable === false || note.roundNumber == null), 3, true, true);
  const legacySummaries = review.legacyRounds.filter(item => item.text.trim()).map(item => `### 场次 ${item.scene} · 第${item.number}轮汇总意见\n\n${item.text}`);
  const combinations = [review.combination, ...review.combinationHistory].filter((item): item is Combination => !!item?.text.trim())
    .map(item => `## 组合汇总意见（${combinationName(item.scenes)}）\n\n${item.text}`);
  return [...header, ...rounds, (legacy || legacySummaries.length) && `## 场次历史意见\n\n${[legacy, ...legacySummaries].filter(Boolean).join('\n\n')}`, ...combinations].filter(Boolean).join('\n\n');
}
