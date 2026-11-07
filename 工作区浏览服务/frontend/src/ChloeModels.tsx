import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, WorkspaceSpace } from './api';
import { Dialog, Preview, PreviewContext, Result } from './components';
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
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<FileItem | null>(null);
  const query = useQuery({ queryKey: ['chloe-models', spaceId],
    queryFn: () => get<ModelCard[]>(`/api/workspaces/${encodeURIComponent(spaceId!)}/shared-models`), refetchInterval: 5000 });
  const detail = query.data?.find(model => model.id === selected);
  return <PreviewContext.Provider value={setPreview}>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && (query.data.length ? <div className="asset-media-grid">
      {query.data.map(model => <AssetMediaCard key={model.id} title={`${model.id} · ${model.name}`} formal revision={0}
        item={{ media: model.media, version: model.version, scope: model.identity['资产用途'], emptyLabel: '尚未采用正面面部图' }}
        onDetails={() => setSelected(model.id)} />)}
    </div> : <p className="muted">暂无模特资料。建立模特资料后，每个模特会在这里显示为一张卡片。</p>)}
    {detail && <Dialog title={`${detail.id} · ${detail.name}`} close={() => setSelected(null)}>
      <div className="prose">{([['资产身份', detail.identity], ['人物特征', detail.features]] as const).map(([heading, values]) =>
        <section key={String(heading)}><h3>{String(heading)}</h3><table><thead><tr><th>字段</th><th>内容</th></tr></thead>
          <tbody>{Object.entries(values).map(([name, value]) => <tr key={name}><th scope="row">{name}</th><td>{value}</td></tr>)}</tbody>
        </table></section>
      )}</div>
    </Dialog>}
    {preview && <Preview project="" item={preview} revision={0} close={() => setPreview(null)} />}
  </PreviewContext.Provider>;
}
