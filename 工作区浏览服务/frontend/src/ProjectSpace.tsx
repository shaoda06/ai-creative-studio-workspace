import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { get, spaceProjectPath } from './api';
import type { FileItem, WorkspaceSpace } from './api';
import { Dialog, Document, FileTree, Preview, PreviewContext, Result } from './components';
import { EntryCard } from './components/EntryCard';
import { PageHeader } from './components/PageHeader';
import { PageCheckStatus } from './components/PageCheckStatus';

export function ProjectSpace() {
  const { spaceId = '' } = useParams();
  const [indexOpen, setIndexOpen] = useState(false);
  const query = useQuery({ queryKey: ['workspaces'], queryFn: () => get<WorkspaceSpace[]>('/api/workspaces'), refetchInterval: 5000 });
  const space = query.data?.find(item => item.id === spaceId);
  const index = useQuery({ queryKey: ['project-index'], queryFn: () => get<{ title: string; html: string }>('/api/project-index'), enabled: indexOpen });
  return <div className="home">
    <PageHeader title={space?.name || '项目空间'} actions={<Link to="/">返回工作区</Link>} />
    <PageCheckStatus queries={[query]} />
    <Result page loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && !space && <p role="alert">项目空间未登记。</p>}
    {space && <>
      <div className="section-heading"><h2>业务项目</h2>{space.view === 'serial-drama' && <button className="link" onClick={() => setIndexOpen(true)}>查看项目总索引</button>}</div>
      <div className="grid">{space.projects.map((project, index) => <EntryCard key={project.id} to={spaceProjectPath(space, project.id)} title={`${String(index + 1).padStart(2, '0')}-${project.name}`} description="查看项目资料与素材" icon="▤" />)}</div>
      {!space.projects.length && <p className="muted">暂无项目。</p>}
    </>}
    {indexOpen && <Dialog title="项目总索引" close={() => setIndexOpen(false)}><Result loading={index.isPending} error={index.error} retry={index.refetch} retrying={index.isFetching} />{index.data && <Document value={index.data} showOriginal={false} />}</Dialog>}
  </div>;
}

export function FilesProject() {
  const { spaceId = '', name = '' } = useParams();
  const baseUrl = `/api/workspaces/${encodeURIComponent(spaceId)}/projects/${encodeURIComponent(name)}`;
  const [preview, setPreview] = useState<FileItem | null>(null);
  const query = useQuery({ queryKey: ['project-files', spaceId, name], queryFn: () => get<{ name: string; files: FileItem[] }>(baseUrl), refetchInterval: 5000 });
  return <PreviewContext.Provider value={setPreview}><div className="home">
    <PageHeader title={name} actions={<Link to={`/spaces/${spaceId}`}>返回项目空间</Link>} />
    <PageCheckStatus queries={[query]} />
    <Result page loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && <FileTree items={query.data.files} showStatus={false} />}
    {preview && <Preview key={preview.key} project={`${spaceId}/${name}`} baseUrl={baseUrl} item={preview} revision={0} close={() => setPreview(null)} />}
  </div></PreviewContext.Provider>;
}
