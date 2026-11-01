import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { get, spaceProjectPath } from '../api';
import type { WorkspaceSpace } from '../api';
import { Result } from '../components';
import { TabSelect } from './TabSelect';

export function ProjectSwitcher() {
  const location = useLocation();
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ['workspaces'],
    queryFn: () => get<WorkspaceSpace[]>('/api/workspaces'), refetchInterval: 5000 });
  return <div className="brand-project-switcher">
    <Link className="brand" to="/">Nora工作台</Link>
    {location.pathname !== '/' && <TabSelect iconOnly label={projects.isPending ? '正在读取项目' : projects.data?.length === 0 ? '暂无项目' : '切换项目'}
      selected={location.pathname} onChange={navigate}
      items={(projects.data || []).flatMap(space => [{ value: `/spaces/${space.id}`, label: space.name }, ...space.projects.map(project => ({ value: spaceProjectPath(space, project.id), label: `${space.name} / ${project.name}` }))])} />}
    <Result loading={false} error={projects.error} retry={projects.refetch} retrying={projects.isFetching} />
  </div>;
}
