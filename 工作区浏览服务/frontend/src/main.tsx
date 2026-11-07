import { PageCheckStatus } from './components/PageCheckStatus';
import { Component, lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { createHashRouter, RouterProvider, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { WorkspaceSpace } from './api';
import { ProjectSpace, FilesProject } from './ProjectSpace';
import { Result } from './components';
import { AppShell } from './components/AppShell';
import { EntryCard } from './components/EntryCard';
import { Loading } from './components/Loading';
import './style.css';
const Project = lazy(() => import('./Project'));
const Krea = lazy(() => import('./Krea'));
const History = lazy(() => import('./History'));
const Workflows = lazy(() => import('./Workflows'));
const Prompts = lazy(() => import('./Prompts'));
const Assets = lazy(() => import('./Assets'));
const ChloeVoicesExample = lazy(() => import('./ChloeVoicesExample'));
const ChloeOverviewExample = lazy(() => import('./ChloeOverviewExample'));
const client = new QueryClient({ defaultOptions: { queries: { staleTime: 2000, retry: false, refetchOnWindowFocus: false } } });
class PageBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    return this.state.error ? <div className="error" role="alert"><p>页面无法打开：{this.state.error.message}</p><p>服务代码更新后，已打开的浏览页需要重新载入。</p><button onClick={() => window.location.reload()}>重新打开页面</button></div> : this.props.children;
  }
}
function Home() {
  const spaces = useQuery({ queryKey: ['workspaces'], queryFn: () => get<WorkspaceSpace[]>('/api/workspaces'), refetchInterval: 5000 });
  return <div className="home">
    <PageCheckStatus queries={[spaces]} />
    <div className="section-heading"><h2>共用工具</h2></div>
    <div className="grid"><EntryCard to="/assets/person" title="资产管理" description="人物资料、服装、道具与图片相册" /><EntryCard to="/prompts" title="提示词管理" description="分类整理、编辑与搜索常用提示词" /><EntryCard to="/krea2" title="Krea2 风格库" description="预览、提示词与资源更新" /><EntryCard to="/workflows" title="内置工作流" description="下载画布版与 API 版工作流" /></div>
    <div className="section-heading"><h2>一级项目空间</h2></div>
    <Result page loading={spaces.isPending} error={spaces.error} retry={spaces.refetch} retrying={spaces.isFetching} />
    <div className="grid">{spaces.data?.map(space => <EntryCard key={space.id} to={`/spaces/${space.id}`} title={space.name} description={`${space.projects.length}个业务项目`} icon="▤" />)}</div>
  </div>;
}
function App() {
  return <AppShell><Suspense fallback={<Loading page />}><Routes><Route path="/" element={<Home />} /><Route path="/projects/:name" element={<Project />} /><Route path="/spaces/:spaceId" element={<ProjectSpace />} /><Route path="/spaces/:spaceId/projects/:name" element={<FilesProject />} /><Route path="/examples/chloe/voices" element={<ChloeVoicesExample />} /><Route path="/examples/chloe/overview" element={<ChloeOverviewExample />} /><Route path="/krea2" element={<Krea />} /><Route path="/workflows" element={<Workflows />} /><Route path="/prompts" element={<Prompts />} /><Route path="/assets/:kind?/:id?" element={<Assets />} /><Route path="/history" element={<History />} /><Route path="*" element={<p>入口不存在。<Link to="/">回到工作区</Link></p>} /></Routes></Suspense></AppShell>;
}
const router = createHashRouter([{ path: '*', element: <PageBoundary><App /></PageBoundary> }]);
createRoot(document.getElementById('root')!).render(<PageBoundary><QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider></PageBoundary>);
