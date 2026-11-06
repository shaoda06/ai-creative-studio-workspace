import { useContext } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, RecordData } from './api';
import { Document, FileLink, FileTree, PreviewContext, Result } from './components';
import { HeaderControlsContext } from './components/AppShell';
import { AssetMediaCard } from './components/AssetMediaCard';
import { DownloadButton } from './components/DownloadButton';
import { ProjectProduction } from './components/ProjectProduction';
import { IrisProduction } from './components/IrisProduction';
import { ReleaseFilmPlayer } from './components/ReleaseFilms';
import { ResourceLibrary } from './components/ResourceLibrary';
import { TabNav } from './components/TabNav';
import { TabSelect } from './components/TabSelect';
import { UnderlineTabs } from './components/UnderlineTabs';
import { useRefreshState } from './refreshPosition';
import './IrisProject.css';

const readingStages = {
  creative: { label: '创意与音画', folder: '03-创意脚本' },
  storyboard: { label: '分镜与声音', folder: '04-分镜声音' },
} as const;

const archiveNames = ['07-交接', '07-审阅', '08-复盘', '归档', '历史制作资料'];
const deliveryTabs = [
  { value: 'results', label: '交付成果' },
  { value: 'handoff', label: '返修与交接' },
  { value: 'review', label: '完单复盘' },
] as const;

export interface IrisPresentation {
  primary: Record<string, string[]>;
  adopted: { title: string; version: string; media: FileItem }[];
  brief?: { sources: FileItem[]; archived: FileItem[] };
  stageArchives?: Record<string, FileItem[]>;
  delivery?: {
    status: string; summary: string; archivedHandoff: string | null;
    items: { title: string; type: string; version: string; purpose: string; file: FileItem }[];
  };
}

export interface IrisWork { id: string; name: string; key: string }

interface IrisWorkData { files: FileItem[]; productionSection?: string; irisPresentation: IrisPresentation }

const tabs = [
  { value: 'overview', label: '项目概况' },
  { value: 'brief', label: '需求与参考' },
  { value: 'creative', label: readingStages.creative.label },
  { value: 'storyboard', label: readingStages.storyboard.label },
  { value: 'assets', label: '资产准备' },
  { value: 'production', label: '视频制作' },
  { value: 'delivery', label: '交付与复盘' },
  { value: 'files', label: '全部资料' },
  { value: 'resources', label: '项目资源' },
] as const;

export function IrisProject({ name, baseUrl, files: projectFiles, productionSection: projectProductionSection, presentation: projectPresentation, works, clearPreview }: {
  name: string; baseUrl: string; files: FileItem[]; productionSection?: string; presentation?: IrisPresentation; works?: IrisWork[] | null; clearPreview: () => void;
}) {
  const controls = useContext(HeaderControlsContext);
  const [section, setSection] = useRefreshState(`${baseUrl}/section`, 'overview');
  const [selectedWork, setSelectedWork] = useRefreshState(`${baseUrl}/work`, '');
  const currentWork = works?.find(work => work.id === selectedWork) || works?.[0];
  const workSection = !['overview', 'files', 'resources'].includes(section);
  const workApi = currentWork ? `${baseUrl}/works/${currentWork.id}` : undefined;
  const work = useQuery({ queryKey: ['iris-work', workApi], queryFn: () => get<IrisWorkData>(workApi!),
    enabled: Boolean(workApi && workSection), refetchInterval: 5000 });
  const legacy = works == null;
  const files = legacy ? projectFiles : work.data?.files || [];
  const presentation = legacy ? projectPresentation : work.data?.irisPresentation;
  const productionSection = legacy ? projectProductionSection : work.data?.productionSection;
  const productionApi = legacy ? baseUrl : workApi;
  const select = (value: string) => { setSection(value); clearPreview(); window.scrollTo(0, 0); };
  const productionFiles = files.find(item => item.key === productionSection)?.children || [];
  const productionKeys = presentation?.primary['06-视频生产'] || [];
  const productionMain = productionFiles.filter(item => productionKeys.includes(item.key || ''));

  const productionRecords = <>
        {productionMain.length > 0 && <section className="panel"><h3>生产任务记录</h3><FileTree items={productionMain} showStatus={false} /></section>}
        <Supplement title="其他制作资料（含工作稿、旧版和执行记录）" items={productionFiles.filter(item => !productionMain.includes(item))} />
  </>;

  return <>
    {controls && createPortal(<TabNav wide label="项目栏目" items={[...tabs]} selected={section} onChange={select} />, controls)}
    {workSection && !legacy && section !== 'production' && <div className="iris-work-toolbar">
      <span>当前作品</span><TabSelect label="切换作品" items={(works || []).map(item => ({ value: item.id, label: `${item.id} · ${item.name}` }))}
        selected={currentWork?.id || ''} onChange={value => { setSelectedWork(value); clearPreview(); }} />
    </div>}
    {workSection && !legacy && section !== 'production' && (currentWork
      ? <Result page loading={work.isPending} error={work.error} retry={work.refetch} retrying={work.isFetching} />
      : <section className="panel"><p className="muted">本项目尚未建立作品。</p></section>)}
    {(!workSection || legacy || section === 'production' || work.data) && <div key={`${section}/${section === 'production' ? '' : currentWork?.id || ''}`} className="iris-project-section">
      {section === 'overview' && <IrisOverview baseUrl={baseUrl} files={projectFiles} />}
      {section === 'brief' && <IrisBrief baseUrl={baseUrl} files={files} presentation={presentation} />}
      {Object.hasOwn(readingStages, section) && <IrisReadingStage stage={section as keyof typeof readingStages} baseUrl={baseUrl} files={files} presentation={presentation} />}
      {section === 'assets' && <IrisAssets baseUrl={baseUrl} files={files} presentation={presentation} />}
      {section === 'production' && <>
        {!legacy ? <IrisProduction project={name} baseUrl={baseUrl} work={currentWork?.id || ''} onWorkChange={setSelectedWork}>{productionRecords}</IrisProduction> : productionSection ? <ProjectProduction project={name} baseUrl={productionApi!} batchIndex /> : <section className="panel iris-production-index">
          <h2>生产批次</h2><p className="muted">{legacy ? '本项目暂无视频制作资料。' : '本作品暂无视频制作资料。'}</p>
        </section>}
        {legacy && productionRecords}
      </>}
      {section === 'resources' && <section className="panel"><ResourceLibrary project={name} baseUrl={baseUrl} /></section>}
      {section === 'files' && <section className="panel"><h2>全部资料</h2><FileTree items={projectFiles} showStatus={false} />
        {!projectFiles.length && <p className="muted">暂无项目资料。</p>}
      </section>}
      {section === 'delivery' && <IrisDelivery baseUrl={baseUrl} files={files} presentation={presentation}
        openProduction={productionSection ? () => select('production') : undefined} />}
    </div>}
  </>;
}

