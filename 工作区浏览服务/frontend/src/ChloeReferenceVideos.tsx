import { assetPaging, useAssetList } from './chloeAssetPages';
import { Pagination } from './components/Pagination';
import type { UseQueryResult } from '@tanstack/react-query';
import type { FileItem, WorkspaceSpace } from './api';
import { useChloeScope } from './chloeScope';
import { Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { PageCheckStatus } from './components/PageCheckStatus';
import { ReleaseFilmPlayer } from './components/ReleaseFilms';
import { formatProductionDuration } from './components/useEpisodeDurations';

export type ReferenceVideoCard = { id: string; name: string; coverUrl: string; videoUrl: string; status: '制作中' | '可用' };
export type ReferenceVideoDetail = {
  id: string;
  name: string;
  status: ReferenceVideoCard['status'];
  source: string;
  sourceUrl: string | null;
  description: string;
  duration: number;
  aspectRatio: string;
  width: number;
  height: number;
  media: FileItem;
};

type WorkspaceQuery = UseQueryResult<WorkspaceSpace[]>;

export function ChloeReferenceVideos({ workspaceQuery }: { workspaceQuery: WorkspaceQuery }) {
  const { page } = useChloeScope();
  const { query, list, changePage } = useAssetList<ReferenceVideoCard>('shared-reference-videos');
  const data = query.isPlaceholderData ? undefined : query.data;
  return <>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending || query.isPlaceholderData} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {data && (data.items.length ? <div className="asset-media-grid">
      {data.items.map(video => <AssetMediaCard key={video.id} title={`${video.id} · ${video.name}`}
        entry formal revision={0} aspectRatio="natural"
        to={`${page}?${list}&referenceVideo=${encodeURIComponent(video.id)}`}
        item={{ media: { kind: 'image', key: video.id, url: video.coverUrl, name: `${video.name}的首帧` } }} />)}
    </div> : <p className="muted">暂无参考视频。</p>)}
    {data && <Pagination {...assetPaging(data, changePage)} />}
  </>;
}

export function ChloeReferenceVideoDetail({ query, workspaceQuery }: {
  query: UseQueryResult<ReferenceVideoDetail>;
  workspaceQuery: WorkspaceQuery;
}) {
  const video = query.data;
  return <>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {video && <div className="chloe-look-detail chloe-model-layout">
      <section className="panel chloe-look-info" aria-label="参考视频信息">
        <h2>参考视频信息</h2>
        <dl className="chloe-overview-fields">
          <div><dt>标题</dt><dd>{video.name}</dd></div>
          <div><dt>状态</dt><dd>{video.status}</dd></div>
          <div><dt>来源</dt><dd>{video.sourceUrl ? <a href={video.sourceUrl} target="_blank" rel="noreferrer">{video.source.split('－', 1)[0]}</a> : video.source}</dd></div>
          <div><dt>时长</dt><dd>{formatProductionDuration({ seconds: video.duration, estimated: false })}</dd></div>
          <div><dt>比例</dt><dd>{video.aspectRatio}</dd></div>
          <div><dt>分辨率</dt><dd>{video.width} × {video.height}</dd></div>
          <div><dt>内容简介</dt><dd>{video.description}</dd></div>
        </dl>
      </section>
      <section className="panel chloe-look-image-column" aria-label="参考视频播放">
        <ReleaseFilmPlayer key={video.media.url} item={video.media} />
      </section>
    </div>}
  </>;
}
