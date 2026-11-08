import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get, type FileItem } from '../api';
import { Result } from '../components';
import { ProductionWorkbench } from './ProductionWorkbench';
import { ProductionAccessContext, noraProductionAccess, type ProductionAccess } from './ProductionAccess';
import { UnderlineTabs } from './UnderlineTabs';
import { useRefreshState } from '../refreshPosition';

export function IrisProduction({ project, baseUrl, work, onSelect }: {
  project: string; baseUrl: string; work: string | null; onSelect: (work: string | null) => void;
}) {
  const [archiveWork, setArchiveWork] = useRefreshState(`${baseUrl}/production/archive`, '');
  const list = useQuery({ queryKey: ['production-works', baseUrl], queryFn: () => get<FileItem[]>(baseUrl + '/production-works'), refetchInterval: 5000 });
  const hasArchive = list.data?.find(item => item.name === work)?.hasArchive;
  const view = hasArchive && archiveWork === work ? 'archive' : 'current';
  const namespace = view === 'archive' ? `${baseUrl}/archive` : baseUrl;
  const access = useMemo<ProductionAccess>(() => ({ ...noraProductionAccess,
    unitKind: 'work',
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
    setArchiveWork('');
    onSelect(value);
  };
  return <ProductionAccessContext value={access}>
    <Result page loading={list.isPending} error={list.error} retry={list.refetch} retrying={list.isFetching} />
    {list.data && <ProductionWorkbench key={view} project={project} items={list.data} selected={work} onSelect={select} revision={0}
      detailControls={work && hasArchive && <UnderlineTabs label="作品制作入口" selected={view}
        items={[{ value: 'current', label: '现行制作' }, { value: 'archive', label: '历史归档（只读）' }]}
        onChange={next => setArchiveWork(next === 'archive' ? work : '')} />}
      statistics={{ total: list.data.length, completed: 0, notStarted: 0, running: 0 }} />}
  </ProductionAccessContext>;
}
