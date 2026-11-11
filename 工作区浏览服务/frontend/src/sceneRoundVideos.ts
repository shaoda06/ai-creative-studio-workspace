import type { FileItem, SceneRound } from './api';

export function carriedRoundSegments(rounds: SceneRound[], current?: SceneRound) {
  if (!current) return [];
  return current.segments.filter(entry => entry.carried ?? rounds.some(round =>
    round.number < current.number && round.segments.some(previous =>
      previous.id === entry.id && previous.stage === entry.stage && previous.run === entry.run && previous.key === entry.key)));
}

export function newVideoSegmentsForRound(segments: NonNullable<FileItem['segments']>[string], rounds: SceneRound[], selectedRound?: number) {
  const current = rounds.find(round => round.number === selectedRound);
  if (current?.songssx) {
    const video = current.songssx.video;
    const isNew = video?.url && !rounds.some(round => round.number < current.number && round.songssx?.video?.key === video.key);
    return new Set(isNew ? current.songssx.segments.map(segment => segment.id) : []);
  }
  const carried = new Set(carriedRoundSegments(rounds, current).map(item => item.id));
  return new Set((current?.segments || []).filter(entry =>
    !carried.has(entry.id) && segments.find(segment => segment.id === entry.id)?.videos.some(video =>
      video.stage === entry.stage && video.run === entry.run && (!entry.key || video.key === entry.key) && video.url)
  ).map(entry => entry.id));
}
