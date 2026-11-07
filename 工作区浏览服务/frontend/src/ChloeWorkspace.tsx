import { useContext, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { get } from './api';
import type { WorkspaceSpace } from './api';
import { Result } from './components';
import { PageCheckStatus } from './components/PageCheckStatus';
import { ChloeAccountOverview } from './ChloeAccountOverview';
import type { ChloeOverviewData } from './ChloeAccountOverview';
import { HeaderControlsContext } from './components/AppShell';
import { TabNav } from './components/TabNav';
import { UnderlineTabs } from './components/UnderlineTabs';
import { Breadcrumbs } from './components/Breadcrumbs';
import { PageHeader } from './components/PageHeader';
import { ChloeClothing, ChloeClothingDetail } from './ChloeClothing';
import type { ClothingDetail } from './ChloeClothing';
import { ChloeProduction } from './ChloeProduction';
import { ChloeModels } from './ChloeModels';
import { ChloeModelDetail } from './ChloeModelDetail';
import type { ModelDetail } from './ChloeModelDetail';

const sections = [
  { value: 'overview', label: '账号概况', description: '发布平台、目标人群与内容风格。' },
  { value: 'products', label: '选品与商品', description: '候选选品、商品资料、带货条件与关联视频。' },
  { value: 'assets', label: '共用资产', description: 'AI模特、服装、造型、场景与声音。' },
  { value: 'production', label: '视频制作', description: '单条视频的脚本、参考素材、生成审阅与剪映交接。' },
  { value: 'publication', label: '成片与发布', description: '人工成片、封面文案、关联商品与发布记录。' },
  { value: 'review', label: '运营复盘', description: '单条表现、跨视频结论与调整验证。' },
  { value: 'resources', label: '资源库', description: '共用及视频专属的图片、视频、音频与具体版本。' },
];

const assetCategories = [
  { value: 'models', label: 'AI 模特' },
  { value: 'clothing', label: '服装' },
  { value: 'scenes', label: '场景' },
  { value: 'voices', label: '声音' },
];

type WorkspaceQuery = UseQueryResult<WorkspaceSpace[]>;

function AccountOverview({ workspaceQuery }: { workspaceQuery: WorkspaceQuery }) {
  const { spaceId } = useParams();
  const query = useQuery({ queryKey: ['account-overview', spaceId],
    queryFn: () => get<ChloeOverviewData>(`/api/workspaces/${encodeURIComponent(spaceId!)}/account-overview`),
    refetchInterval: 5000 });
  return <section aria-label="账号概况">
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && <ChloeAccountOverview data={query.data} />}
    <p><Link to="/examples/chloe/overview">查看账号概况演示</Link></p>
  </section>;
}

