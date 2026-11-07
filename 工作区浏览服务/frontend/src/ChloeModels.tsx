import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, WorkspaceSpace } from './api';
import { Dialog, Preview, PreviewContext, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { PageCheckStatus } from './components/PageCheckStatus';
import { MessagePanel } from './components/MessagePanel';

interface ModelCard {
  id: string;
  name: string;
  identity: Record<string, string>;
  features: Record<string, string>;
  media: FileItem | null;
  version: string | null;
}

const exampleModels: ModelCard[] = [{
  id: 'DEMO-M001', name: '示例模特',
  identity: { '资产编号': 'DEMO-M001', '资产名称': '示例模特', '资产类型': '模特',
    '资产用途': '服装上身展示、日常穿搭演示。', '来源说明': '页面布局占位示例，非正式模特。', '使用限制': '仅用于确认资料卡样式。' },
  features: { '外观性别': '女性（示例）', '视觉年龄': '25岁左右（示例）', '面部特征': '待设计',
    '发型与发色': '黑色中长发（示例）', '肤色': '待设计', '体型与头身比例': '待设计',
    '人物气质': '自然、亲切（示例）', '保持一致的特征': '待设计' },
  media: { kind: 'image', name: '人物剪影占位图', key: 'demo-portrait', url: '/examples/chloe-model-placeholder.svg' }, version: 'V001',
}];

export function ChloeModels({ workspaceQuery }: { workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const { spaceId } = useParams();
  const [params] = useSearchParams();
  const example = params.get('example') === 'model-card';
  const base = `/spaces/${encodeURIComponent(spaceId!)}?section=assets&asset=models`;
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<FileItem | null>(null);
  const query = useQuery({ queryKey: ['chloe-models', spaceId],
    queryFn: () => get<ModelCard[]>(`/api/workspaces/${encodeURIComponent(spaceId!)}/shared-models`), refetchInterval: 5000, enabled: !example });
  const models = example ? exampleModels : query.data;
  const detail = models?.find(model => model.id === selected);
  return <PreviewContext.Provider value={setPreview}>
    <PageCheckStatus queries={example ? [workspaceQuery] : [workspaceQuery, query]} />
    {example && <MessagePanel messages={[{ id: 'model-example', content: '占位模特卡示例：人物剪影、资料和版本仅用于确认样式，不属于正式资产。' }]} />}
    {!example && <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />}
    {models && (models.length ? <div className="asset-media-grid">
      {models.map(model => <AssetMediaCard key={model.id} title={`${model.id} · ${model.name}`} formal revision={0}
        item={{ media: model.media, version: model.version, scope: model.identity['资产用途'], emptyLabel: '尚未采用正面面部图' }}
        onDetails={() => setSelected(model.id)} />)}
    </div> : <p className="muted">暂无模特资料。建立模特资料后，每个模特会在这里显示为一张卡片。</p>)}
    <p><Link to={example ? base : `${base}&example=model-card`}>{example ? '退出示例，返回实际模特' : '查看占位模特卡'}</Link></p>
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
