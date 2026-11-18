import { useChloeScope } from './chloeScope';
import { chloeVideoStatuses } from './chloeVideoStatuses';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { get } from './api';
import type { FileItem } from './api';
import { Dialog, Preview, PreviewContext, Result } from './components';
import { PageHeader } from './components/PageHeader';
import { Breadcrumbs } from './components/Breadcrumbs';
import { PageCheckStatus } from './components/PageCheckStatus';
import { ProductionEpisodeButton } from './components/ProductionEpisodeButton';
import { ProductionAccessContext } from './components/ProductionAccess';
import { useChloeProductionAccess } from './chloeProductionAccess';
import { TabSelect } from './components/TabSelect';
import { UnderlineTabs } from './components/UnderlineTabs';
import { AssetMediaCard } from './components/AssetMediaCard';
import { CopyButton } from './components/CopyButton';
import { DownloadButton } from './components/DownloadButton';
import { FilePicker } from './components/FilePicker';
import { useNotify } from './components/Notifications';
import './ChloePublication.css';
import './components/EpisodeProduction.css';

type Video = { project: string; id: string; title: string; status: string; finalCount: number };
type Material = { id: string; fields: Record<string, string>; film: FileItem | null; covers: { label: string; media: FileItem | null }[] };
type FinalFile = FileItem & {
  fileTime: string;
  fileTimeSource: 'created' | 'modified';
  videoMetadata: { width: number; height: number; duration: number | null } | null;
};
type Publication = { project: string; id: string; title: string; finals: FinalFile[]; materials: Material[];
  history: { fields: Record<string, string>; materialId: string | null; url: string | null }[] };
const publicationTabs: { value: 'files' | 'release'; label: string }[] = [
  { value: 'files', label: '成片目录' },
  { value: 'release', label: '发布记录' },
];
const informationTabs: { value: 'basic' | 'product'; label: string }[] = [
  { value: 'basic', label: '基础信息' },
  { value: 'product', label: '挂品信息' },
];
const mediaTabs: { value: 'landscape' | 'portrait' | 'video'; label: string }[] = [
  { value: 'landscape', label: '封面（横版）' },
  { value: 'portrait', label: '封面（竖版）' },
  { value: 'video', label: '本次视频' },
];
const missing = new Set(['待确定', '待核实', '未取得', '不适用', '无']);
const fileTimeFormat = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
});
const durationFormat = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 });
const commonAspects = [[1, 1], [5, 4], [4, 3], [3, 2], [16, 10], [16, 9], [2, 1], [21, 9]];

function commonAspect(width: number, height: number) {
  const ratio = Math.max(width, height) / Math.min(width, height);
  const distance = ([w, h]: number[]) => Math.abs(Math.log(ratio / (w / h)));
  const [w, h] = commonAspects.reduce((closest, aspect) => distance(aspect) < distance(closest) ? aspect : closest);
  return width >= height ? `${w}:${h}` : `${h}:${w}`;
}

export function ChloePublication({ title, baseUrl, selected, onSelect }: {
  title: string; baseUrl: string; selected: string | null; onSelect: (value: string | null) => void;
}) {
  const { workspacePage } = useChloeScope();
  const access = useChloeProductionAccess(baseUrl, selected);
  const list = useQuery({ queryKey: ['chloe-publication', baseUrl], queryFn: () => get<Video[]>(`${baseUrl}/publication-videos`), refetchInterval: 5000 });
  return <>
    <PageHeader stacked title={title} actions={<Link to={workspacePage}>返回项目列表</Link>}>
      <Breadcrumbs items={[{ label: '成片与发布', onClick: selected ? () => onSelect(null) : undefined }, ...(selected ? [{ label: selected }] : [])]} />
    </PageHeader>
    {selected ? <PublicationDetail key={`${baseUrl}/${selected}`} baseUrl={baseUrl} project={selected} /> : <section className="panel" aria-label="成片与发布">
      <div className="production-list-heading"><h2>作品列表</h2>
        {list.data && <div className="production-statistics" aria-label="作品发布统计"><span>共 <strong>{list.data.length}</strong> 部</span>
          {chloeVideoStatuses.map(status => <span key={status}>{status} <strong>{list.data.filter(video => video.status === status).length}</strong> 部</span>)}
        </div>}
      </div>
      <PageCheckStatus queries={[list]} />
      <Result loading={list.isPending} error={list.error} retry={list.refetch} retrying={list.isFetching} />
      {list.data && (list.data.length ? <ProductionAccessContext value={access}><div className="episode-grid episode-grid-pairs">{list.data.slice().sort((a, b) => b.id.localeCompare(a.id, undefined, { numeric: true })).map(video => <ProductionEpisodeButton key={video.project}
        project={baseUrl} revision={0} item={{ kind: 'group', name: video.project, title: video.title }} onSelect={onSelect} />)}</div></ProductionAccessContext>
        : <p className="muted">暂无视频项目。已有视频的成片和发布资料会显示在这里。</p>)}
    </section>}
  </>;
}

