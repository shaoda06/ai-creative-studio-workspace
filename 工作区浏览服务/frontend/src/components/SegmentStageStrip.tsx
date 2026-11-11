import { RoundNewDot } from './RoundNewDot';
import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import type { FileItem, SegmentVideo } from '../api';
import { PointerTooltip } from './PointerTooltip';
import type { PreviousEpisodeEnding } from '../previousEpisodeEnding';
import type { ReviewVersions } from './RevisionNotes';
import { latestVideo, workVideoState } from './SegmentVideo';
import './SegmentStageStrip.css';

const stages = ['一采', '二采', '后处理'];

export function segmentStageStatus(videos: SegmentVideo[], stage: string, chosen?: ReviewVersions[string]) {
  const recorded = videos.filter(video => video.stage === stage);
  const candidate = chosen === undefined ? recorded.find(video => video.approved) || latestVideo(recorded)
    : recorded.find(video => chosen && video.key === chosen.key && video.run === chosen.run);
  const otherRuns = chosen === undefined ? [] : [...new Set(recorded.filter(video => video !== candidate).map(video => video.run))];
  const suffix = otherRuns.length ? `；其他候选：${otherRuns.join('、')}` : '';
  if (!candidate) return { state: 'not-started', symbol: '○', detail: `${stage}：${recorded.length ? '本轮未选' : '未开始'}${suffix}` };
  if (candidate.approved) return { state: 'adopted', symbol: '✓',
    detail: `${stage}：已采用（${candidate.run}）${candidate.url ? '' : ' · ' + workVideoState(candidate)}${suffix}` };
  const status = candidate.url ? (candidate.adoptionKnown === false ? '采用状态待核对' : '待审阅') : workVideoState(candidate);
  return { state: 'started', symbol: '−', detail: `${stage}：${candidate.run} · ${status}${suffix}` };
}

export function SegmentStageStrip({ segments, selected, onSelect, vertical = false, newVideoSegments, previousEnding, previousSelected, onPreviousSelect, roundVersions, showStages = true }: {
  segments: NonNullable<FileItem['segments']>[string]; newVideoSegments: Set<string>; selected: string; vertical?: boolean; onSelect: (id: string) => void;
  previousEnding: PreviousEpisodeEnding | null; previousSelected: boolean; onPreviousSelect: () => void;
  roundVersions?: ReviewVersions;
  showStages?: boolean;
}) {
  const rail = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!vertical) return;
    const active = rail.current!.querySelector<HTMLElement>('[data-selected="true"]')!;
    const scroller = rail.current!.parentElement!;
    const offset = active.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
    if (offset < 0 || offset + active.offsetHeight > scroller.clientHeight) scroller.scrollTop += offset;
  }, [selected, vertical]);
  const previousAvailable = previousEnding?.segment?.videos.some(video => video.url);
  const previousButton = previousEnding && <button className="previous-ending-button" data-selected={previousSelected}
    aria-label={`查看${previousEnding.episode}上集末段`} aria-pressed={previousSelected} disabled={!previousAvailable} onClick={onPreviousSelect}
    title={!previousAvailable ? previousEnding.segment ? '暂无可播放视频' : '暂无分段资料' : undefined}>
    <strong>上集末段</strong><span>{previousEnding.segment ? `${previousEnding.segment.duration}秒` : '—秒'}</span>
  </button>;
  const previousStatus = !vertical && previousEnding && <div className="segment-stage-cell previous-ending-status" data-selected={previousSelected} role="group" aria-label="上集末段制作进度：一采、二采、后处理">
    {stages.map(stage => {
      const status = segmentStageStatus(previousEnding.segment?.videos || [], stage);
      const label = `上集末段 ${status.detail}`;
      return <PointerTooltip key={stage} text={label}><span className={`segment-stage-icon is-${status.state}`} role="img" aria-label={label} tabIndex={0}>{status.symbol}</span></PointerTooltip>;
    })}
  </div>;
  if (vertical) return <div ref={rail} className="segment-vertical-strip" role="group" aria-label="本场分段">
    {previousEnding && <div className="segment-vertical-item is-previous-ending" data-selected={previousSelected}>{previousButton}</div>}
    {segments.map(item => <div className="segment-vertical-item" key={item.id} data-selected={item.id === selected}>
      <PointerTooltip text={`${item.id} · 计划时长 ${item.duration}秒${newVideoSegments.has(item.id) ? ' · 本轮新生成视频' : ''}`}><button aria-label={`分段 ${item.id}，计划时长 ${item.duration}秒${newVideoSegments.has(item.id) ? '，本轮新生成视频' : ''}`} aria-pressed={item.id === selected} onClick={() => onSelect(item.id)}><span>{item.label || item.id}</span><span>{item.duration}秒</span>{newVideoSegments.has(item.id) && <RoundNewDot />}</button></PointerTooltip>
    </div>)}
  </div>;
  return <div className="segment-scroll segment-progress-scroll">
    <div className={'segment-timeline' + (previousEnding ? ' has-previous-ending' : '') + (showStages ? '' : ' segment-timeline-navigation')} style={{ '--segment-columns': segments.map(item => `minmax(84px, ${item.duration}fr)`).join(' '), '--segment-count': segments.length } as CSSProperties}>
      {previousButton}
      {previousStatus}
      <div className="segment-strip" role="group" aria-label="本场分段">
        {segments.map(item => <PointerTooltip key={item.id} text={`${item.id} · 计划时长 ${item.duration}秒${newVideoSegments.has(item.id) ? ' · 本轮新生成视频' : ''}`}><button  aria-label={`分段 ${item.id}，计划时长 ${item.duration}秒${newVideoSegments.has(item.id) ? '，本轮新生成视频' : ''}`}  aria-pressed={item.id === selected} onClick={() => onSelect(item.id)}><span>{item.label || item.id}</span><span>{item.duration}秒</span>{newVideoSegments.has(item.id) && <RoundNewDot />}</button></PointerTooltip>)}
      </div>
      {showStages && <div className="segment-stage-strip" role="group" aria-label="分段制作进度：一采、二采、后处理">
        {segments.map(item => <div className="segment-stage-cell" key={item.id} data-segment={item.id} data-selected={item.id === selected}>
          {stages.map(stage => {
            const status = segmentStageStatus(item.videos, stage, roundVersions ? roundVersions[item.id] || null : undefined);
            const label = `${item.id} ${status.detail}`;
            return <PointerTooltip key={stage} text={label}><span className={`segment-stage-icon is-${status.state}`} role="img" aria-label={label} tabIndex={0}>{status.symbol}</span></PointerTooltip>;
          })}
        </div>)}
      </div>}
    </div>
  </div>;
}
