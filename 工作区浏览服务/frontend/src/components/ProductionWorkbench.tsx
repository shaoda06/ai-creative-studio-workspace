import { newVideoSegmentsForRound } from '../sceneRoundVideos';
import { PointerTooltip } from './PointerTooltip';
import { useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import type { FileItem } from '../api';
import { Dialog, FileActions, PreviewContext, Result, Rich } from '../components';
import { TabNav } from './TabNav';
import { Pagination } from './Pagination';
import { ProductionEpisodeButton } from './ProductionEpisodeButton';
import { SceneWorkspace, type EpisodePlayback } from './SceneWorkspace';
import { useRefreshState } from '../refreshPosition';
import { BreadcrumbActionsContext, BreadcrumbSelectorContext } from './Breadcrumbs';
import { TabSelect } from './TabSelect';
import { get } from '../api';
import { useProductionAccess } from './ProductionAccess';
import { DownloadButton } from './DownloadButton';
import { previousEpisodeEnding } from '../previousEpisodeEnding';
import type { EpisodeReview } from '../episodeRevisionNotes';
import { workSceneLabel } from '../episodeRevisionNotes';
import { useRevisionNotesExport } from './RevisionNotes';
import { formatProductionDuration, sceneDurationEntries, useEpisodeDurations } from './useEpisodeDurations';
import { FloatingMessage } from './Notifications';
import { workPackageLabel, type Downloads } from './SceneDownloads';
import './SceneDownloads.css';
import './EpisodeProduction.css';

export function ProductionWorkbench({ project, items, statistics, selected, onSelect, revision, detailControls, inlineListHeading = false }: { project: string; items: FileItem[]; statistics: { total: number; completed: number; notStarted: number; running: number }; selected: string | null; onSelect: (episode: string | null) => void; revision: number; detailControls?: ReactNode; inlineListHeading?: boolean }) {
  const access = useProductionAccess();
  const workMode = access.unitKind === 'work';
  const namespace = access.namespace(project);
  const unitLabel = workMode ? "本片" : "本集";
  const preview = useContext(PreviewContext);
  const breadcrumbActions = useContext(BreadcrumbActionsContext);
  const breadcrumbSelector = useContext(BreadcrumbSelectorContext);
  const [scene, setScene] = useRefreshState(`project/${namespace}/production/scene`, '');
  const [sceneView, setSceneView] = useRefreshState(`project/${namespace}/production/${selected || ''}/scene-view`, 'segments');
  const [segmentTab, setSegmentTab] = useRefreshState(`project/${namespace}/production/${selected || ''}/segment-tab`, 'script');
  const [wideVideo, setWideVideo] = useRefreshState(`project/${namespace}/production/${selected || ''}/wide-video`, false);
  const [repeatVideo, setRepeatVideo] = useRefreshState(`project/${namespace}/production/${selected || ''}/repeat-video`, false);
  const [integrateSheets, setIntegrateSheets] = useRefreshState(`project/${namespace}/production/${selected || ''}/integrate-sheets`, false);
  const [page, setPage] = useState(1);
  const [handoffKey, setHandoffKey] = useState('');
  const [roundEntry, setRoundEntry] = useState(0);
  const [recordNumber, setRecordNumber] = useState<number | null>(null);
  const [playback, setPlayback] = useState<{ episode: string; rounds: Record<string, number | undefined>; start?: EpisodePlayback['start'] } | null>(null);
  const cards = useRef<HTMLDivElement>(null);
  const previousEpisode = useRef(selected);
  useEffect(() => {
    if (!selected && previousEpisode.current) cards.current!.querySelector<HTMLButtonElement>(`[data-episode="${previousEpisode.current}"]`)?.focus();
    previousEpisode.current = selected;
  }, [selected]);
  const selectedItem = items.find(item => item.name === selected);
  const shared = items.filter(item => item.name === '片头' || item.name === '片尾');
  const episodes = items.filter(item => item.name !== '片头' && item.name !== '片尾');
  const workCounts = new Map<string, number>();
  if (workMode) for (const item of episodes) {
    const label = item.workStatusLabel || '未登记制作状态';
    workCounts.set(label, (workCounts.get(label) || 0) + 1);
  }
  const sharedSelected = selected === '片头' || selected === '片尾';
  const contentLabel = sharedSelected ? `${selected}内容稿` : workMode ? '制作脚本' : '本集剧本';
  const detail = useQuery({ queryKey: ['episode', namespace, selected, revision],
    queryFn: () => get<FileItem>(access.detail(project, selected!)), enabled: !!selectedItem, refetchInterval: workMode ? 5000 : false,
    placeholderData: (previous, query) => query?.queryKey[2] === selected ? previous : undefined });
  const current = selectedItem && detail.data?.name === selected ? detail.data : undefined;
  useEffect(() => {
    if (selected && !selectedItem) onSelect(null);
  }, [selected, selectedItem, onSelect]);
  const [roundNumbers, setRoundNumbers] = useRefreshState<Record<string, number | null>>(`project/${namespace}/production/rounds`, {});
  const episodeRounds = current?.episodeRounds || [];
  const episodeChoice = current ? roundNumbers[current.name] === undefined ? episodeRounds.at(-1)?.number : roundNumbers[current.name] : undefined;
  const episodeRound = episodeRounds.find(item => item.number === episodeChoice);
  const scenes = episodeRound?.scenes || (episodeChoice === null
    ? (current?.scenes || []).filter(id => current?.sceneRounds?.[id]?.some(item => !item.episodeRound)) : current?.scenes || []);
  const selectedScene = scenes.includes(scene) ? scene : scenes[0] || '';
  const roundNumberForScene = (id: string) => {
    if (episodeRound) return episodeRound.number;
    const rounds = (current?.sceneRounds?.[id] || []).filter(item => episodeChoice !== null || !item.episodeRound);
    return rounds.find(item => item.number === roundNumbers[current!.name + '/' + id])?.number ?? rounds.at(-1)?.number;
  };
  const durations = useEpisodeDurations(Object.fromEntries(scenes.map(id => [id, sceneDurationEntries(current!, id, roundNumberForScene(id))])));
  const episodeReview: EpisodeReview | undefined = current ? {
    number: episodeRound?.number, rounds: episodeRounds.map(item => item.number),
    scenes: (workMode ? [...new Set([...scenes, ...(current.scenes || [])])] : scenes).map(id => {
      const number = roundNumberForScene(id);
      const round = current.sceneRounds?.[id]?.find(item => item.number === number);
      return { id, number, segments: current.segments?.[id] || [], versions: round?.segments || [],
        history: workMode ? current.sceneRounds?.[id] : undefined };
    }),
  } : undefined;
  const episodeNotesExport = useRevisionNotesExport(current && selectedScene && (current.readOnly || current.segments?.[selectedScene]?.length)
    ? { ...access.scope(project, current.name, selectedScene), episodeTitle: current.title } : null, [], null, undefined, episodeReview);
  const workSheets = workMode && !scenes.includes('whole') ? current?.directorSheets?.whole : undefined;
  const directorScenes = (workSheets ? [selectedScene] : scenes).map(id => {
    const rounds = current?.sceneRounds?.[id] || [];
    const selectedRound = episodeRound?.number ?? (id === selectedScene ? roundNumberForScene(id)
      : rounds.filter(item => episodeChoice !== null || !item.episodeRound).at(-1)?.number);
    const round = rounds.find(item => item.number === selectedRound);
    return { id, sheets: current?.directorSheets?.[id] || workSheets,
      storyboardVersion: round ? round.storyboard?.version || '' : current?.storyboards?.[id]?.version || '' };
  });
  const segments = current?.segments?.[selectedScene] || [];
  const sceneRounds = current?.sceneRounds?.[selectedScene] || [];
  const selectableRounds = [...new Map([...episodeRounds, ...sceneRounds.filter(item => !item.episodeRound)]
    .map(item => [item.number, item])).values()].sort((a, b) => b.number - a.number);
  const selectedRound = roundNumberForScene(selectedScene);
  const round = sceneRounds.find(item => item.number === selectedRound);
  const currentStoryboard = current?.storyboards?.[selectedScene];
  const recordScenes = episodeRounds.find(item => item.number === recordNumber)?.scenes || [selectedScene];
  const recordRounds = recordScenes.flatMap(id => (current?.sceneRounds?.[id] || [])
    .filter(item => item.number === recordNumber).map(item => ({ id, item })));
  const recordedOutputs = recordRounds[0]?.item.reviewOutputs || [];
  const recordOptions = selectableRounds.map(item => ({ value: String(item.number), label: `第${item.number}轮` }));
  const openRecordFile = (item: FileItem) => { setRecordNumber(null); preview(item); };
  const downloads = useQuery({
    queryKey: ['episode-downloads', namespace, current?.name, selectedScene, revision],
    queryFn: () => get<Downloads>(access.downloads(project, current!.name, selectedScene)),
    enabled: workMode && !!current && !!selectedScene,
  });
  const handoffs = downloads.data?.workPackages?.filter(item => item.archived || item.rounds.includes(selectedRound!)) || [];
  const handoff = handoffs.find(item => item.key === handoffKey) || handoffs[0];
  const productionTask = workMode ? current?.productionTask : undefined;
  const roundHistory = workMode ? current?.roundHistory : undefined;
  const currentFiles = [
    [contentLabel, current?.script], ['现行分镜', currentStoryboard], ['生成说明', current?.generationPlan],
    ['生产任务', productionTask], ['历史索引原件', roundHistory],
  ] as const;
  const continuous = !!playback && playback.episode === current?.name;
  const nextScene = scenes[scenes.indexOf(selectedScene) + 1];
  const nextRoundNumber = continuous ? playback!.rounds[nextScene] : undefined;
  const nextRound = current?.sceneRounds?.[nextScene]?.find(item => item.number === nextRoundNumber);
  const nextEntry = nextRound?.segments[0];
  const nextVideo = nextEntry && current?.segments?.[nextScene]?.find(item => item.id === nextEntry.id)?.videos
    .find(video => video.stage === nextEntry.stage && video.run === nextEntry.run && (!nextEntry.key || video.key === nextEntry.key));
  const episodePlayback: EpisodePlayback = {
    continuous,
    start: continuous ? playback!.start : undefined,
    next: nextScene ? { scene: nextScene, round: nextRoundNumber, segment: nextEntry?.id, video: nextVideo } : undefined,
    onChange: checked => setPlayback(checked ? { episode: current!.name, rounds: Object.fromEntries(scenes.map(id =>
      [id, roundNumberForScene(id)])) } : null),
    onNext: () => {
      setRoundNumbers(previous => ({ ...previous, [current!.name + '/' + nextScene]: nextRoundNumber! }));
      setPlayback(previous => ({ ...previous!, start: { segment: nextEntry!.id, selection: { stage: nextVideo!.stage, key: nextVideo!.key } } }));
      setScene(nextScene);
    },
  };

  useEffect(() => {
    if (current && episodeRounds.length && roundNumbers[current.name] === undefined)
      setRoundNumbers(previous => ({ ...previous, [current.name]: episodeRounds.at(-1)!.number }));
    const key = (current?.name || '') + '/' + selectedScene;
    const fallback = episodeChoice === null ? sceneRounds.filter(item => !item.episodeRound).at(-1) : sceneRounds.at(-1);
    if (current && selectedScene && fallback && roundNumbers[key] === undefined)
      setRoundNumbers(previous => ({ ...previous, [key]: fallback.number }));
  }, [current?.name, selectedScene, sceneRounds, episodeRounds, roundNumbers, setRoundNumbers]);
  const selectRound = (number: number) => {
    setPlayback(null);
    setRoundNumbers(previous => ({ ...previous, [current!.name + '/' + selectedScene]: number,
      ...(episodeRounds.length ? { [current!.name]: episodeRounds.some(item => item.number === number) ? number : null } : {}) }));
  };
  const openRound = (number: number) => {
    setRoundEntry(previous => previous + 1);
    selectRound(number);
  };
  const issues = (current?.productionIssues || []).filter(issue => !issue.scene || issue.scene === selectedScene);
  const episodeComplete = current?.productionComplete && !current.productionIssues?.length && scenes.length > 0 && scenes.every(id => {
    const sceneSegments = current.segments?.[id] || [];
    return sceneSegments.length > 0 && sceneSegments.every(item =>
      item.videos.filter(video => video.stage === '后处理' && video.approved).length === 1);
  });
  const segmentCount = scenes.reduce((count, id) => count + (current?.segments?.[id]?.length || 0), 0);
  const emptyMessage = issues.length > 0 ? '请先修正上方提示的资料。'
    : !current?.script ? `尚未登记${contentLabel}。` : '尚未登记分段计划。';
  let directorFiles = current?.children;
  for (const folder of ['06-阶段采用视频', '01-一采', selectedScene + '-场次', '导演包']) {
    directorFiles = directorFiles?.find(item => item.name === folder)?.children;
  }
  const open = (name: string) => {
    setPlayback(null);
    setScene('');
    onSelect(name);
  };
  const renderActions = () => <div className="episode-heading-actions">
      <PointerTooltip text={sharedSelected ? "按当前轮次的选中场次统计；* 表示含计划时长" : "按当前轮次统计；* 表示含计划时长"}><span className="muted" aria-label={`${unitLabel}时长`}>{sharedSelected ? current!.name : unitLabel}时长：{formatProductionDuration(sharedSelected ? durations.scenes[selectedScene] : durations.total)}</span></PointerTooltip>
      {workMode && handoff && <div className="episode-heading-actions" role="group" aria-label="整片交接下载">
        {handoffs.length > 1 ? <TabSelect label="选择交接版本" selected={handoff.key} onChange={setHandoffKey}
          items={handoffs.map(item => ({ value: item.key, label: workPackageLabel(item) }))} />
          : <span className="muted">{workPackageLabel(handoff)}{handoff.count ? `（${handoff.count}段）` : ''}</span>}
        {handoff.jypack && <DownloadButton key={handoff.jypack} url={handoff.jypack} pack={!handoff.archived}
          label={handoff.archived ? '下载归档剪映包' : '剪映草稿包'} title={[handoff.version, handoff.purpose].filter(Boolean).join(' · ')} />}
        {handoff.zip && <DownloadButton key={handoff.zip} url={handoff.zip} pack
          label="本片 ZIP 下载" title={`按交接清单打包本轮 ${handoff.count} 段视频`} />}
      </div>}
      {!workMode && episodeComplete && <><DownloadButton key={current!.name + '/draft'} pack
      url={access.package(project, current!.name) + '?format=jypack'} label="剪映草稿包"
      title="下载全部后处理已采用视频的剪映草稿包；双击或拖入剪映导入，需对应会员权限" />
      <DownloadButton key={current!.name} pack
      url={access.package(project, current!.name)} label={`${sharedSelected ? current!.name : unitLabel}打包下载`}
      title={`下载${current!.name}全部${scenes.length}个场次、${segmentCount}段后处理已采用视频 ZIP 包`} /></>}
    </div>;
  return <>
    {breadcrumbSelector && selectedItem && createPortal(<TabSelect iconOnly label="快速选择制作对象" selected={selected!} onChange={open}
      items={items.map(item => ({ value: item.name, label: `${item.name} · ${item.title || (item.name === '片头' || item.name === '片尾' ? '全剧通用' : '题名未记录')}${item.titleStatus ? `（${item.titleStatus}）` : ''}` }))} />, breadcrumbSelector)}
    {selectedItem && !current ? <Result page loading={detail.isPending} error={detail.error} retry={detail.refetch} retrying={detail.isFetching} /> : current ? <div className="episode-detail">
    {breadcrumbActions && createPortal(renderActions(), breadcrumbActions)}
    {detailControls}
    {workMode && downloads.error && <FloatingMessage tone="error">交接清单读取失败：{downloads.error.message}。<button className="link" onClick={() => void downloads.refetch()}>重新读取</button></FloatingMessage>}
    {durations.failed > 0 && <FloatingMessage key={current.name + '/' + selectedRound} tone="error">{durations.failed}段视频时长读取失败，暂用计划时长（*）。<button className="link" onClick={durations.retry}>重新读取</button></FloatingMessage>}
    <div className="episode-scene-header">
      {scenes.length > 0 && <TabNav label={workMode ? '本片场次' : '本集场次'} items={scenes.map(id => ({ value: id, label: `${workMode ? workSceneLabel(id) : '场次 ' + id} · ${formatProductionDuration(durations.scenes[id])}`, marker: newVideoSegmentsForRound(current.segments?.[id] || [], current.sceneRounds?.[id] || [], roundNumberForScene(id)).size ? '本轮新生成视频' : undefined }))} selected={selectedScene} onChange={value => { setPlayback(previous => previous ? { ...previous, start: undefined } : null); setScene(value); }} />}
      <div className="episode-scene-actions">
      <div className="scene-round-selector">
        {selectableRounds.length > 0 && <span className="production-latest">当前最新{selectedRound !== selectableRounds[0].number && <>：第{selectableRounds[0].number}轮，<button className="production-latest-link" aria-label="切换到最新修改轮次" onClick={() => openRound(selectableRounds[0].number)}>点击切换</button></>}</span>}
        <TabSelect size="toolbar" highlightSelected label="修改轮次" selected={String(selectedRound ?? '')}
          onChange={value => openRound(Number(value))} items={recordOptions.length ? recordOptions : [{ value: '', label: '暂无轮次', disabled: true }]} />
      </div>
      <button className="link episode-script-link" onClick={() => setRecordNumber(selectedRound ?? 0)}>轮次记录</button>
      </div>
    </div>
    {recordNumber !== null && <Dialog title="轮次记录" close={() => setRecordNumber(null)}>
      {recordOptions.length > 0 ? <TabSelect size="toolbar" label="查阅轮次" selected={String(recordNumber)} items={recordOptions} onChange={value => setRecordNumber(Number(value))} />
        : <p className="muted">尚未登记轮次。</p>}
      {recordRounds[0]?.item.note && <p>{recordRounds[0].item.note}</p>}
      {recordedOutputs.length > 0 && <section><h3>本轮审阅产出</h3><ul>{recordedOutputs.map((file, index) =>
        <li key={file.key || index}>{file.url ? <button className="link" onClick={() => openRecordFile(file)}>{file.name}</button> : `${file.name}（文件不可用）`}</li>)}</ul></section>}
      {recordRounds.map(({ id, item }) => {
        const candidates = current.segments?.[id] || [];
        const generated = newVideoSegmentsForRound(candidates, current.sceneRounds![id], item.number);
        return <section key={id}>
          <h3>{id === 'whole' ? '整片' : `场次 ${id}`}</h3>
          <ul>
            {([[contentLabel, item.script], ['分镜', item.storyboard], ['制作记录', item.record]] as const).map(([label, file]) =>
              file && <li key={label}><button className="link" onClick={() => openRecordFile(file)}>{label}{file.version ? ` ${file.version}` : ''}</button></li>)}
            {item.segments.filter(entry => generated.has(entry.id)).map(entry => {
              const video = candidates.find(candidate => candidate.id === entry.id)?.videos.find(video =>
                video.url && video.stage === entry.stage && video.run === entry.run && (!entry.key || video.key === entry.key));
              const label = `${entry.id} · ${entry.stage} · ${entry.run}`;
              return video && <li key={entry.id}><button className="link" onClick={() => openRecordFile({ ...video, kind: 'video', name: label })}>{label}</button> <FileActions url={video.downloadUrl || video.url} downloadOnly /></li>;
            })}
          </ul>
        </section>;
      })}
      {currentFiles.some(([, file]) => file) && <section>
        <h3>现行资料与历史索引</h3>
        <ul>{currentFiles.map(([label, file]) =>
          file && <li key={label}><button className="link" onClick={() => openRecordFile(file)}>{label}</button></li>)}</ul>
      </section>}
    </Dialog>}
    {issues.length > 0 ? <div className="notice episode-data-issues" role="alert">
      <strong>制作资料需要修正</strong>
      <ul>{issues.map((issue, index) => <li key={index}>
        <PointerTooltip text={issue.key}><button className="link"  onClick={() => preview({ kind: 'document', key: issue.key, name: issue.key.split('/').pop()! })}>{issue.key.split('/').pop()}</button></PointerTooltip>：{issue.message}
      </li>)}</ul>
    </div> : null}
    <SceneWorkspace wideVideo={wideVideo} onToggleWide={() => setWideVideo(value => !value)} repeatControl={{ checked: repeatVideo, onChange: setRepeatVideo }} segmentTab={segmentTab} onSegmentTabChange={setSegmentTab} episodeNotesExportControl={episodeNotesExport.control} episodePlayback={episodePlayback} view={sceneView} onViewChange={setSceneView} key={current.name + '/' + selectedScene + '/' + roundEntry} scope={access.scope(project, current.name, selectedScene)} segments={segments} sceneRounds={sceneRounds} selectedRound={selectedRound} onRoundChange={selectRound} previousEnding={workMode ? null : previousEpisodeEnding(current.previousEpisode ? [current.previousEpisode] : [], current.name)} emptyMessage={emptyMessage} revision={revision} directorFiles={directorFiles || []} directorScenes={directorScenes} integrateSheets={integrateSheets} onIntegrateSheetsChange={setIntegrateSheets} storyboardVersion={round ? round.storyboard?.version || '' : current.storyboards?.[selectedScene]?.version || ''} storyboardDocument={round ? round.storyboard?.doc : current.storyboards?.[selectedScene]?.doc} storyboardSource={round ? round.storyboard || undefined : current.storyboards?.[selectedScene]} />
    {episodeNotesExport.dialog}
    {(!!current.materials?.length || current.materialRecord) && <details className="asset-candidate-type production-materials"><summary>制作素材与审阅（{current.materials?.length || 0}）</summary>
      {current.materialRecord && <p><button className="link" onClick={() => preview(current.materialRecord!)}>查看素材记录</button></p>}
      {(['pending', 'revision', 'adopted', 'unknown', 'history'] as const).map(group => {
        const images = (current.materials || []).filter(file => (file.materialGroup || 'unknown') === group)
          .sort((a, b) => b.name.replace(/\.[^.]+$/, '').localeCompare(a.name.replace(/\.[^.]+$/, ''), 'zh-CN', { numeric: true }));
        const label = { pending: '待审核', revision: '待修改', adopted: '当前采用', unknown: '状态待核对', history: '历史素材' }[group];
        return images.length || group === 'adopted' ? <details key={group} className="asset-candidate-type" data-material-group={group} open={group !== 'history'}>
          <summary>{label}（{images.length}）</summary>
          {!images.length && <p className="muted">暂无适用于当前制作的已采用专用图；项目人物、场景和道具资产仍按素材索引引用。</p>}
          <div className="asset-media-grid">{images.map(file => <article className="asset-media-card" key={file.key}>
            <h3>{file.name}</h3>
            <p><span className={`status-badge status-${group === 'adopted' ? 'green' : group === 'history' ? 'gray' : 'orange'}`}>{file.materialStatus || '状态待核对'}</span></p>
            {file.approvalHtml && <div className="asset-media-field"><span className="field-label">审核决定：</span><Rich html={file.approvalHtml} /></div>}
            <p className="asset-media-field">{file.materialNote}</p>
            <button className="production-image-preview" onClick={() => preview(file)} aria-label={`查看${file.name}`}><img loading="lazy" src={file.url} alt={file.name} /></button>
            <div className="asset-media-footer"><DownloadButton url={file.url!} label="下载原图" title={`下载${file.name}`} />
              {file.materialReview && <button className="link" onClick={() => preview(file.materialReview!)}>查看审阅记录</button>}
            </div>
          </article>)}</div>
        </details> : null;
      })}
    </details>}
  </div> : <>
    <div ref={cards}>
      {!workMode && <section aria-label="片头与片尾"><h2>片头与片尾</h2><div className="episode-grid episode-grid-pairs">{shared.map(item => <ProductionEpisodeButton key={item.key} project={project} revision={revision} item={item} onSelect={open} />)}</div>
        {!shared.length && <p className="muted">片头、片尾尚未开始制作。</p>}</section>}
      <section aria-label={workMode ? "视频制作" : "剧集制作"}>
        <div className={inlineListHeading ? 'production-list-heading' : undefined}>
          <h2>{workMode ? "作品列表" : "剧集制作"}</h2>
          <div className="production-statistics" aria-label={workMode ? "作品制作统计" : "剧集制作统计"}><span>共 <strong>{statistics.total}</strong>{workMode ? " 部" : " 集"}</span>
            {workMode ? [...workCounts].map(([label, count]) => <span key={label}>{label} <strong>{count}</strong> 部</span>)
              : <><span>未开始 <strong>{statistics.notStarted}</strong> 集</span><span>进行中 <strong>{statistics.running}</strong> 集</span><span>已完成 <strong>{statistics.completed}</strong> 集</span></>}
          </div>
        </div>
        <div className="episode-grid episode-grid-pairs">{episodes.slice((page - 1) * 36, page * 36).map(item => <ProductionEpisodeButton key={item.key} project={project} revision={revision} item={item} onSelect={open} />)}</div>
        {!episodes.length && <p className="muted">{workMode ? "尚无作品，请先建立作品资料。" : "尚无剧集制作目录。"}</p>}
        <Pagination page={page} total={episodes.length} change={setPage} />
      </section>
    </div>
  </>}</>;
}
