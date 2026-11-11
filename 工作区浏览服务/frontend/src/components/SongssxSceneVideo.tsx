import { useRef, useState } from 'react';
import type { FileItem, SceneRound } from '../api';
import { Rich } from '../components';
import { SegmentLayout } from './SegmentLayout';
import { SegmentStageStrip } from './SegmentStageStrip';
import { SegmentVideo, type RepeatPlaybackControl, type SegmentVideoHandle } from './SegmentVideo';

const retainStream = () => () => {};

export function SongssxSceneVideo({ round, planned, wide, onToggleWide, repeatControl, newVideoSegments }: {
  round?: SceneRound; planned: NonNullable<FileItem['segments']>[string]; wide: boolean;
  onToggleWide: () => void; repeatControl: RepeatPlaybackControl; newVideoSegments: Set<string>;
}) {
  const segments = round ? round.segments.map(segment => ({ ...segment, videos: [] })) : planned.filter(segment => !segment.historical);
  const timings = round?.songssx?.segments || [];
  const video = round?.songssx?.video;
  const [selection, setSelection] = useState('');
  const player = useRef<SegmentVideoHandle>(null);
  const segment = segments.find(item => item.id === selection) || segments[0];
  const timing = timings.find(item => item.id === segment?.id);
  const choose = (id: string) => {
    setSelection(id);
    const start = timings.find(item => item.id === id)?.start;
    if (start !== undefined) player.current?.seekTo(start, true);
  };
  const navigation = segments.length > 0 && <SegmentStageStrip segments={segments} selected={segment.id}
    newVideoSegments={newVideoSegments}
    onSelect={choose} vertical={wide} showStages={false}
    previousEnding={null} previousSelected={false} onPreviousSelect={() => {}} />;

  return <>
    {!wide && navigation}
    <SegmentLayout wide={wide && !!navigation} navigation={navigation}
      player={<SegmentVideo key={`${video?.key || ''}/${Boolean(video?.url)}`} current={video} playerRef={player}
        wide={wide} onToggleWide={onToggleWide} repeatControl={repeatControl} continuousControl={null}
        retainSource={retainStream} onTimeChange={time => {
          const active = timings.find(item => time >= item.start && time < item.end);
          if (active) setSelection(active.id);
        }} />}>
      {segment && <section className="segment-script" aria-label="分段分镜脚本">
        <div className="segment-script-header">
          <h3>{segment.id} 分镜脚本</h3>
          {timing && <span className="muted">GEN {timing.gen} · {Number(timing.start.toFixed(3))}–{Number(timing.end.toFixed(3))} 秒</span>}
        </div>
        <div className="segment-script-content">
          {segment.scriptHtml ? <Rich html={segment.scriptHtml} /> : <div className="script-placeholder">尚未登记本段分镜。</div>}
        </div>
      </section>}
    </SegmentLayout>
  </>;
}
