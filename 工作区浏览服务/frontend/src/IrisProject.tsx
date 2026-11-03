import { useContext, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, RecordData } from './api';
import { FileTree, Result } from './components';
import { HeaderControlsContext } from './components/AppShell';
import { ProjectProduction } from './components/ProjectProduction';
import { ResourceLibrary } from './components/ResourceLibrary';
import { TabNav } from './components/TabNav';
import { useRefreshState } from './refreshPosition';
import './IrisProject.css';

const stages = {
  brief: { label: '需求与参考', description: '查看客户原件、制作简报和参考分析。', groups: [
    ['01-客户资料', '客户需求与原件'], ['02-参考分析', '制作简报与参考分析'],
  ] },
  creative: { label: '创意与音画', description: '查看创意方向、内容主线和音画脚本。', groups: [['03-创意脚本', '创意方案与脚本']] },
  storyboard: { label: '分镜与声音', description: '查看逐镜安排、导演表和声音设计。', groups: [['04-分镜声音', '分镜与声音制作资料']] },
  assets: { label: '资产准备', description: '查看素材要求、资产清单和采用记录。', groups: [['05-资产', '资产清单与制作资料']] },
  delivery: { label: '交付与复盘', description: '查阅返修、审阅、交接和完单复盘记录。', groups: [
    ['07-返修交接', '返修与交接'], ['08-完单复盘', '完单复盘'],
    ['07-交接', '旧交接资料'], ['07-审阅', '旧审阅资料'], ['08-复盘', '旧复盘资料'],
    ['归档', '归档资料'], ['历史制作资料', '历史制作资料'],
  ] },
} as const;

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

export function IrisProject({ name, baseUrl, files, productionSection, clearPreview }: {
  name: string; baseUrl: string; files: FileItem[]; productionSection?: string; clearPreview: () => void;
}) {
  const controls = useContext(HeaderControlsContext);
  const [section, setSection] = useRefreshState(`${baseUrl}/section`, 'overview');
  const select = (value: string) => { setSection(value); clearPreview(); window.scrollTo(0, 0); };
  const productionFiles = files.find(item => item.name === productionSection)?.children || [];

  return <>
    {controls && createPortal(<TabNav wide label="项目栏目" items={[...tabs]} selected={section} onChange={select} />, controls)}
    <div key={section} className="iris-project-section">
      {section === 'overview' && <IrisOverview baseUrl={baseUrl} files={files} hasProduction={Boolean(productionSection)} select={select} />}
      {section === 'production' && <>
        {productionSection ? <ProjectProduction project={name} baseUrl={baseUrl} batchIndex /> : <section className="panel iris-production-index">
          <h2>生产批次</h2><p className="muted">本项目暂无视频制作资料。</p>
        </section>}
        {productionFiles.length > 0 && <section className="panel" aria-label="制作资料">
          <details><summary>制作资料</summary><FileTree items={productionFiles} showStatus={false} /></details>
        </section>}
      </>}
      {section === 'resources' && <section className="panel"><ResourceLibrary project={name} baseUrl={baseUrl} /></section>}
      {section === 'files' && <section className="panel"><h2>全部资料</h2><FileTree items={files} showStatus={false} />
        {!files.length && <p className="muted">暂无项目资料。</p>}
      </section>}
      {Object.hasOwn(stages, section) && <IrisStage stage={section as keyof typeof stages} files={files} select={select} />}
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
  const entryFiles = files.filter(item => item.kind !== 'group' && item.name !== '复盘.md');

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
    </section>
  </div>;
}

function IrisStage({ stage, files, select }: {
  stage: keyof typeof stages; files: FileItem[]; select: (section: string) => void;
}) {
  const { label, description, groups } = stages[stage];
  const documents = groups.flatMap(([name, title]) => {
    const folder = files.find(item => item.kind === 'group' && item.name === name);
    return folder?.children?.length ? [{ name, title, items: folder.children }] : [];
  });
  const retrospective = stage === 'delivery' ? files.filter(item => item.kind === 'file' && item.name === '复盘.md') : [];
  return <>
    <div className="section-heading iris-stage-heading">
      <div><h2>{label}</h2><p className="muted">{description}</p></div>
      {stage === 'assets' && <button type="button" onClick={() => select('resources')}>查看项目资源</button>}
    </div>
    <div className="iris-stage-documents">
      {documents.map(({ name, title, items }) => <section className="panel" key={name}><h3>{title}</h3><FileTree items={items} showStatus={false} /></section>)}
      {retrospective.length > 0 && <section className="panel"><h3>完单复盘记录</h3><FileTree items={retrospective} showStatus={false} /></section>}
    </div>
    {!documents.length && !retrospective.length && <section className="panel"><p className="muted">本项目暂无{label}资料。</p></section>}
  </>;
}
