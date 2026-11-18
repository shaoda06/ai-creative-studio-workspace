import { useChloeScope } from './chloeScope';
import { chloeVideoStatuses } from './chloeVideoStatuses';
import { useState } from 'react';
import { useChloeProductionAccess } from './chloeProductionAccess';
import { Link } from 'react-router-dom';
import { PageHeader } from './components/PageHeader';
import { useQuery } from '@tanstack/react-query';
import { get, type FileItem } from './api';
import { Preview, PreviewContext, Result } from './components';
import { ProductionWorkbench } from './components/ProductionWorkbench';
import { ProductionAccessContext } from './components/ProductionAccess';
import { Breadcrumbs, BreadcrumbActionsContext, BreadcrumbSelectorContext } from './components/Breadcrumbs';
import { PageCheckStatus } from './components/PageCheckStatus';
import { TaskApiContext } from './components/TaskApiContext';

export function ChloeProduction({ title, baseUrl, selected, onSelect }: {
  title: string; baseUrl: string; selected: string | null; onSelect: (value: string | null) => void;
}) {
  const { workspacePage, taskApi } = useChloeScope();
  const [actions, setActions] = useState<HTMLDivElement | null>(null);
  const [selector, setSelector] = useState<HTMLSpanElement | null>(null);
  const [preview, setPreview] = useState<FileItem | null>(null);
  const list = useQuery({ queryKey: ['production-videos', baseUrl], queryFn: ({ signal }) => get<FileItem[]>(baseUrl + '/production-videos', signal), refetchInterval: selected ? false : 15000 });
  const videos = list.data?.slice().sort((a, b) => b.name.localeCompare(a.name, undefined, { numeric: true }));
  const projectUrl = (unit: string) => `${baseUrl}/projects/${encodeURIComponent(unit)}`;
  const access = useChloeProductionAccess(baseUrl, selected);
  return <div><ProductionAccessContext value={access}><BreadcrumbActionsContext value={actions}><BreadcrumbSelectorContext value={selector}><PreviewContext value={setPreview}>
    <PageHeader stacked title={title} actions={<Link to={workspacePage}>返回项目列表</Link>}>
    <Breadcrumbs actionsRef={setActions} selectorRef={setSelector} items={[
      { label: '视频制作', onClick: selected ? () => onSelect(null) : undefined },
      ...(selected ? [{ label: selected }] : []),
    ]} />
    </PageHeader>
    <PageCheckStatus queries={[list]} />
    <section className="panel">
    <Result page loading={list.isPending} error={list.error} retry={list.refetch} retrying={list.isFetching} />
    <TaskApiContext value={taskApi}>
      {videos && <ProductionWorkbench showHeadingDownloads={false} inlineListHeading workStatusLabels={chloeVideoStatuses} project={selected || baseUrl} items={videos} selected={selected} onSelect={onSelect} revision={0}
        statistics={{ total: videos.length, completed: 0, notStarted: 0, running: 0 }} />}
    </TaskApiContext>
    </section>
    {preview && selected && <Preview project={selected} baseUrl={projectUrl(selected)} item={preview} revision={0} close={() => setPreview(null)} />}
  </PreviewContext></BreadcrumbSelectorContext></BreadcrumbActionsContext></ProductionAccessContext></div>;
}
