import { useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { FileItem, SceneRound } from '../api';
import type { NoteScope } from './RevisionNotes';
import { SegmentWorkspace } from './SegmentWorkspace';
import { SegmentStageStrip } from './SegmentStageStrip';
import type { RepeatPlaybackControl, SegmentVideoHandle } from './SegmentVideo';

const noop = () => {};
const retainStream = () => noop;

export function SongssxSceneVideo({ round, planned, wide, onToggleWide, repeatControl, newVideoSegments, scope, tab, onTabChange, revision, notesExportControl }: {
  round?: SceneRound; planned: NonNullable<FileItem['segments']>[string]; wide: boolean;
  onToggleWide: () => void; repeatControl: RepeatPlaybackControl; newVideoSegments: Set<string>;
  scope: NoteScope; tab: string; onTabChange: (tab: string) => void; revision: number; notesExportControl: ReactNode;
}) {
  const segments = round ? round.segments.map(segment => ({ ...segment, videos: [] })) : planned.filter(segment => !segment.historical);
  const timings = round?.songssx?.segments || [];
  const video = round?.songssx?.video;
  const [selection, setSelection] = useState('');
  const player = useRef<SegmentVideoHandle>(null);
  const segment = segments.find(item => item.id === selection) || segments[0];
  const timing = timings.find(item => item.id === segment?.id);
  const selectedVideo = video && { ...video, context: timing?.context };
  const choose = (id: string) => {
    setSelection(id);
    const start = timings.find(item => item.id === id)?.start;
    if (start !== undefined) player.current?.seekTo(start, true);
  };
  if (!segment) return <p className="muted">暂无可显示的分段。</p>;
  const navigation = <SegmentStageStrip segments={segments} selected={segment.id}
    newVideoSegments={newVideoSegments}
    onSelect={choose} vertical={wide} showStages={false}
    previousEnding={null} previousSelected={false} onPreviousSelect={noop} />;

  return <>
    {!wide && navigation}
    <SegmentWorkspace scope={scope} segment={segment.id} roundNumber={round?.number} revision={revision}
      tab={tab} onTabChange={onTabChange} readOnly={scope.readOnly}
      items={selectedVideo ? [selectedVideo] : []} selection={{ stage: video?.stage || '', key: video?.key || '' }} onSelectionChange={noop}
      plannedScript={{ html: segment.scriptHtml, url: segment.scriptUrl, label: round ? `第${round.number}轮保存的分镜` : '当前分段计划' }}
      wideVideo={wide} onToggleWide={onToggleWide} repeatControl={repeatControl} segmentNavigation={navigation}
      autoPlay={false} continuousControl={null} cachedSources={{}} retainSource={retainStream} onVideoEnded={noop} onVideoError={noop}
      notesExportControl={notesExportControl}
      scenePlayback={{ player, start: timing?.start ?? 0,
        label: timing && `GEN ${timing.gen} · ${Number(timing.start.toFixed(3))}–${Number(timing.end.toFixed(3))} 秒`,
        onTimeChange: time => {
          const active = timings.find(item => time >= item.start && time < item.end);
          if (active) setSelection(active.id);
        },
      }} />
  </>;
}
