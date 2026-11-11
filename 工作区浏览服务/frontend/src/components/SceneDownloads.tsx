import { useProductionAccess } from './ProductionAccess';
import { useState } from 'react';
import { TabSelect } from './TabSelect';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { get } from '../api';
import { projectUrl, type FileItem } from '../api';
import { Result } from '../components';
import { DownloadButton } from './DownloadButton';
import './SceneDownloads.css';

type StagePackage = { name: string; count: number; url: string };
type Resource = { packages?: StagePackage[]; count: number; url: string | null; files: { name: string; url: string; label?: string; description?: string }[]; messages?: string[] };
interface WorkPackage {
  key: string; label: string; version: string; purpose: string; rounds: number[];
  count?: number; archived?: boolean; jypack: string | null; zip: string | null;
}
type DownloadGroup = Record<'videos' | 'canvas', Resource>;
export type Downloads = Record<'后处理' | '二采' | '一采', DownloadGroup>
  & { workPackages?: WorkPackage[]; round?: DownloadGroup };

export function workPackageLabel({ label, rounds }: WorkPackage) {
  return rounds.length ? `${rounds.map(number => `第${number}轮`).join('、')} · ${label}` : label;
}

export function SongssxRoundDownloads({ project, episode, round, ready, total }: {
  project: string; episode: string; round?: number; ready: number; total: number;
}) {
  const url = round && ready ? `${projectUrl(project)}/episodes/${episode}/rounds/${round}/download` : null;
  return <div className="stage-downloads" aria-label="资源下载">
    <section className="stage-download-section" aria-label="本轮资源">
      <h3>{round ? `第${round}轮` : '本轮资源'}</h3>
      {round && ready === 0 ? <p className="muted">本轮暂无可下载的视频。</p> : null}
      {ready > 0 && ready < total ? <p className="muted">本轮已取回 {ready}/{total} 场，下载包含已取回的视频。</p> : null}
      {!round && <p className="muted">请先选择制作轮次。</p>}
      <div className="stage-download-actions stage-download-packages">
        <DownloadButton url={url} label="本轮打包下载" title="按场次顺序打包本轮视频 ZIP" pack />
        <DownloadButton url={url && url + '?format=jypack'} label="剪映草稿下载" title="按本轮场次顺序生成剪映草稿" pack />
      </div>
    </section>
  </div>;
}

