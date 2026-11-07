import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { get } from './api';
import { Result } from './components';
import { PageHeader } from './components/PageHeader';
import { PageCheckStatus } from './components/PageCheckStatus';
import { MessagePanel } from './components/MessagePanel';
import { UnderlineTabs } from './components/UnderlineTabs';
import { ChloeAccountOverview } from './ChloeAccountOverview';
import type { ChloeOverviewData } from './ChloeAccountOverview';

export default function ChloeOverviewExample() {
  const [params, setParams] = useSearchParams();
  const scenario = params.get('scenario') === 'new' ? 'new' : 'working';
  const query = useQuery({ queryKey: ['chloe-overview-example', scenario],
    queryFn: () => get<ChloeOverviewData>(`/api/examples/chloe/overview?scenario=${scenario}`) });
  return <div className="home">
    <PageHeader eyebrow="Chloe · 页面演示" title="账号概况" description="查看账号方向、制作概况与视频进度。"
      actions={<Link to="/spaces/chloe?section=overview">返回 Chloe</Link>} />
    <MessagePanel messages={[{ id: 'demo', content: '以下为演示资料，仅供查看布局。' }]} />
    <UnderlineTabs label="账号概况演示状态" items={[{ value: 'working', label: '已有制作的示例' }, { value: 'new', label: '新账号空白状态' }]}
      selected={scenario} onChange={value => setParams({ scenario: value })} />
    <PageCheckStatus queries={[query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && <ChloeAccountOverview data={query.data} />}
  </div>;
}
