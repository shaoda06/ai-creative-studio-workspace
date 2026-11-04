import { useContext, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, RecordData } from './api';
import { FileLink, FileTree, Result } from './components';
import { HeaderControlsContext } from './components/AppShell';
import { AssetMediaCard } from './components/AssetMediaCard';
import { ProjectProduction } from './components/ProjectProduction';
import { ResourceLibrary } from './components/ResourceLibrary';
import { TabNav } from './components/TabNav';
import { useRefreshState } from './refreshPosition';
import './IrisProject.css';

const stages = {
  brief: { label: '需求与参考', description: '查看客户原件、制作简报和参考分析。', groups: [
    ['01-客户资料', '需求与来源'], ['02-参考分析', '制作简报'],
  ] },
  creative: { label: '创意与音画', description: '查看用于分镜和制作的脚本。', groups: [['03-创意脚本', '制作脚本']] },
  storyboard: { label: '分镜与声音', description: '查看逐镜安排和声音设计。', groups: [['04-分镜声音', '分镜与声音制作稿']] },
  assets: { label: '资产准备', description: '查看已采用的素材版本及其依据。', groups: [['05-资产', '资产清单与制作说明']] },
  delivery: { label: '交付与复盘', description: '查阅返修、审阅、交接和完单复盘记录。', groups: [
    ['07-返修交接', '返修与交接'], ['08-完单复盘', '完单复盘'],
  ] },
} as const;
const archiveNames = ['07-交接', '07-审阅', '08-复盘', '归档', '历史制作资料'];

export interface IrisPresentation {
  primary: Record<string, string[]>;
  adopted: { title: string; version: string; media: FileItem }[];
}

const tabs = [
  { value: 'overview', label: '项目概况' },
  { value: 'brief', label: stages.brief.label },
  { value: 'creative', label: stages.creative.label },
  { value: 'storyboard', label: stages.storyboard.label },
  { value: 'assets', label: stages.assets.label },
  { value: 'production', label: '视频制作' },
  { value: 'delivery', label: stages.delivery.label },
  { value: 'resources', label: '项目资源' },
  { value: 'files', label: '全部资料' },
] as const;

export function IrisProject({ name, baseUrl, files, productionSection, presentation, clearPreview }: {
  name: string; baseUrl: string; files: FileItem[]; productionSection?: string; presentation?: IrisPresentation; clearPreview: () => void;
}) {
  const controls = useContext(HeaderControlsContext);
  const [section, setSection] = useRefreshState(`${baseUrl}/section`, 'overview');
  const select = (value: string) => { setSection(value); clearPreview(); window.scrollTo(0, 0); };
  const productionFiles = files.find(item => item.name === productionSection)?.children || [];
  const productionKeys = presentation?.primary['06-视频生产'] || [];
  const productionMain = productionFiles.filter(item => productionKeys.includes(item.key || ''));

  return <>
    {controls && createPortal(<TabNav wide label="项目栏目" items={[...tabs]} selected={section} onChange={select} />, controls)}
    <div key={section} className="iris-project-section">
      {section === 'overview' && <IrisOverview baseUrl={baseUrl} files={files} hasProduction={Boolean(productionSection)} select={select} />}
      {section === 'production' && <>
        {productionSection ? <ProjectProduction project={name} baseUrl={baseUrl} batchIndex /> : <section className="panel iris-production-index">
          <h2>生产批次</h2><p className="muted">本项目暂无视频制作资料。</p>
        </section>}
        {productionMain.length > 0 && <section className="panel"><h3>生产任务记录</h3><FileTree items={productionMain} showStatus={false} /></section>}
        <Supplement title="其他制作资料（含工作稿、旧版和执行记录）" items={productionFiles.filter(item => !productionMain.includes(item))} />
      </>}
      {section === 'resources' && <section className="panel"><ResourceLibrary project={name} baseUrl={baseUrl} /></section>}
      {section === 'files' && <section className="panel"><h2>全部资料</h2><FileTree items={files} showStatus={false} />
        {!files.length && <p className="muted">暂无项目资料。</p>}
      </section>}
      {Object.hasOwn(stages, section) && <IrisStage stage={section as keyof typeof stages} files={files} presentation={presentation} select={select} />}
    </div>
  </>;
}

