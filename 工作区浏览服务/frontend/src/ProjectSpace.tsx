import { useContext, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { get, spaceProjectPath } from './api';
import type { FileItem, WorkspaceSpace } from './api';
import { Dialog, Document, FileTree, Preview, PreviewContext, Result } from './components';
import { EntryCard } from './components/EntryCard';
import { PageHeader } from './components/PageHeader';
import { PageCheckStatus } from './components/PageCheckStatus';
import { HeaderControlsContext } from './components/AppShell';
import { TabNav } from './components/TabNav';
import { TabSelect } from './components/TabSelect';
import { ProjectProduction } from './components/ProjectProduction';
import { ResourceLibrary } from './components/ResourceLibrary';
import { IrisProject } from './IrisProject';
import { ChloeWorkspace } from './ChloeWorkspace';
import type { IrisPresentation, IrisWork } from './IrisProject';
import './ProjectSpace.css';

export function ProjectSpace() {
  const { spaceId = '', context } = useParams();
  const [indexOpen, setIndexOpen] = useState(false);
  const [search, setSearch] = useSearchParams();
  const query = useQuery({ queryKey: ['workspaces'], queryFn: () => get<WorkspaceSpace[]>('/api/workspaces'), refetchInterval: 5000 });
  const space = query.data?.find(item => item.id === spaceId);
  const archived = search.get('archive') === '1';
  const reason = search.get('reason') || '';
  const projects = space?.projects || [];
  const archivedProjects = projects.filter(project => project.archive?.status === 'archived');
  const reasons = [...new Set(archivedProjects.map(project => project.archive!.reason))];
  const visible = projects.map((project, index) => ({ ...project, number: index + 1 }))
    .filter(project => (project.archive?.status === 'archived') === archived)
    .filter(project => !archived || !reason || project.archive?.reason === reason);
  const index = useQuery({ queryKey: ['project-index'], queryFn: () => get<{ title: string; html: string }>('/api/project-index'), enabled: indexOpen });
  return <div className="home">
    {(space?.view !== 'chloe-commerce' || (space.project_layout === 'nested' && !context)) && <PageHeader title={space?.name || '项目空间'} actions={<Link to="/">返回工作区</Link>} />}
    {space?.view !== 'chloe-commerce' && <PageCheckStatus queries={[query]} />}
    <Result page loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && !space && <p role="alert">项目空间未登记。</p>}
    {space && (space.view === 'chloe-commerce' && (space.project_layout !== 'nested' || context) ? <ChloeWorkspace key={`${spaceId}/${context}`} workspaceQuery={query} /> : <>
      <div className="section-heading"><h2>业务项目</h2>{space.view === 'serial-drama' && <button className="link" onClick={() => setIndexOpen(true)}>查看项目总索引</button>}</div>
      <div className="project-archive-filters">
        <TabNav label="项目管理状态" selected={archived ? 'archived' : 'active'}
          items={[{ value: 'active', label: `进行中（${projects.length - archivedProjects.length}）` }, { value: 'archived', label: `已归档（${archivedProjects.length}）` }]}
          onChange={value => setSearch(value === 'archived' ? { archive: '1' } : {})} />
        {archived && <TabSelect label="归档原因" selected={reason}
          items={[{ value: '', label: '全部原因' }, ...reasons.map(value => ({ value, label: value }))]}
          onChange={value => setSearch(value ? { archive: '1', reason: value } : { archive: '1' })} />}
      </div>
      <div className="grid">{visible.map(project => <EntryCard key={project.id} to={spaceProjectPath(space, project.id)} title={`${String(project.number).padStart(2, '0')}-${project.name}`} description={archived ? `已归档 · ${project.archive!.reason}` : '进行中 · 查看项目资料与素材'} icon="▤" />)}</div>
      {!visible.length && <p className="muted">{archived ? reason ? '没有符合此原因的归档项目。' : '暂无已归档项目。' : '暂无进行中的项目。'}</p>}
    </>)}
    {indexOpen && <Dialog title="项目总索引" close={() => setIndexOpen(false)}><Result loading={index.isPending} error={index.error} retry={index.refetch} retrying={index.isFetching} />{index.data && <Document value={index.data} showOriginal={false} />}</Dialog>}
  </div>;
}

export function FilesProject() {
  const { spaceId = '', name = '' } = useParams();
  const controlsRoot = useContext(HeaderControlsContext);
  const [section, setSection] = useState('');
  const baseUrl = `/api/workspaces/${encodeURIComponent(spaceId)}/projects/${encodeURIComponent(name)}`;
  const [preview, setPreview] = useState<FileItem | null>(null);
  const workspaces = useQuery({ queryKey: ['workspaces'], queryFn: () => get<WorkspaceSpace[]>('/api/workspaces'), refetchInterval: 5000 });
  const iris = workspaces.data?.find(space => space.id === spaceId)?.view === 'iris-commercial';
  const query = useQuery({ queryKey: ['project-files', spaceId, name], queryFn: () => get<{ name: string; files: FileItem[]; productionSection?: string; irisPresentation?: IrisPresentation; works?: IrisWork[] | null }>(baseUrl), refetchInterval: 5000 });
  useEffect(() => { setSection(''); setPreview(null); }, [spaceId, name]);
  const files = query.data?.files || [];
  const directories = files.filter(item => item.kind === 'group');
  const directory = directories.find(item => item.name === section);
  const selected = section === '/' || section === '资源' || directory ? section : '';
  const items = selected === '/' ? files : directory ? directory.children || [] : files.filter(item => item.kind !== 'group');
  const tabs = [{ value: '', label: '项目概况' },
    ...directories.filter(item => item.name !== '资源').map(item => ({ value: item.name, label: item.name === query.data?.productionSection ? '视频制作' : item.name.replace(/^\d+[-_、.\s]+/, '') })),
    { value: '资源', label: '项目资源' },
    { value: '/', label: '全部资料' }];
  const returnLink = <Link to={`/spaces/${spaceId}`}>返回项目空间</Link>;
  return <PreviewContext.Provider value={setPreview}><div className="home">
    {(!iris || !query.data) && <PageHeader title={name} actions={returnLink} />}
    <PageCheckStatus queries={[query]} />
    <Result page loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && !workspaces.data && <Result page loading={workspaces.isPending} error={workspaces.error} retry={workspaces.refetch} retrying={workspaces.isFetching} />}
    {query.data && workspaces.data && (iris ? <IrisProject key={baseUrl} name={name} baseUrl={baseUrl} headerActions={returnLink}
      files={files} productionSection={query.data.productionSection} presentation={query.data.irisPresentation} works={query.data.works} clearPreview={() => setPreview(null)} /> : <>
      {controlsRoot && createPortal(<TabNav wide label="项目栏目" items={tabs} selected={selected}
        onChange={value => { setSection(value); setPreview(null); }} />, controlsRoot)}
      {selected === query.data.productionSection && <ProjectProduction key={baseUrl} project={name} baseUrl={baseUrl} />}
      <section className="panel" key={selected} aria-label="项目资料">
        {selected === '资源' ? <ResourceLibrary key={baseUrl} project={name} baseUrl={baseUrl} /> : selected === query.data.productionSection ? <details><summary>制作资料</summary><FileTree items={items} showStatus={false} /></details> : <>
        <FileTree items={items} showStatus={false} />
        {!items.length && <p className="muted">本栏目暂无资料。</p>}
        </>}
      </section>
    </>)}
    {preview && <Preview key={preview.key} project={`${spaceId}/${name}`} baseUrl={baseUrl} item={preview} revision={0} close={() => setPreview(null)} />}
  </div></PreviewContext.Provider>;
}
