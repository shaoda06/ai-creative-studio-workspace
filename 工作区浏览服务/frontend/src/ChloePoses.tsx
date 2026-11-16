import { useState } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import type { FileItem, WorkspaceSpace } from './api';
import { ChloeAssetTypes } from './ChloeReferenceAssets';
import { assetPaging, poseAssetPageSize, useAssetList } from './chloeAssetPages';
import { Dialog, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { CopyButton } from './components/CopyButton';
import { FullscreenImage } from './components/FullscreenImage';
import { PageCheckStatus } from './components/PageCheckStatus';
import { Pagination } from './components/Pagination';
import './ChloePoses.css';

interface PoseCard {
  id: string;
  name: string;
  category: string;
  description: string;
  media: FileItem;
}

function PoseDetails({ pose, close }: { pose: PoseCard; close: () => void }) {
  const [zoom, setZoom] = useState(false);
  return <>
    <Dialog title={`${pose.id} · ${pose.name}`} close={close} lockPageScroll>
      <div className="chloe-pose-detail">
        <section aria-label="姿态信息">
          <h3>姿态信息</h3>
          <dl className="chloe-pose-fields">
            <dt>编号</dt><dd>{pose.id}</dd>
            <dt>名称</dt><dd>{pose.name}</dd>
            <dt>分类</dt><dd>{pose.category}</dd>
          </dl>
        </section>
        <button type="button" className="chloe-pose-picture" aria-label={`查看${pose.name}大图`} onClick={() => setZoom(true)}>
          <img src={pose.media.thumbnailUrl || pose.media.url} alt={pose.name} />
        </button>
        <section aria-label="定姿文字">
          <div className="chloe-pose-text-heading">
            <h3>定姿文字</h3>
            <CopyButton text={pose.description} label="复制" />
          </div>
          <div className="chloe-pose-text">{pose.description}</div>
        </section>
      </div>
    </Dialog>
    {zoom && pose.media.url && <FullscreenImage title={pose.name} alt={pose.name} src={pose.media.url} close={() => setZoom(false)} />}
  </>;
}

export function ChloePoses({ workspaceQuery }: { workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const [params, setParams] = useSearchParams();
  const { query, list, changePage, activeTypes, setTypeChecked } = useAssetList<PoseCard>('shared-poses', { page_size: poseAssetPageSize });
  const data = query.isPlaceholderData ? undefined : query.data;
  const selected = data?.items.find(pose => pose.id === params.get('pose'));
  const types = [...new Set([...(query.data?.types ?? []), ...activeTypes])];

  return <>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending || query.isPlaceholderData} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {types.length > 0 && <ChloeAssetTypes types={types} activeTypes={activeTypes} setTypeChecked={setTypeChecked} label="按分类筛选" />}
    {data && (data.items.length ? <div className="chloe-pose-grid">{data.items.map(pose => <AssetMediaCard key={pose.id}
      title={`${pose.id} · ${pose.name}`} item={{ media: pose.media }} revision={0} compact entry aspectRatio="natural"
      to={`?${list}&pose=${encodeURIComponent(pose.id)}`} />)}</div> : <p className="muted">暂无姿态资料。</p>)}
    {data && <Pagination {...assetPaging(data, changePage)} />}
    {selected && <PoseDetails key={selected.id} pose={selected} close={() => setParams(list, { replace: true })} />}
  </>;
}
