import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, WorkspaceSpace } from './api';
import { Preview, PreviewContext, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { PageCheckStatus } from './components/PageCheckStatus';

interface ModelCard {
  id: string;
  name: string;
  identity: Record<string, string>;
  features: Record<string, string>;
  media: FileItem | null;
  version: string | null;
}

export function ChloeModels({ workspaceQuery }: { workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const { spaceId } = useParams();
  const [preview, setPreview] = useState<FileItem | null>(null);
  const query = useQuery({ queryKey: ['chloe-models', spaceId],
    queryFn: () => get<ModelCard[]>(`/api/workspaces/${encodeURIComponent(spaceId!)}/shared-models`), refetchInterval: 5000 });
  return <PreviewContext.Provider value={setPreview}>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && (query.data.length ? <div className="asset-media-grid">
      {query.data.map(model => <AssetMediaCard key={model.id} title={`${model.id} · ${model.name}`} formal entry revision={0}
        item={{ media: model.media, emptyLabel: '尚未采用正面面部图' }} />)}
    </div> : <p className="muted">暂无模特资料。建立模特资料后，每个模特会在这里显示为一张卡片。</p>)}
    {preview && <Preview project="" item={preview} revision={0} close={() => setPreview(null)} />}
  </PreviewContext.Provider>;
}