const overviewDocuments = [
  { value: 'README.md', label: '项目说明' },
  { value: '项目状态.md', label: '项目状态' },
];

function withoutLeadingTitle(document: RecordData): RecordData {
  return { ...document, html: document.html.replace(/^\s*<h1\b[^>]*>[\s\S]*?<\/h1>/, '') };
}

function IrisOverview({ baseUrl, files }: { baseUrl: string; files: FileItem[] }) {
  const rootFiles = files.filter(item => item.kind !== 'group');
  const available = overviewDocuments.filter(item => rootFiles.some(file => file.kind === 'file' && file.key === item.value));

  return <>
    <section className="panel iris-reading-panel" aria-label="项目概况正文">
      {available.length ? available.map(({ value, label }) => (
        <IrisOverviewDocument key={value} baseUrl={baseUrl} path={value} label={label} />
      )) : <p className="muted">暂无项目说明或状态记录。</p>}
    </section>
    <Supplement title="其他项目文件" items={rootFiles.filter(item => !overviewDocuments.some(doc => doc.value === item.name) && item.name !== '复盘.md')} />
  </>;
}

function IrisOverviewDocument({ baseUrl, path, label }: { baseUrl: string; path: string; label: string }) {
  const query = useQuery({ queryKey: ['document', baseUrl, path, 0],
    queryFn: () => get<RecordData>(`${baseUrl}/document?path=${encodeURIComponent(path)}`),
    select: path === 'README.md' ? withoutLeadingTitle : undefined });

  return <section className="iris-overview-document" aria-label={label}>
    <Result page loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && <Document value={query.data} showOriginal={false} chaptersInitiallyOpen={false} />}
  </section>;
}

const briefDocuments = [
  ['02-参考分析', '制作简报'],
  ['01-客户资料', '需求与来源'],
] as const;

function IrisDocumentReading({ baseUrl, section, label, documents, empty, beforeBody }: {
  baseUrl: string; section: string; label: string; documents: { value: string; label: string }[]; empty: ReactNode; beforeBody?: ReactNode;
}) {
  const [selected, setSelected] = useRefreshState(`${baseUrl}/${section}-document`, '');
  const current = documents.find(doc => doc.value === selected) ?? documents[0];
  const key = current?.value;
  const query = useQuery({ queryKey: ['document', baseUrl, key, 0],
    queryFn: () => get<RecordData>(`${baseUrl}/document?path=${encodeURIComponent(key!)}`), enabled: Boolean(key),
    select: withoutLeadingTitle });

  return <section className="panel iris-reading-panel" aria-label={`${label}正文`}>
    {current ? <div>
      {documents.length > 1
        ? <UnderlineTabs label={`${label}文档`} items={documents} selected={current.value} onChange={setSelected} />
        : <h3>{current.label}</h3>}
      <Result page loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
      {query.data ? <Document key={key} value={query.data} showOriginal={false} chaptersInitiallyOpen={false} beforeBody={beforeBody} />
        : query.isError && beforeBody}
    </div> : <>{empty}{beforeBody}</>}
  </section>;
}

