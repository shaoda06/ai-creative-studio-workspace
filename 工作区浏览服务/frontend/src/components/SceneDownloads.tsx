import { useProductionAccess } from './ProductionAccess';
import { useState } from 'react';
import { TabSelect } from './TabSelect';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { get } from '../api';
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

export function SceneDownloads({ project, episode, scene, revision, readOnly }: { project: string; episode: string; scene: string; revision: number; readOnly?: boolean }) {
  const [choices, setChoices] = useState<Record<string, string>>({});
  const access = useProductionAccess();
  const workMode = access.unitKind === 'work';
  const currentWork = workMode && !readOnly;
  const videoLabel = workMode ? '交接视频下载' : '已采用视频下载';
  const downloads = useQuery({ queryKey: ['episode-downloads', access.namespace(project), episode, scene, revision],
    queryFn: () => get<Downloads>(access.downloads(project, episode, scene)), placeholderData: keepPreviousData });
  const packageLabel = (item: StagePackage) => {
    if (!workMode) return item.name;
    const handoff = downloads.data?.workPackages?.find(pkg => pkg.zip === item.url);
    return handoff ? workPackageLabel(handoff) : `未关联整片轮次 · ${item.name}`;
  };
  return <div className="stage-downloads" aria-label="资源下载">
    {(downloads.isFetching || downloads.isPending || downloads.error) && <Result
      loading={downloads.isFetching || downloads.isPending} error={downloads.error} retry={downloads.refetch} retrying={downloads.isFetching} />}
    <div hidden={downloads.isFetching || downloads.isPending || !!downloads.error}>
    {downloads.data && <>
    {(['后处理', '二采', '一采'] as const).map(stage => {
      const original = downloads.data[stage].videos;
      const selectedPackage = original.packages?.find(item => item.url === choices[stage]) || original.packages?.[0];
      const videos = selectedPackage || original;
      return <section className="stage-download-section" key={stage} aria-label={stage + '资源下载'}>
      <h3>{stage}</h3>
      <section className="stage-download-group" aria-label={stage + videoLabel}>
        <h4>{videoLabel} <small className="stage-download-count muted">{videos.count}份产物文件</small></h4>
        {workMode && selectedPackage && original.packages?.length === 1 && <p className="muted">{packageLabel(selectedPackage)}</p>}
        {original.packages && original.packages.length > 1 && <TabSelect label={`${stage}交付版本`} selected={videos.url || ''} onChange={url => setChoices(previous => ({ ...previous, [stage]: url }))} items={original.packages.map(item => ({ value: item.url, label: packageLabel(item) }))} />}
        <div className="stage-download-actions">
        <DownloadButton url={videos.url ? videos.url.replace(/&format=zip$/, '') + '&format=jypack' : null}
          label="剪映草稿包" pack title={workMode ? '按本片交接清单打包；剪映需支持原生草稿包导入' : '下载后双击或拖入剪映，由剪映导入本场已采用视频；需支持原生草稿包导入及对应会员权限'} />
        <DownloadButton url={videos.url} label="视频 ZIP 包" pack title={videos.url
          ? workMode ? `下载本片${stage}交接清单，共${videos.count}份视频` : `仅下载${episode}场次${scene}的${stage}已采用视频，共${videos.count}份产物文件`
          : workMode ? `本片暂无${stage}交接清单` : `场次${scene}的${stage}暂无已采用视频`} />
        </div>
      </section>
      {currentWork ? <details className="stage-download-group" aria-label={stage + '画布与导演包'}>
        <summary>画布与导演包</summary>
        {([{ key: 'canvas', label: '原画布' }, { key: 'director', label: '导演包' }] as const).map(({ key, label }) => {
          const resource = downloads.data[stage][key];
          return <div key={key}>
            <h4>{label}</h4>
            {resource.files.length > 0 && <div className="stage-download-actions">
              <OriginalDownloads resource={resource} label={label} generated={key === 'director'} />
            </div>}
            {resource.messages?.map(message => <p className="muted" key={message}>{message}</p>)}
            {!resource.files.length && !resource.messages?.length && <p className="muted">本场该阶段暂无执行记录。</p>}
          </div>;
        })}
      </details> : <details className="stage-download-group" aria-label={stage + '导演包下载'}>
        <summary>导演包下载</summary>
        <div className="stage-download-actions">
          <OriginalDownloads resource={downloads.data[stage].director} label="下载导演包" generated />
          <OriginalDownloads resource={downloads.data[stage].canvas} label="下载画布" />
        </div>
      </details>}
    </section>; })}
    </>}
    </div>
  </div>;
}
