import { useProductionAccess } from './ProductionAccess';
import { useState } from 'react';
import { TabSelect } from './TabSelect';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { get } from '../api';
import type { FileItem } from '../api';
import { Result } from '../components';
import { DownloadButton } from './DownloadButton';
import './SceneDownloads.css';

type StagePackage = { name: string; count: number; url: string };
type Resource = { packages?: StagePackage[]; count: number; url: string | null; files: { name: string; url: string }[]; messages?: string[] };
interface WorkPackage {
  key: string; label: string; version: string; purpose: string; rounds: number[];
  count?: number; archived?: boolean; jypack: string | null; zip: string | null;
}
export type Downloads = Record<'后处理' | '二采' | '一采', Record<'videos' | 'director' | 'canvas', Resource>>
  & { workPackages?: WorkPackage[] };

export function workPackageLabel({ label, rounds }: WorkPackage) {
  return rounds.length ? `${rounds.map(number => `第${number}轮`).join('、')} · ${label}` : label;
}

function OriginalDownloads({ resource, label, generated = false }: { resource: Resource; label: string; generated?: boolean }) {
  return resource.files.length
    ? <>{resource.files.map(file => <DownloadButton key={file.url} url={file.url} label={file.name} title={`${generated ? '按需生成导演包' : '下载原文件'}：${file.name}`} />)}</>
    : <DownloadButton url={resource.url} label={label} title={resource.url ? '按当前已采用来源临时生成导演包' : '本场该阶段暂无对应文件'} />;
}

export function SceneDownloads({ project, episode, scene, revision, segments = [] }: {
  project: string; episode: string; scene: string; revision: number; segments?: NonNullable<FileItem['segments']>[string];
}) {
  const [choices, setChoices] = useState<Record<string, string>>({});
  const access = useProductionAccess();
  const workMode = access.unitKind === 'work';
  const downloads = useQuery({ queryKey: ['episode-downloads', access.namespace(project), episode, scene, revision],
    queryFn: () => get<Downloads>(access.downloads(project, episode, scene)), placeholderData: keepPreviousData });
  const packageLabel = (item: StagePackage) => {
    if (!workMode) return item.name;
    const handoff = downloads.data?.workPackages?.find(pkg => pkg.zip === item.url);
    return handoff ? workPackageLabel(handoff) : `未关联整片轮次 · ${item.name}`;
  };
  const adopted = segments.flatMap(item => item.videos.filter(video => video.approved && video.url)
    .map(video => ({ id: item.id, video })));
  const archivedPackages = downloads.data?.workPackages?.filter(item => item.archived) || [];
  const hasResources = downloads.data && (adopted.length > 0 || archivedPackages.length > 0 || Object.values(downloads.data).some(group =>
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
    {(['后处理', '二采', '一采'] as const).map(stage => {
      const original = downloads.data[stage].videos;
      const selectedPackage = original.packages?.find(item => item.url === choices[stage]) || original.packages?.[0];
      const videos = selectedPackage || original;
      const approved = adopted.filter(item => item.video.stage === stage);
      return <section className="stage-download-section" key={stage} aria-label={stage + '资源下载'}>
      <h3>{stage}</h3>
      <details className="stage-download-group" aria-label={stage + '已采用视频'}>
        <summary>已采用视频 <small className="stage-download-count muted">{approved.length} 段</small></summary>
        {approved.length ? <div className="stage-download-actions">{approved.map(({ id, video }) =>
          <DownloadButton key={video.key} url={video.downloadUrl || video.url} label={`${id} · ${video.run}`} title="下载已采用的原视频" />)}</div> : <p className="muted">暂无已采用视频。</p>}
      </details>
      <section className="stage-download-group" aria-label={stage + '交接包'}>
        <h4>交接包 {videos.url && <small className="stage-download-count muted">{videos.count} 份视频</small>}</h4>
        {!videos.url && <p className="muted">{workMode ? '尚未登记交接包。' : '尚无可下载的交接包。'}</p>}
        {workMode && selectedPackage && original.packages?.length === 1 && <p className="muted">{packageLabel(selectedPackage)}</p>}
        {original.packages && original.packages.length > 1 && <TabSelect label={`${stage}交付版本`} selected={videos.url || ''} onChange={url => setChoices(previous => ({ ...previous, [stage]: url }))} items={original.packages.map(item => ({ value: item.url, label: packageLabel(item) }))} />}
        <div className="stage-download-actions stage-download-packages">
        <DownloadButton url={videos.url} label="视频 ZIP 包" pack title={videos.url
          ? workMode ? `下载本片${stage}交接清单，共${videos.count}份视频` : `仅下载${episode}场次${scene}的${stage}已采用视频，共${videos.count}份产物文件`
          : workMode ? `本片暂无${stage}交接清单` : `场次${scene}的${stage}暂无已采用视频`} />
        <DownloadButton url={videos.url ? videos.url.replace(/&format=zip$/, '') + '&format=jypack' : null}
          label="剪映草稿包" pack title={workMode ? '按本片交接清单打包；剪映需支持原生草稿包导入' : '下载后双击或拖入剪映，由剪映导入本场已采用视频；需支持原生草稿包导入及对应会员权限'} />
        </div>
      </section>
      <details className="stage-download-group" aria-label={stage + '画布与导演包'}>
        <summary>画布与导演包</summary>
        {([{ key: 'canvas', label: '原画布' }, { key: 'director', label: '导演包' }] as const).map(({ key, label }) => {
          const resource = downloads.data[stage][key];
          return <div key={key}>
            <h4>{label}</h4>
            {(resource.files.length > 0 || resource.url) && <div className="stage-download-actions">
              <OriginalDownloads resource={resource} label={key === 'director' ? '下载导演包' : '下载画布'} generated={key === 'director'} />
            </div>}
            {resource.messages?.map(message => <p className="muted" key={message}>{message}</p>)}
            {!resource.files.length && !resource.url && !resource.messages?.length && <p className="muted">暂无对应文件。</p>}
          </div>;
        })}
      </details>
    </section>; })}
    </>}
    </div>
  </div>;
}