function IrisOverview({ baseUrl, files, hasProduction, select }: {
  baseUrl: string; files: FileItem[]; hasProduction: boolean; select: (section: string) => void;
}) {
  const status = files.find(item => item.name === '项目状态.md' && item.kind === 'file');
  const query = useQuery({ queryKey: ['document', baseUrl, status?.key, 0],
    queryFn: () => get<RecordData>(`${baseUrl}/document?path=${encodeURIComponent(status!.key!)}`), enabled: Boolean(status) });
  const html: string = query.data?.html || '';
  const progress = useMemo(() => {
    const body = new DOMParser().parseFromString(html, 'text/html').body;
    for (const node of body.children) {
      if (node.tagName === 'H2') break;
      const lines = node.matches('ul, ol') ? Array.from(node.children, item => item.textContent || '') : (node.textContent || '').split('\n');
      for (const line of lines) {
        const current = line.match(/^\s*(?:当前阶段与下一步|状态)[：:]\s*(.+)$/);
        if (current) return current[1];
      }
    }
    return '';
  }, [html]);
  const rootFiles = files.filter(item => item.kind !== 'group');
  const entryFiles = rootFiles.filter(item => ['README.md', '项目状态.md'].includes(item.name));

  return <div className="iris-overview">
    <section className="panel" aria-label="当前进展">
      <p className="iris-eyebrow">IRIS 商业视频</p>
      <h2>当前进展</h2>
      {status && <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />}
      {progress && <p className="iris-project-progress">{progress}</p>}
      {(!status || query.data && !progress) && <p className="muted">{status ? '请查看项目状态文件中的详细记录。' : '暂无项目状态记录。'}</p>}
      <div className="iris-overview-actions">
        {hasProduction && <button type="button" onClick={() => select('production')}>查看视频制作</button>}
        <button type="button" onClick={() => select(hasProduction ? 'delivery' : 'brief')}>{hasProduction ? '查看交付与复盘' : '查看需求与参考'}</button>
      </div>
    </section>
    <section className="panel"><h2>项目入口文件</h2>
      {entryFiles.length ? <FileTree items={entryFiles} showStatus={false} /> : <p className="muted">暂无入口文件。</p>}
      <Supplement title="其他项目文件" items={rootFiles.filter(item => !entryFiles.includes(item) && item.name !== '复盘.md')} />
    </section>
  </div>;
}

function Supplement({ title, items }: { title: string; items: FileItem[] }) {
  return items.length > 0 && <details className="iris-supplement"><summary>{title}</summary>
    <FileTree items={items} showStatus={false} />
  </details>;
}

function IrisStage({ stage, files, presentation, select }: {
  stage: keyof typeof stages; files: FileItem[]; presentation?: IrisPresentation; select: (section: string) => void;
}) {
  const { label, description, groups } = stages[stage];
  const documents = groups.map(([name, title]) => {
    const folder = files.find(item => item.kind === 'group' && item.name === name);
    const items = folder?.children || [];
    const keys = presentation?.primary[name] || [];
    return { name, title, folder, main: items.filter(item => keys.includes(item.key || '')), extra: items.filter(item => !keys.includes(item.key || '')) };
  });
  const archives = stage === 'delivery' ? files.filter(item => archiveNames.includes(item.name) || item.name === '复盘.md') : [];
  const adopted = presentation?.adopted || [];
  return <>
    <div className="section-heading iris-stage-heading">
      <div><h2>{label}</h2><p className="muted">{description}</p></div>
      {stage === 'assets' && <button type="button" onClick={() => select('resources')}>查看项目资源</button>}
    </div>
    <div className="iris-stage-documents">
      {documents.map(({ name, title, main }) => <section className="panel" key={name}>
        <h3>{title}</h3>
        {main.length ? <FileTree items={main} showStatus={false} /> : <p className="muted">暂无可确认的阶段主文件。</p>}
      </section>)}
    </div>
    {stage === 'assets' && <section className="panel"><h3>已采用素材</h3>
      {adopted.length ? <div className="asset-media-grid">{adopted.map(item => item.media.kind === 'image'
        ? <AssetMediaCard key={item.title + item.media.key} title={item.title} item={item} revision={0} formal />
        : <article key={item.title + item.media.key}><h4>{item.title}</h4><FileLink item={item.media} showStatus={false} /></article>)}</div>
        : <p className="muted">现行资产清单中暂无可预览的已采用素材。</p>}
    </section>}
    <Supplement title="其他资料（含工作稿、旧版和执行记录）" items={documents.length === 1
      ? documents[0].extra
      : documents.flatMap(({ folder, extra }) => folder && extra.length ? [{ ...folder, children: extra }] : [])} />
    <Supplement title="历史归档" items={archives} />
  </>;
}
