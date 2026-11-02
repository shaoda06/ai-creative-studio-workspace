import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get, type FileItem } from '../api';
import { Result } from '../components';
import { SegmentWorkspace } from './SegmentWorkspace';
import { SegmentStageStrip } from './SegmentStageStrip';
import { TabSelect } from './TabSelect';
import { latestVideo, selectedRevision } from './SegmentVideo';
import { useSceneVideoCache } from './useSceneVideoCache';
import { useRevisionNotesExport } from './RevisionNotes';
import { useRefreshState } from '../refreshPosition';
import { MessagePanel } from './MessagePanel';

type Segments = NonNullable<FileItem['segments']>[string];
type Batch = { id: string; name: string; url: string; readOnly?: boolean; segments: { id: string; stage: string; key: string }[] };
type Production = { segments: Segments; batches: Batch[]; issues: string[] };

export function ProjectProduction({ project, baseUrl }: { project: string; baseUrl: string }) {
  const query = useQuery({ queryKey: ['production', baseUrl], queryFn: () => get<Production>(baseUrl + '/production'), refetchInterval: 5000 });
  const [requested, setBatch] = useRefreshState(baseUrl + '/production/batch', '');
  const batch = query.data?.batches.find(item => item.id === requested) || query.data?.batches.at(-1);
  return <>
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && <>
      <MessagePanel label="制作记录说明" messages={query.data.issues.map(issue => ({ id: issue, content: issue }))} />
      {batch ? <>
        <TabSelect label="生产批次" selected={batch.id} onChange={setBatch} items={query.data.batches.map(item => ({ value: item.id, label: item.name }))} />
        <BatchProduction key={baseUrl} project={project} baseUrl={baseUrl} batch={batch} allSegments={query.data.segments} />
      </> : <p className="muted">尚无已提交的生产批次。制作资料仍可在下方查看。</p>}
    </>}
  </>;
}

function BatchProduction({ project, baseUrl, batch, allSegments }: { project: string; baseUrl: string; batch: Batch; allSegments: Segments }) {
  const segments = [...new Set(batch.segments.map(entry => entry.id))].map(id => allSegments.find(item => item.id === id)!);
  const [requested, setSegment] = useState(segments[0].id);
  const segment = segments.find(item => item.id === requested) || segments[0];
  const [selections, setSelections] = useState<Record<string, { stage: string; key: string }>>({});
  const fixed = batch.segments.find(item => item.id === segment.id)!;
  const selectionKey = batch.id + '/' + segment.id;
  const selection = selections[selectionKey] || { stage: fixed.stage, key: fixed.key };
  const current = selectedRevision(segment.videos, selection);
  const [tab, setTab] = useRefreshState(baseUrl + '/production/tab', 'script');
  const [wide, setWide] = useRefreshState(baseUrl + '/production/wide', false);
  const [repeat, setRepeat] = useRefreshState(baseUrl + '/production/repeat', false);
  const cache = useSceneVideoCache(current?.url ? [current] : [], current?.url ? [current.url] : []);
  const scope = { project, episode: '', scene: '', label: '视频制作', notesUrl: baseUrl + '/production-notes' };
  const notes = useRevisionNotesExport(batch.readOnly ? null : scope, segments, { stage: '混合阶段', label: batch.name,
    versions: Object.fromEntries(batch.segments.map(entry => [entry.id, allSegments.find(item => item.id === entry.id)!.videos.find(video => video.key === entry.key) || null])) });
  const navigation = <SegmentStageStrip segments={segments} selected={segment.id} onSelect={setSegment} vertical={wide}
    newVideoSegments={new Set()} previousEnding={null} previousSelected={false} onPreviousSelect={() => {}} />;
  return <>
    {!wide && navigation}
    <SegmentWorkspace scope={scope} segment={segment.id} revision={0} items={segment.videos} selection={selection}
      onSelectionChange={value => {
        const latest = value.key ? undefined : latestVideo(segment.videos.filter(video => video.stage === value.stage));
        setSelections(previous => ({ ...previous, [selectionKey]: latest ? { stage: latest.stage, key: latest.key } : value }));
      }} tab={batch.readOnly && tab === 'notes' ? 'script' : tab} onTabChange={setTab} wideVideo={wide} onToggleWide={() => setWide(value => !value)} readOnly={batch.readOnly}
      repeatControl={{ checked: repeat, onChange: setRepeat }} notesExportControl={notes.control} segmentNavigation={navigation}
      autoPlay={false} onVideoEnded={() => {}} onVideoError={() => {}} continuousControl={null}
      cachedSources={cache.sources} retainSource={cache.retainSource} />
    {notes.dialog}
  </>;
}