function omitDisplayedFiles(items: FileItem[], displayed: Set<string>): FileItem[] {
  return items.flatMap(item => {
    if (displayed.has(item.key || '')) return [];
    if (!item.children) return [item];
    const children = omitDisplayedFiles(item.children, displayed);
    return children.length ? [{ ...item, children }] : [];
  });
}

function IrisBrief({ baseUrl, files, presentation }: { baseUrl: string; files: FileItem[]; presentation?: IrisPresentation }) {
  const preview = useContext(PreviewContext);
  const available = briefDocuments.flatMap(([folder, label]) => (presentation?.primary[folder] || []).map(key => ({
    value: key,
    label: (presentation?.primary[folder]?.length || 0) > 1 ? key.split('/').at(-1)! : label,
  })));
  const sources = presentation?.brief?.sources || [];
  const archived = presentation?.brief?.archived || [];
  const displayed = new Set([...available.map(doc => doc.value), ...sources.map(item => item.key || '')]);
  const extras = omitDisplayedFiles(files.filter(item => briefDocuments.some(([folder]) => item.name === folder)), displayed);

  const sourceDetails = sources.length > 0 && <details className="iris-brief-attachments">
    <summary>客户原件与参考</summary>
    <div className="iris-brief-sources">{sources.map(item => {
      const name = item.name.replace(/^SRC\d+-/i, '').replace(/(?:-v\d+(?:\.\d+)*)?\.[^.]+$/i, '');
      const source = { ...item, name };
      return item.kind === 'image' ? <button type="button" className="iris-brief-thumbnail" key={item.key} onClick={() => preview(source)}>
        <img src={item.url} alt="" loading="lazy" /><span>{name}</span>
      </button> : <FileLink key={item.key} item={source} showOriginal={false} showStatus={false} />;
    })}</div>
  </details>;

  return <>
    <div className="section-heading iris-stage-heading"><h2>需求与参考</h2></div>
    <IrisDocumentReading baseUrl={baseUrl} section="brief" label="需求与参考" documents={available} beforeBody={sourceDetails}
      empty={archived.length > 0 ? <>
        <p className="muted">本项目的需求与参考资料保存在历史归档中。</p>
        <Supplement title="查看历史需求与参考" items={archived} />
      </> : <p className="muted">暂无可确认的需求记录或制作简报。</p>} />
    <Supplement title="其他资料（含工作稿、旧版和执行记录）" items={extras} />
  </>;
}

function IrisReadingStage({ stage, baseUrl, files, presentation }: {
  stage: keyof typeof readingStages; baseUrl: string; files: FileItem[]; presentation?: IrisPresentation;
}) {
  const { label, folder } = readingStages[stage];
  const keys = presentation?.primary[folder] || [];
  const documents = keys.map(key => ({ value: key, label: key.split('/').at(-1)!.replace(/\.md$/i, '') }));
  const items = files.find(item => item.name === folder)?.children || [];
  const archived = presentation?.stageArchives?.[folder] || [];

  return <>
    <div className="section-heading iris-stage-heading"><h2>{label}</h2></div>
    <IrisDocumentReading baseUrl={baseUrl} section={stage} label={label} documents={documents}
      empty={archived.length > 0 ? <>
        <p className="muted">本项目的{label}资料保存在历史归档中。</p>
        <Supplement title={`查看历史${label}`} items={archived} />
      </> : <p className="muted">暂无可确认的阶段主文件。</p>} />
    <Supplement title="其他资料（含工作稿、旧版和执行记录）" items={omitDisplayedFiles(items, new Set(keys))} />
  </>;
}

function Supplement({ title, items }: { title: string; items: FileItem[] }) {
  return items.length > 0 && <details className="iris-supplement"><summary>{title}</summary>
    <FileTree items={items} showStatus={false} />
  </details>;
}

