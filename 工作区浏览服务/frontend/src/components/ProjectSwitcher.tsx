import { useQuery } from '@tanstack/react-query';
import { Link, matchPath, useLocation, useNavigate } from 'react-router-dom';
import { get, spaceProjectPath } from '../api';
import type { WorkspaceSpace } from '../api';
import { Result } from '../components';
import { TabSelect } from './TabSelect';

export function ProjectSwitcher() {
  const location = useLocation();
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ['workspaces'],
    queryFn: () => get<WorkspaceSpace[]>('/api/workspaces'), refetchInterval: 5000 });
  const scopedProject = matchPath('/spaces/:spaceId/projects/:name/*', location.pathname);
  const noraProject = matchPath('/projects/:name/*', location.pathname);
  const projectSpaceId = scopedProject?.params.spaceId || (noraProject ? 'nora' : undefined);
  const space = projects.data?.find(item => item.id === projectSpaceId);
  const items = projectSpaceId
    ? (space?.projects || []).map(project => ({ value: spaceProjectPath(space!, project.id), label: project.name }))
    : (projects.data || []).map(space => ({ value: `/spaces/${space.id}`, label: space.name }));
  const label = projects.isPending ? (projectSpaceId ? '正在读取项目' : '正在读取工作区')
    : !items.length ? (projectSpaceId ? '暂无项目' : '暂无工作区') : projectSpaceId ? '切换项目' : '切换工作区';
  return <div className="brand-project-switcher">
    <Link className="brand" to="/">AI创作台</Link>
    {location.pathname !== '/' && <TabSelect iconOnly label={label}
      selected={scopedProject?.pathnameBase || noraProject?.pathnameBase || location.pathname} onChange={navigate} items={items} />}
    <Result loading={false} error={projects.error} retry={projects.refetch} retrying={projects.isFetching} />
  </div>;
}
