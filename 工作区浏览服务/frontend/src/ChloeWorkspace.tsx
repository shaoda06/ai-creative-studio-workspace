import { useContext } from 'react';
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
import { ChloeModels } from './ChloeModels';

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
  { value: 'looks', label: '造型' },
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
  const { spaceId } = useParams();
  const space = workspaceQuery.data?.find(item => item.id === spaceId);
  const [params, setParams] = useSearchParams();
  const current = sections.find(section => section.value === params.get('section')) || sections[0];
  const assetCategory = assetCategories.find(item => item.value === params.get('asset')) || assetCategories[0];
  return <>
    <PageHeader title={space!.name} stacked={current.value === 'assets'} actions={<Link to="/">返回工作区</Link>}>
      {current.value === 'assets' && <Breadcrumbs items={[
        { label: '共用资产', href: `#/spaces/${encodeURIComponent(spaceId!)}?section=assets` },
        { label: assetCategory.label },
      ]} />}
    </PageHeader>
    {controls && createPortal(<TabNav wide label="Chloe栏目" items={sections} selected={current.value}
      onChange={value => setParams({ section: value })} />, controls)}
    {current.value === 'overview' ? <AccountOverview workspaceQuery={workspaceQuery} /> : <section className="panel" aria-label={current.label}>
      {(current.value !== 'assets' || assetCategory.value !== 'models') && <PageCheckStatus queries={[workspaceQuery]} />}
      {current.value !== 'assets' && <h2>{current.label}</h2>}
      {current.value === 'assets' ? <>
        <UnderlineTabs label="共用资产分类" items={assetCategories} selected={assetCategory.value}
          onChange={value => setParams({ section: 'assets', asset: value })} />
        {assetCategory.value === 'models' ? <ChloeModels key={spaceId} workspaceQuery={workspaceQuery} /> :
          <p className="muted">该分类的展示内容待下一步确定。</p>}
      </> : <>
        <p>{current.description}</p>
        <p className="muted">当前为栏目预览，具体内容随后补充。</p>
      </>}
    </section>}
  </>;
}