function PublicationDetail({ baseUrl, project }: { baseUrl: string; project: string }) {
  const [params, setParams] = useSearchParams();
  const tab = params.get('publicationTab') === 'release' ? 'release' : 'files';
  const [materialId, setMaterialId] = useState('');
  const url = `${baseUrl}/publication-videos/${encodeURIComponent(project)}`;
  const query = useQuery({ queryKey: ['chloe-publication-detail', baseUrl, project],
    queryFn: () => get<Publication>(url), refetchInterval: 5000 });
  const client = useQueryClient();
  const refreshFinals = () => Promise.all([
    client.invalidateQueries({ queryKey: ['chloe-publication-detail', baseUrl, project] }),
    client.invalidateQueries({ queryKey: ['chloe-publication', baseUrl] }),
  ]);
  return <section className="panel chloe-publication-detail" aria-label="作品成片与发布">
    <UnderlineTabs label="成片与发布子页" items={publicationTabs} selected={tab} onChange={value => {
      if (value === tab) return;
      const next = new URLSearchParams(params);
      if (value === 'release') next.set('publicationTab', value);
      else next.delete('publicationTab');
      setParams(next);
    }} />
    <PageCheckStatus queries={[query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && (tab === 'files'
      ? <FinalDirectory files={query.data.finals} uploadUrl={`${url}/files`} project={project} refresh={refreshFinals} />
      : <PublicationRelease data={query.data} project={project} materialId={materialId} onMaterialChange={setMaterialId} />)}
  </section>;
}

function PublicationRelease({ data, project, materialId, onMaterialChange }: {
  data: Publication; project: string; materialId: string; onMaterialChange: (value: string) => void;
}) {
  const [preview, setPreview] = useState<FileItem | null>(null);
  const [informationTab, setInformationTab] = useState<'basic' | 'product'>('basic');
  const [mediaTab, setMediaTab] = useState<'landscape' | 'portrait' | 'video'>('landscape');
  const material = data.materials.find(item => item.id === materialId) || data.materials.at(-1);
  const videoTab = mediaTab === 'video';
  const mediaLabel = videoTab ? '本次视频' : mediaTab === 'landscape' ? '横版封面' : '竖版封面';
  const media = videoTab ? material?.film : material?.covers.find(item => item.label === mediaLabel)?.media;
  const used = data.history.some(item => item.materialId === material?.id);
  const product = material ? ['商品', '款式或SKU', '挂品链接'].filter(field => !missing.has(material.fields[field]))
    .map(field => `${field}：${material.fields[field]}`).join('\n') : '';
  return <PreviewContext value={setPreview}>
    {material ? <>
      <div className="chloe-publication-toolbar">
        <TabSelect label="选择发布资料" items={data.materials.map(item => ({ value: item.id, label: `${item.id} · ${item.fields['平台']} · ${item.fields['账号']}` }))}
          selected={material.id} onChange={onMaterialChange} />
        <span>{used ? '已有发布记录引用此资料' : '发布准备资料'}</span>
        <span>发布执行：{material.fields['发布执行']}</span>
      </div>
      <div className="chloe-publication-preparation">
        <section aria-label="发布文字资料" className="chloe-publication-column">
          <UnderlineTabs label="发布信息分类" items={informationTabs} selected={informationTab} onChange={setInformationTab} />
          {informationTab === 'basic' ? <div className="chloe-publication-copy">
            {['标题', '正文', '话题'].map(field => <section key={field} aria-label={field}>
              <div className="chloe-publication-toolbar"><h2>{field}</h2>
                {!missing.has(material.fields[field]) && <CopyButton text={material.fields[field]} label="复制" ariaLabel={`复制${field}`} appearance="link" successMessage={`${field}已复制`} />}
              </div>
              <p className="chloe-publication-text">{material.fields[field]}</p>
            </section>)}
          </div> : <section aria-label="挂品信息">
            {product && <CopyButton text={product} label="复制挂品信息" />}
            {['商品', '款式或SKU', '挂品链接'].map(field => <div className="chloe-publication-product" key={field}>
              <strong>{field}：</strong><span className="chloe-publication-text">{field === '挂品链接' && /^https?:\/\//.test(material.fields[field])
                ? <a href={material.fields[field]} target="_blank" rel="noopener noreferrer">{material.fields[field]}</a> : material.fields[field]}</span>
              {!missing.has(material.fields[field]) && <CopyButton text={material.fields[field]} label={`复制${field}`} />}
            </div>)}
          </section>}
        </section>
        <section aria-label="发布媒体" className="chloe-publication-column chloe-publication-media-column">
          <UnderlineTabs label="发布媒体分类" items={mediaTabs} selected={mediaTab} onChange={setMediaTab} />
          <section aria-label={mediaLabel} className="chloe-publication-preview">
            <AssetMediaCard key={media?.url || mediaLabel} title={mediaLabel} hideTitle previewLayout="fill" revision={0}
              item={{ media: media || undefined, emptyLabel: videoTab ? '尚未指定本次发布使用的成片。' : `尚未准备${mediaLabel}。` }}
              showVersion={false} showFileActions={false} />
          </section>
        </section>
      </div>
      <p>建议发布时间：{material.fields['建议发布时间']}（具体发布安排以确认结果为准）</p>
    </> : <p className="muted">暂无发布准备资料。</p>}
    <section aria-label="发布记录"><h2>发布记录</h2>
      {!data.history.length ? <p className="muted">暂无发布安排或结果。</p> : data.history.map(record => <article key={record.fields['发布编号']} className="chloe-publication-history">
        <h3>{record.fields['发布编号']} · {record.fields['发布进展']}</h3>
        {record.materialId && <button onClick={() => onMaterialChange(record.materialId!)}>查看 {record.materialId} 发布资料</button>}
        {['发布方式', '计划发布时间', '实际发布时间', '平台作品ID'].map(field => <p key={field}>{field}：{record.fields[field]}</p>)}
        {record.url && <a href={record.url} target="_blank" rel="noopener noreferrer">打开已发布作品</a>}
      </article>)}
    </section>
    {preview && <Preview project={project} item={preview} revision={0} close={() => setPreview(null)} />}
  </PreviewContext>;
}

function FinalDirectory({ files, uploadUrl, project, refresh }: {
  files: FinalFile[]; uploadUrl: string; project: string; refresh: () => Promise<unknown>;
}) {
  const [preview, setPreview] = useState<FileItem | null>(null);
  const [remove, setRemove] = useState<FileItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [upload, setUpload] = useState(false);
  const notify = useNotify();
  async function deleteFile() {
    setDeleting(true);
    try {
      const response = await fetch(remove!.url!, { method: 'DELETE' });
      if (!response.ok) throw new Error((await response.json()).detail || '删除失败');
      setRemove(null);
      await refresh();
      notify('已删除成片');
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error), 'error');
    } finally { setDeleting(false); }
  }
  return <>
    <section aria-label="成片目录">
      <div className="chloe-publication-toolbar chloe-publication-directory-heading">
        <h2>成片目录</h2><button type="button" onClick={() => setUpload(true)}>上传</button>
      </div>
      <div className="prose"><div className="table-scroll"><table className="chloe-publication-files" aria-label="成片文件">
        <colgroup><col style={{ width: 170 }} /><col /><col style={{ width: 88 }} /><col style={{ width: 168 }} /><col style={{ width: 88 }} /><col style={{ width: 324 }} /></colgroup>
        <thead><tr><th scope="col" title="优先显示文件创建时间，无法取得时显示修改时间">文件时间</th><th scope="col">文件名</th>
          <th scope="col">文件类型</th><th scope="col">分辨率与比例</th><th scope="col">时长</th><th scope="col">操作</th></tr></thead>
        <tbody>{files.length ? files.map(file => {
          const metadata = file.videoMetadata;
          const extensionAt = file.name.lastIndexOf('.');
          return <tr key={file.key}>
            <td><time dateTime={file.fileTime} title={file.fileTimeSource === 'created' ? '文件创建时间' : '文件修改时间'}>
              {fileTimeFormat.format(new Date(file.fileTime))}
            </time></td>
            <td className="chloe-publication-file-name"><FinalName name={file.name.slice(0, extensionAt)} url={file.url!} refresh={refresh} /></td>
            <td>{file.name.slice(extensionAt)}</td>
            <td>{metadata && metadata.width > 0 && metadata.height > 0
              ? <>{metadata.width} × {metadata.height} <span className="muted">· {commonAspect(metadata.width, metadata.height)}</span></>
              : <span title="无法读取视频分辨率">—</span>}</td>
            <td>{metadata?.duration != null ? `${durationFormat.format(metadata.duration)} 秒` : <span title="无法读取视频时长">—</span>}</td>
            <td><div className="chloe-publication-toolbar chloe-publication-file-actions">
              <button onClick={() => setPreview(file)}>预览成片</button>
              <DownloadButton url={file.url!} filename={file.name} label="下载" title={file.name} />
              <button className="danger-button" onClick={() => setRemove(file)}>删除</button>
            </div></td>
          </tr>;
        }) : <tr><td colSpan={6}>暂无成片</td></tr>}</tbody>
      </table></div></div>
    </section>
    {upload && <FinalUpload url={uploadUrl}
      close={() => setUpload(false)} done={async () => { await refresh(); setUpload(false); }} />}
    {remove && <Dialog title="删除成片" size="compact" closeDisabled={deleting} close={() => setRemove(null)}>
      <p>确定删除“{remove.name}”吗？文件将从磁盘删除，无法撤销。</p>
      <div className="chloe-publication-toolbar"><button disabled={deleting} onClick={() => setRemove(null)}>取消</button>
        <button className="danger-button" disabled={deleting} onClick={() => void deleteFile()}>{deleting ? '删除中…' : '确认删除'}</button></div>
    </Dialog>}
    {preview && <Preview project={project} item={preview} revision={0} close={() => setPreview(null)} />}
  </>;
}

