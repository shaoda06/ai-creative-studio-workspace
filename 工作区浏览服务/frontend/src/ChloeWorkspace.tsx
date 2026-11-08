import { useChloeScope } from './chloeScope';
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
import { ChloeReferenceAssets, ChloeReferenceAssetDetail, referenceAssetKinds } from './ChloeReferenceAssets';
import type { ReferenceAssetDetail, ReferenceAssetKind } from './ChloeReferenceAssets';
import { ChloeVoices, ChloeVoiceDetail } from './ChloeVoices';
import type { VoiceDetail } from './ChloeVoices';
import { ChloeProduction } from './ChloeProduction';
import { ChloeReview } from './ChloeReview';
import { ChloePublication } from './ChloePublication';
import { ChloeResources } from './ChloeResources';
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
  const { api } = useChloeScope();
  const query = useQuery({ queryKey: ['account-overview', api],
    queryFn: () => get<ChloeOverviewData>(`${api}/account-overview`),
    refetchInterval: 5000 });
  return <section aria-label="账号概况">
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && <ChloeAccountOverview data={query.data} />}
  </section>;
}

export function ChloeWorkspace({ workspaceQuery }: { workspaceQuery: WorkspaceQuery }) {
  const controls = useContext(HeaderControlsContext);
  const [breadcrumbActions, setBreadcrumbActions] = useState<HTMLDivElement | null>(null);
  const { spaceId } = useParams();
  const { api, page, context, workspacePage } = useChloeScope();
  const space = workspaceQuery.data?.find(item => item.id === spaceId);
  const [params, setParams] = useSearchParams();
  const current = sections.find(section => section.value === params.get('section')) || sections[0];
  const assetCategory = assetCategories.find(item => item.value === params.get('asset')) || assetCategories[0];
  const modelId = current.value === 'assets' && assetCategory.value === 'models' ? params.get('model') : null;
  const modelQuery = useQuery({queryKey:['chloe-model',api,modelId], queryFn:()=>get<ModelDetail>(`${api}/shared-models/${encodeURIComponent(modelId!)}`), enabled:!!modelId, refetchInterval:5000});
  const referenceKind = assetCategory.value in referenceAssetKinds ? assetCategory.value as ReferenceAssetKind : null;
  const referenceConfig = referenceKind ? referenceAssetKinds[referenceKind] : null;
  const referenceId = current.value==='assets' && referenceConfig ? params.get(referenceConfig.parameter) : null;
  const referenceQuery = useQuery({queryKey:['chloe-reference-detail',referenceKind,api,referenceId],queryFn:()=>get<ReferenceAssetDetail>(`${api}/${referenceConfig!.endpoint}/${encodeURIComponent(referenceId!)}`),enabled:!!referenceId,refetchInterval:5000});
  const voiceId = current.value==='assets' && assetCategory.value==='voices' ? params.get('voice') : null;
  const voiceQuery = useQuery({queryKey:['chloe-voice',api,voiceId],queryFn:()=>get<VoiceDetail>(`${api}/shared-voices/${encodeURIComponent(voiceId!)}`),enabled:!!voiceId,refetchInterval:5000});
  const currentLook = params.get('modelTab')==='looks' ? modelQuery.data?.looks.find(item=>item.id===params.get('look')) : undefined;
  return <>
    {!['production', 'publication'].includes(current.value) && <PageHeader title={context || space!.name} stacked actions={<Link to={workspacePage}>返回项目列表</Link>}>
      {current.value === 'assets' && <Breadcrumbs actionsRef={setBreadcrumbActions} items={[
        { label: '共用资产', href: `#${page}?section=assets` },
        { label: assetCategory.label, href: modelId || referenceId || voiceId ? `#${page}?section=assets&asset=${assetCategory.value}` : undefined },
        ...(modelId ? [{label:modelQuery.data ? `${modelId} · ${modelQuery.data.name}` : modelId, href:currentLook ? `#${page}?section=assets&asset=models&model=${encodeURIComponent(modelId)}&modelTab=looks` : undefined}] : []),
        ...(referenceId ? [{label:referenceQuery.data ? `${referenceId} · ${referenceQuery.data.name}` : referenceId}] : []),
        ...(voiceId ? [{label:voiceQuery.data ? `${voiceId} · ${voiceQuery.data.name}` : voiceId}] : []),
        ...(currentLook ? [{label:`${currentLook.id} · ${currentLook.name}`}] : []),
      ]} />}
      {current.value !== 'assets' && <Breadcrumbs items={[{ label: current.label }]} />}
    </PageHeader>}
    {breadcrumbActions && (referenceId || currentLook || voiceId) && createPortal(
      voiceId ? <Link to={`${page}?section=assets&asset=voices`}>返回声音列表</Link> :
      referenceId ? <Link to={`${page}?section=assets&asset=${referenceKind}`}>返回{referenceConfig!.label}列表</Link> :
        <Link to={`${page}?section=assets&asset=models&model=${encodeURIComponent(modelId!)}&modelTab=looks`}>返回造型列表</Link>, breadcrumbActions)}
    {controls && createPortal(<TabNav wide label="Chloe栏目" items={sections} selected={current.value}
      onChange={value => setParams({ section: value })} />, controls)}
    {current.value === 'publication' ? <ChloePublication title={context || space!.name} baseUrl={api} selected={params.get('video')} onSelect={value => setParams(value ? {section:'publication',video:value} : {section:'publication'})} /> : current.value === 'production' ? <ChloeProduction title={context || space!.name} baseUrl={api} selected={params.get('video')} onSelect={value => setParams(value ? {section:'production',video:value} : {section:'production'})} /> : current.value === 'resources' ? <ChloeResources key={api} workspaceQuery={workspaceQuery} /> : current.value === 'overview' ? <AccountOverview workspaceQuery={workspaceQuery} /> : <section className={modelId || referenceId || voiceId ? undefined : 'panel'} aria-label={current.label}>
      {current.value !== 'review' && (current.value !== 'assets' || !['models','clothing','scenes','voices'].includes(assetCategory.value)) && <PageCheckStatus queries={[workspaceQuery]} />}
      {current.value !== 'assets' && <h2>{current.label}</h2>}
      {current.value === 'review' ? <ChloeReview key={api} /> : current.value === 'assets' ? voiceId ? <ChloeVoiceDetail key={`${spaceId}/${voiceId}`} query={voiceQuery} workspaceQuery={workspaceQuery} /> : modelId ? <ChloeModelDetail key={`${spaceId}/${modelId}`} query={modelQuery} workspaceQuery={workspaceQuery} /> : referenceId ? <ChloeReferenceAssetDetail kind={referenceKind!} key={`${spaceId}/${referenceKind}/${referenceId}`} query={referenceQuery} workspaceQuery={workspaceQuery} /> : <>
        <UnderlineTabs label="共用资产分类" items={assetCategories} selected={assetCategory.value}
          onChange={value => setParams({ section: 'assets', asset: value })} />
        <div className="chloe-assets-content">{assetCategory.value === 'models' ? <ChloeModels key={spaceId} workspaceQuery={workspaceQuery} /> : referenceKind ? <ChloeReferenceAssets kind={referenceKind} key={`${spaceId}/${referenceKind}`} workspaceQuery={workspaceQuery} /> :
          <ChloeVoices key={spaceId} workspaceQuery={workspaceQuery} />}</div>
      </> : <>
        <p>{current.description}</p>
        <p className="muted">当前为栏目预览，具体内容随后补充。</p>
      </>}
    </section>}
  </>;
}
