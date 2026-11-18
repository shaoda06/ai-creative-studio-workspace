import { Result, Rich } from './components';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';

export interface AssetSection { heading: string; html: string; empty: boolean }

export function ChloeAssetRecords({ sections, url, lookId }: { sections: AssetSection[]; url?: string; lookId?: string }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({ queryKey: ['chloe-asset-records', url],
    queryFn: ({ signal }) => get<{sections: AssetSection[]; looks?: {id:string; sections:AssetSection[]}[]}>(url!, signal), enabled: open && !!url,
    refetchInterval: open ? 30000 : false });
  const loaded = lookId ? query.data?.looks?.find(look => look.id === lookId)?.sections : query.data?.sections;
  const content = (heading: string) => {
    const section = (loaded || sections).find(item=>item.heading===heading);
    if (!section) return null;
    return section.empty ? <p className="muted">暂无{heading}。</p> : <Rich html={section.html} />;
  };
  return <details className="panel" onToggle={event => setOpen(event.currentTarget.open)}><summary>资料与制作记录</summary>
    {url && <Result loading={open && query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />}
    {['关联资料','当前采用','采用变更'].map(heading=><details key={heading}><summary>{heading==='当前采用' ? '采用依据与时间' : heading}</summary>{content(heading)}</details>)}
    <details><summary>执行记录</summary>{['执行记录','输入记录','输出记录','审阅记录','返修记录'].map(heading=><section key={heading}>{heading!=='执行记录' && <h3>{heading}</h3>}{content(heading)}</section>)}</details>
  </details>;
}