function FinalName({ name, url, refresh }: { name: string; url: string; refresh: () => Promise<unknown> }) {
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  function cancel() {
    setDraft(null);
    setError('');
  }

  if (draft === null) return <div className="chloe-publication-name-row">
    <span className="chloe-publication-text">{name}</span>
    <button type="button" className="chloe-publication-name-action" aria-label="重命名" title="重命名"
      onClick={() => setDraft(name)}>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="m14 5 5 5M5 19l4-.8L20 7.2 16.8 4 5.8 15Z" />
      </svg>
    </button>
  </div>;

  return <form onSubmit={async event => {
    event.preventDefault();
    if (saving || !draft.trim()) return;
    if (draft.trim() === name) { cancel(); return; }
    setSaving(true);
    setError('');
    try {
      const response = await fetch(url, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: draft.trim() }),
      });
      if (!response.ok) throw new Error((await response.json()).detail || '成片重命名失败');
      await refresh();
      cancel();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setSaving(false);
    }
  }}>
    <div className="chloe-publication-name-row">
      <input type="text" aria-label="新文件名" aria-invalid={!!error} autoFocus value={draft} disabled={saving}
        onFocus={event => event.currentTarget.select()} onChange={event => { setDraft(event.target.value); setError(''); }}
        onKeyDown={event => {
          if (event.key === 'Enter' && event.nativeEvent.isComposing) event.preventDefault();
          if (event.key === 'Escape' && !event.nativeEvent.isComposing) { event.preventDefault(); cancel(); }
        }} />
      <button type="submit" className="chloe-publication-name-action" aria-label="保存文件名" title="保存文件名"
        disabled={saving || !draft.trim()}>✓</button>
      <button type="button" className="chloe-publication-name-action" aria-label="取消重命名" title="取消重命名"
        disabled={saving} onClick={cancel}>×</button>
    </div>
    {error && <small className="chloe-publication-name-error" role="alert">{error}</small>}
  </form>;
}

function FinalUpload({ url, close, done }: { url: string; close: () => void; done: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const notify = useNotify();
  return <Dialog title="上传成片" size="compact" close={close} closeDisabled={busy}>
    <form className="chloe-publication-upload-form" onSubmit={async event => {
      event.preventDefault();
      if (!file || busy) return;
      const body = new FormData();
      body.append('file', file);
      setBusy(true);
      try {
        const response = await fetch(url, { method: 'POST', body });
        if (!response.ok) throw new Error((await response.json()).detail || '成片上传失败');
        await done();
        notify('成片已上传');
      } catch (error) {
        notify(error instanceof Error ? error.message : String(error), 'error');
      } finally {
        setBusy(false);
      }
    }}>
      <FilePicker label="视频文件" chooseLabel="选择视频" accept="video/*,.mkv,.avi" fileName={file?.name} onSelect={setFile} disabled={busy} />
      <div className="chloe-publication-toolbar chloe-publication-upload-actions">
        <button type="submit" disabled={!file || busy}>{busy ? '上传中…' : '上传'}</button>
        <button type="button" disabled={busy} onClick={close}>取消</button>
      </div>
    </form>
  </Dialog>;
}
