import { useState } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { FileItem, WorkspaceSpace } from './api';
import { ChloeAssetTypes } from './ChloeReferenceAssets';
import { assetPaging, useAssetList } from './chloeAssetPages';
import { Dialog, PreviewContext, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { FullscreenImage } from './components/FullscreenImage';
import { LinkButton } from './components/LinkButton';
import { PageCheckStatus } from './components/PageCheckStatus';
import { Pagination } from './components/Pagination';

interface PoseCard {
  id: string;
  name: string;
  description: string;
  media: FileItem;
}

export function ChloePoses({ workspaceQuery }: { workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const { query, changePage, activeTypes, setTypeChecked } = useAssetList<PoseCard>('shared-poses');
  const [image, setImage] = useState<FileItem | null>(null);
  const [description, setDescription] = useState<PoseCard | null>(null);
  const data = query.isPlaceholderData ? undefined : query.data;
  const types = [...new Set([...(query.data?.types ?? []), ...activeTypes])];

  return <>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending || query.isPlaceholderData} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {types.length > 0 && <ChloeAssetTypes types={types} activeTypes={activeTypes} setTypeChecked={setTypeChecked} label="按分类筛选" />}
    {data && (data.items.length ? <PreviewContext.Provider value={setImage}>
      <div className="asset-media-grid">{data.items.map(pose => <AssetMediaCard key={pose.id}
        title={`${pose.id} · ${pose.name}`} item={{ media: pose.media }} revision={0} formal entry aspectRatio="natural"
        titleActions={<LinkButton aria-label={`查看${pose.id}定姿文字`} onClick={() => setDescription(pose)}>定姿文字</LinkButton>} />)}</div>
    </PreviewContext.Provider> : <p className="muted">暂无姿态资料。</p>)}
    {data && <Pagination {...assetPaging(data, changePage)} />}
    {image?.url && <FullscreenImage title={image.name} alt={image.name} src={image.url} close={() => setImage(null)} />}
    {description && <Dialog title={`${description.id} · ${description.name}`} close={() => setDescription(null)}>
      {description.description.split(/\n\s*\n/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
    </Dialog>}
  </>;
}