function IrisAssets({ baseUrl, files, presentation }: { baseUrl: string; files: FileItem[]; presentation?: IrisPresentation }) {
  const folder = '05-资产';
  const current = presentation?.primary[folder] || [];
  const archived = presentation?.stageArchives?.[folder] || [];
  const historical = current.length === 0 && archived.length > 0;
  const keys = historical ? archived.map(item => item.key!) : current;
  const documents = keys.map(key => ({ value: key, label: key.split('/').at(-1)!.replace(/\.md$/i, '') }));
  const items = files.find(item => item.name === folder)?.children || [];
  const adopted = presentation?.adopted || [];
  const [view, setView] = useRefreshState<'media' | 'list'>(`${baseUrl}/asset-view`, historical ? 'list' : 'media');
  const listLabel = historical ? '查看历史资产清单' : '资产清单与制作说明';

  return <>
    <div className="section-heading iris-stage-heading"><h2>资产准备</h2></div>
    <UnderlineTabs label="资产准备视图" items={[
      { value: 'media', label: '已采用素材' }, { value: 'list', label: listLabel },
    ]} selected={view} onChange={setView} />
    {view === 'media' ? <section className="panel" aria-label="已采用素材">
      {adopted.length ? <div className="iris-adopted-grid">{adopted.map(item => item.media.kind === 'image'
        ? <AssetMediaCard key={item.title + item.media.key} title={item.title} item={item} revision={0} formal compact />
        : <article key={item.title + item.media.key}>
          <h3>{item.title}</h3>
          {item.version && <p className="muted">资源版本：{item.version}</p>}
          <FileLink item={item.media} showOriginal={false} showStatus={false} />
        </article>)}</div>
        : <p className="muted">{historical ? '本项目的资产资料保存在历史归档中。' : '现行资产清单中暂无可预览的已采用素材。'}</p>}
    </section> : <>
      {historical && <p className="muted iris-archive-note">以下是归档中的历史资产清单。</p>}
      <IrisDocumentReading baseUrl={baseUrl} section="assets" label={historical ? '历史资产清单' : listLabel} documents={documents}
        empty={<p className="muted">暂无可确认的资产清单。</p>} />
    </>}
    <Supplement title="其他资料（含工作稿、旧版和执行记录）" items={omitDisplayedFiles(items, new Set(current))} />
  </>;
}

function IrisDelivery({ baseUrl, files, presentation, openProduction }: {
  baseUrl: string; files: FileItem[]; presentation?: IrisPresentation; openProduction?: () => void;
}) {
  const [view, setView] = useRefreshState<(typeof deliveryTabs)[number]['value']>(`${baseUrl}/delivery-view`, 'results');
  const delivery = presentation?.delivery;
  const handoffKeys = presentation?.primary['07-返修交接'] || [];
  const reviewKeys = presentation?.primary['08-完单复盘'] || [];
  const archivedHandoff = !handoffKeys.length ? delivery?.archivedHandoff : null;
  const keys = view === 'handoff' ? (archivedHandoff ? [archivedHandoff] : handoffKeys) : reviewKeys;
  const documents = keys.map(key => ({ value: key, label: key.split('/').at(-1)!.replace(/\.md$/i, '') }));
  const excluded = new Set([...handoffKeys, ...reviewKeys, ...(delivery?.items.map(({ file }) => file.key!) || [])]);
  const extras = omitDisplayedFiles(files.filter(item => item.name === '07-返修交接' || item.name === '08-完单复盘'), excluded);
  const archives = files.filter(item => archiveNames.includes(item.name) || item.name === '复盘.md');
  return <>
    <div className="section-heading iris-stage-heading"><h2>交付与复盘</h2></div>
    <UnderlineTabs label="交付与复盘视图" items={[...deliveryTabs]} selected={view} onChange={setView} />
    {view === 'results' ? <section className="panel iris-delivery-results" aria-label="交付成果">
      {delivery?.status && <h3>{delivery.status}</h3>}
      {delivery?.summary && <p className="muted">{delivery.summary}</p>}
      {delivery?.items.length ? delivery.items.map(({ title, type, version, purpose, file }) =>
        <article className="iris-delivery-item" key={file.key}>
          <div className="iris-delivery-item-heading">
            <div><h4>{title}</h4><p className="muted">{[type, version].filter(Boolean).join(' · ')}</p></div>
            {file.jianying
              ? <DownloadButton url={file.jianying.jypack} label="下载剪映草稿包" title={title} pack />
              : <DownloadButton url={file.url!} filename={file.name} label={file.name.toLowerCase().endsWith('.jypack') ? '下载剪映草稿包' : '下载文件'} title={title} />}
          </div>
          {purpose && <p>{purpose}</p>}
          {file.kind === 'video' && <ReleaseFilmPlayer item={file} />}
        </article>) : <>
        <p className="muted">暂无可播放或下载的交付成果。</p>
        {openProduction && <button type="button" onClick={openProduction}>前往视频制作</button>}
      </>}
    </section> : <IrisDocumentReading key={view} baseUrl={baseUrl} section={view} label={view === 'handoff' ? '返修与交接' : '完单复盘'} documents={documents}
      empty={<p className="muted">{view === 'handoff' ? '暂无返修与交接记录。' : '暂无完单复盘，最终交付后可在这里查阅。'}</p>} />}
    <Supplement title="其他资料（含工作稿、旧版和执行记录）" items={extras} />
    <Supplement title="历史归档" items={archives} />
  </>;
}