export function ChloeWorkspace({ workspaceQuery }: { workspaceQuery: WorkspaceQuery }) {
  const controls = useContext(HeaderControlsContext);
  const [breadcrumbActions, setBreadcrumbActions] = useState<HTMLDivElement | null>(null);
  const { spaceId } = useParams();
  const space = workspaceQuery.data?.find(item => item.id === spaceId);
  const [params, setParams] = useSearchParams();
  const current = sections.find(section => section.value === params.get('section')) || sections[0];
  const assetCategory = assetCategories.find(item => item.value === params.get('asset')) || assetCategories[0];
  const modelId = current.value === 'assets' && assetCategory.value === 'models' ? params.get('model') : null;
  const modelQuery = useQuery({queryKey:['chloe-model',spaceId,modelId], queryFn:()=>get<ModelDetail>(`/api/workspaces/${encodeURIComponent(spaceId!)}/shared-models/${encodeURIComponent(modelId!)}`), enabled:!!modelId, refetchInterval:5000});
  const clothingId = current.value==='assets' && assetCategory.value==='clothing' ? params.get('clothing') : null;
  const clothingQuery = useQuery({queryKey:['chloe-clothing-detail',spaceId,clothingId],queryFn:()=>get<ClothingDetail>(`/api/workspaces/${encodeURIComponent(spaceId!)}/shared-clothing/${encodeURIComponent(clothingId!)}`),enabled:!!clothingId,refetchInterval:5000});
  const currentLook = params.get('modelTab')==='looks' ? modelQuery.data?.looks.find(item=>item.id===params.get('look')) : undefined;
  return <>
    {current.value !== 'production' && <PageHeader title={space!.name} stacked={current.value === 'assets'} actions={<Link to="/">返回工作区</Link>}>
      {current.value === 'assets' && <Breadcrumbs actionsRef={setBreadcrumbActions} items={[
        { label: '共用资产', href: `#/spaces/${encodeURIComponent(spaceId!)}?section=assets` },
        { label: assetCategory.label, href: modelId || clothingId ? `#/spaces/${encodeURIComponent(spaceId!)}?section=assets&asset=${assetCategory.value}` : undefined },
        ...(modelId ? [{label:modelQuery.data ? `${modelId} · ${modelQuery.data.name}` : modelId, href:currentLook ? `#/spaces/${encodeURIComponent(spaceId!)}?section=assets&asset=models&model=${encodeURIComponent(modelId)}&modelTab=looks` : undefined}] : []),
        ...(clothingId ? [{label:clothingQuery.data ? `${clothingId} · ${clothingQuery.data.name}` : clothingId}] : []),
        ...(currentLook ? [{label:`${currentLook.id} · ${currentLook.name}`}] : []),
      ]} />}
    </PageHeader>}
    {breadcrumbActions && (clothingId || currentLook) && createPortal(
      clothingId ? <Link to={`/spaces/${encodeURIComponent(spaceId!)}?section=assets&asset=clothing`}>返回服装列表</Link> :
        <Link to={`/spaces/${encodeURIComponent(spaceId!)}?section=assets&asset=models&model=${encodeURIComponent(modelId!)}&modelTab=looks`}>返回造型列表</Link>, breadcrumbActions)}
    {controls && createPortal(<TabNav wide label="Chloe栏目" items={sections} selected={current.value}
      onChange={value => setParams({ section: value })} />, controls)}
    {current.value === 'production' ? <ChloeProduction title={space!.name} baseUrl={`/api/workspaces/${encodeURIComponent(spaceId!)}`} selected={params.get('video')} onSelect={value => setParams(value ? {section:'production',video:value} : {section:'production'})} /> : current.value === 'overview' ? <AccountOverview workspaceQuery={workspaceQuery} /> : <section className={modelId || clothingId ? undefined : 'panel'} aria-label={current.label}>
      {(current.value !== 'assets' || !['models','clothing'].includes(assetCategory.value)) && <PageCheckStatus queries={[workspaceQuery]} />}
      {current.value !== 'assets' && <h2>{current.label}</h2>}
      {current.value === 'assets' ? modelId ? <ChloeModelDetail key={`${spaceId}/${modelId}`} query={modelQuery} workspaceQuery={workspaceQuery} /> : clothingId ? <ChloeClothingDetail key={`${spaceId}/${clothingId}`} query={clothingQuery} workspaceQuery={workspaceQuery} /> : <>
        <UnderlineTabs label="共用资产分类" items={assetCategories} selected={assetCategory.value}
          onChange={value => setParams({ section: 'assets', asset: value })} />
        <div className="chloe-assets-content">{assetCategory.value === 'models' ? <ChloeModels key={spaceId} workspaceQuery={workspaceQuery} /> : assetCategory.value==='clothing' ? <ChloeClothing key={spaceId} workspaceQuery={workspaceQuery} /> :
          <p className="muted">该分类的展示内容待下一步确定。</p>}</div>
      </> : <>
        <p>{current.description}</p>
        <p className="muted">当前为栏目预览，具体内容随后补充。</p>
      </>}
    </section>}
  </>;
}