export function SceneDownloads({ project, episode, scene, revision, segments = [], selectedRound, roundNote }: {
  project: string; episode: string; scene: string; revision: number; selectedRound?: number; roundNote?: string; segments?: NonNullable<FileItem['segments']>[string];
}) {
  const [choices, setChoices] = useState<Record<string, string>>({});
  const access = useProductionAccess();
  const workMode = access.unitKind === 'work';
  const roundMode = access.roundDownloads === true;
  const round = roundMode ? selectedRound : undefined;
  const downloads = useQuery({ queryKey: ['episode-downloads', access.namespace(project), episode, scene, revision, ...(roundMode ? [round] : [])],
    queryFn: () => get<Downloads>(access.downloads(project, episode, scene, round)), placeholderData: keepPreviousData });
  const packageLabel = (item: StagePackage) => {
    if (!workMode) return item.name;
    const handoff = downloads.data?.workPackages?.find(pkg => pkg.zip === item.url);
    return handoff ? workPackageLabel(handoff) : `未关联整片轮次 · ${item.name}`;
  };
  const adopted = segments.flatMap(item => item.videos.filter(video => video.approved && video.url)
    .map(video => ({ id: item.id, video })));
  const archivedPackages = downloads.data?.workPackages?.filter(item => item.archived) || [];
  const hasResources = downloads.data && (!!downloads.data.round || (!roundMode && adopted.length > 0) || archivedPackages.length > 0 || Object.values(downloads.data).some(group =>
    !Array.isArray(group) && Object.values(group).some(resource => resource.url || resource.files.length || resource.messages?.length)));
  return <div className="stage-downloads" aria-label="资源下载">
    {(downloads.isFetching || downloads.isPending || downloads.error) && <Result
      loading={downloads.isFetching || downloads.isPending} error={downloads.error} retry={downloads.refetch} retrying={downloads.isFetching} />}
    <div hidden={downloads.isFetching || downloads.isPending || !!downloads.error}>
    {downloads.data && !hasResources && <div className="scene-empty" role="status"><h3>暂无可下载资源</h3></div>}
    {downloads.data && hasResources && <>
    {archivedPackages.length > 0 && <section className="stage-download-group" aria-label="归档交接包"><h4>归档交接包</h4>
      <div className="stage-download-actions">{archivedPackages.map(item => <DownloadButton key={item.key} url={item.jypack} label={item.label} title="下载已归档的剪映草稿包" />)}</div>
    </section>}
    {(roundMode
      ? downloads.data.round ? [{ label: `第${round}轮`, resources: downloads.data.round }] : []
      : (['后处理', '二采', '一采'] as const).map(stage => ({ label: stage, resources: downloads.data[stage] }))
    ).map(({ label: stage, resources }) => {
      const original = resources.videos;
      const selectedPackage = original.packages?.find(item => item.url === choices[stage]) || original.packages?.[0];
      const videos = selectedPackage || original;
      const approved = adopted.filter(item => item.video.stage === stage);
      const available = roundMode ? original.files : approved.map(({ id, video }) => ({
        name: `${id} · ${video.run}`, url: video.downloadUrl || video.url!,
      }));
      const videoLabel = roundMode ? '本轮视频' : '已采用视频';
      const videoList = <details className="stage-download-group" aria-label={stage + videoLabel}>
        <summary>{videoLabel} <small className="stage-download-count muted">{available.length} 段</small>
          {!available.length && <small className="stage-download-count muted">{roundMode ? '本轮暂无视频。' : '暂无已采用视频。'}</small>}
        </summary>
        {available.length > 0 && <div className="stage-download-actions">{available.map(file =>
          <DownloadButton key={file.url} url={file.url} label={file.name} title="下载原视频" />)}</div>}
      </details>;
      return <section className="stage-download-section" key={stage} aria-label={stage + '资源下载'}>
      <h3>{stage}{roundMode && roundNote && <small className="stage-download-note muted">{roundNote}</small>}</h3>
      {!roundMode && videoList}
      <section className="stage-download-group" aria-label={stage + '交接包'}>
        <h4>交接包 <small className="stage-download-count muted">{videos.url ? `${videos.count} 份视频` : roundMode ? '本轮暂无视频。' : workMode ? '尚未登记交接包。' : '尚无可下载的交接包。'}</small>
          {workMode && selectedPackage && original.packages?.length === 1 && <small className="stage-download-count muted">{packageLabel(selectedPackage)}</small>}
        </h4>
        {original.packages && original.packages.length > 1 && <TabSelect label={`${stage}交付版本`} selected={videos.url || ''} onChange={url => setChoices(previous => ({ ...previous, [stage]: url }))} items={original.packages.map(item => ({ value: item.url, label: packageLabel(item) }))} />}
        <div className="stage-download-actions stage-download-packages">
        <DownloadButton url={videos.url} label="视频 ZIP 包" pack title={videos.url
          ? roundMode ? `按${stage}完整分段顺序临时打包，共${videos.count}份原视频` : workMode ? `下载本片${stage}交接清单，共${videos.count}份视频` : `仅下载${episode}场次${scene}的${stage}已采用视频，共${videos.count}份产物文件`
          : roundMode ? `${stage}暂无视频` : workMode ? `本片暂无${stage}交接清单` : `场次${scene}的${stage}暂无已采用视频`} />
        <DownloadButton url={videos.url ? videos.url.replace(/&format=zip$/, '') + '&format=jypack' : null}
          label="剪映草稿包" pack title={roundMode ? `按${stage}完整分段顺序临时生成剪映草稿` : workMode ? '按本片交接清单打包；剪映需支持原生草稿包导入' : '下载后双击或拖入剪映，由剪映导入本场已采用视频；需支持原生草稿包导入及对应会员权限'} />
        </div>
      </section>
      {roundMode && videoList}
      <details className="stage-download-group" aria-label={stage + '原画布'}>
        <summary>原画布</summary>
        {resources.canvas.messages?.map(message => <small className="stage-download-count muted" key={message}>{message}</small>)}
        {!resources.canvas.files.length && !resources.canvas.messages?.length && <small className="stage-download-count muted">暂无对应文件。</small>}
        {resources.canvas.files.length > 0 && <div className="stage-download-actions">
          {resources.canvas.files.map(file => {
            const button = <DownloadButton key={file.url} url={file.url} label={file.label || file.name} title={`下载原文件：${file.name}`} />;
            return file.description ? <div key={file.url} className="stage-download-file">{button}<small className="muted">{file.description}</small></div> : button;
          })}
        </div>}
      </details>
    </section>; })}
    </>}
    </div>
  </div>;
}
