import { useMemo, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get, type FileItem } from '../api';
import { Result } from '../components';
import { ProductionWorkbench } from './ProductionWorkbench';
import { ProductionAccessContext, noraProductionAccess, type ProductionAccess } from './ProductionAccess';
import { TabSelect } from './TabSelect';
import { UnderlineTabs } from './UnderlineTabs';
import { useRefreshState } from '../refreshPosition';

export function IrisProduction({ project, baseUrl, work, onWorkChange, children }: {
  project: string; baseUrl: string; work: string; onWorkChange: (work: string) => void; children?: ReactNode;
}) {
  const [opened, setOpened] = useRefreshState(`${baseUrl}/production/opened`, false);
  const [archiveWork, setArchiveWork] = useRefreshState(`${baseUrl}/production/archive`, '');
  const list = useQuery({ queryKey: ['production-works', baseUrl], queryFn: () => get<FileItem[]>(baseUrl + '/production-works'), refetchInterval: 5000 });
  const hasArchive = list.data?.find(item => item.name === work)?.hasArchive;
  const view = opened && hasArchive && archiveWork === work ? 'archive' : 'current';
  const namespace = view === 'archive' ? `${baseUrl}/archive` : baseUrl;
  const access = useMemo<ProductionAccess>(() => ({ ...noraProductionAccess,
    unitKind: 'work',
    candidateSelection: 'preview',
    storyboard: undefined,
    namespace: () => namespace,
    detail: (_, unit) => `${baseUrl}/works/${unit}/production-detail?view=${view}`,
    scope: (_, unit, scene) => ({ project, episode: unit, scene, label: `${unit}整片`,
      notesUrl: `${baseUrl}/works/${unit}/production-notes${view === 'archive' ? '/archive' : hasArchive ? '?view=current' : ''}`,
      stateKey: `scene/${namespace}/${unit}/${scene}`, readOnly: view === 'archive' }),
    notesSummary: scope => `${baseUrl}/works/${scope.episode}/production-notes/archive`,
    downloads: (_, unit, scene) => `${baseUrl}/works/${unit}/production-downloads?scene=${encodeURIComponent(scene)}&view=${view}`,
    document: (_, path) => `${baseUrl}/document?path=${encodeURIComponent(path)}`,
  }), [baseUrl, hasArchive, namespace, project, view]);
  const select = (value: string | null) => {
    if (value) onWorkChange(value);
    setArchiveWork('');
    setOpened(Boolean(value));
  };
  return <ProductionAccessContext value={access}>
    <Result page loading={list.isPending} error={list.error} retry={list.refetch} retrying={list.isFetching} />
    {list.data && <>
      {opened && <div className="iris-work-toolbar"><button className="link" onClick={() => select(null)}>返回作品列表</button>
        <TabSelect label="切换作品" selected={work} onChange={select} items={list.data.map(item => ({ value: item.name, label: `${item.name} · ${item.title}` }))} />
        {view === 'archive' && <span className="muted">历史制作归档（只读）</span>}
      </div>}
      {opened && hasArchive && <UnderlineTabs label="作品制作入口" selected={view}
        items={[{ value: 'current', label: '现行制作' }, { value: 'archive', label: '历史归档' }]}
        onChange={next => setArchiveWork(next === 'archive' ? work : '')} />}
      <ProductionWorkbench key={view} project={project} items={list.data} selected={opened ? work : null} onSelect={select} revision={0}
        statistics={{ total: list.data.length, completed: 0, notStarted: 0, running: 0 }} />
      {opened && view === 'current' && children}
    </>}
  </ProductionAccessContext>;
}
