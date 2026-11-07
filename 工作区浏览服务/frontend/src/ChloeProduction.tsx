import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from './components/PageHeader';
import { useQuery } from '@tanstack/react-query';
import { get, type FileItem } from './api';
import { Preview, PreviewContext, Result } from './components';
import { ProductionWorkbench } from './components/ProductionWorkbench';
import { ProductionAccessContext, type ProductionAccess } from './components/ProductionAccess';
import { Breadcrumbs, BreadcrumbActionsContext, BreadcrumbSelectorContext } from './components/Breadcrumbs';
import { PageCheckStatus } from './components/PageCheckStatus';

export function ChloeProduction({ title, baseUrl, selected, onSelect }: {
  title: string; baseUrl: string; selected: string | null; onSelect: (value: string | null) => void;
}) {
  const [actions, setActions] = useState<HTMLDivElement | null>(null);
  const [selector, setSelector] = useState<HTMLSpanElement | null>(null);
  const [preview, setPreview] = useState<FileItem | null>(null);
  const list = useQuery({ queryKey: ['production-videos', baseUrl], queryFn: () => get<FileItem[]>(baseUrl + '/production-videos'), refetchInterval: 5000 });
  const projectUrl = (unit: string) => `${baseUrl}/projects/${encodeURIComponent(unit)}`;
  const workUrl = (unit: string) => `${projectUrl(unit)}/works/${encodeURIComponent(unit.split('-')[0])}`;
  const access = useMemo<ProductionAccess>(() => ({
    unitKind: 'work', storyboardLabel: '分镜脚本', sourceDocumentLabel: '脚本', showStoryboardEditor: false, namespace: () => baseUrl,
    detail: (_, unit) => workUrl(unit) + '/production-detail',
    scope: (_, unit, scene) => ({ project: unit, episode: unit, scene, label: `${unit}整片`,
      notesUrl: workUrl(unit) + '/production-notes', stateKey: `${baseUrl}/${unit}/${scene}` }),
    notesSummary: scope => workUrl(scope.episode) + '/production-notes',
    notes: scope => workUrl(scope.episode) + '/production-notes',
    downloads: (_, unit, scene) => workUrl(unit) + '/production-downloads?scene=' + encodeURIComponent(scene),
    package: (_, unit) => projectUrl(unit) + '/download',
    document: (_, path) => projectUrl(selected!) + '/document?path=' + encodeURIComponent(path),
  }), [baseUrl, selected]);
  return <div><ProductionAccessContext value={access}><BreadcrumbActionsContext value={actions}><BreadcrumbSelectorContext value={selector}><PreviewContext value={setPreview}>
    <PageHeader stacked title={title} actions={<Link to="/">返回工作区</Link>}>
    <Breadcrumbs actionsRef={setActions} selectorRef={setSelector} items={[
      { label: '视频制作', onClick: selected ? () => onSelect(null) : undefined },
      ...(selected ? [{ label: selected }] : []),
    ]} />
    </PageHeader>
    <PageCheckStatus queries={[list]} />
    <section className="panel">
    <Result page loading={list.isPending} error={list.error} retry={list.refetch} retrying={list.isFetching} />
    {list.data && <ProductionWorkbench project={selected || baseUrl} items={list.data} selected={selected} onSelect={onSelect} revision={0}
      statistics={{ total: list.data.length, completed: 0, notStarted: 0, running: 0 }} />}
    </section>
    {preview && selected && <Preview project={selected} baseUrl={projectUrl(selected)} item={preview} revision={0} close={() => setPreview(null)} />}
  </PreviewContext></BreadcrumbSelectorContext></BreadcrumbActionsContext></ProductionAccessContext></div>;
}
