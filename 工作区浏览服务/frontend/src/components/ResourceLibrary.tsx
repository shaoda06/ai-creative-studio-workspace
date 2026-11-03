import { useContext, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { get, projectUrl } from '../api';
import type { FileItem } from '../api';
import { Dialog, FileLink, PreviewContext, Result } from '../components';
import { AssetMediaCard } from './AssetMediaCard';
import { Pagination } from './Pagination';
import { SearchField } from './SearchField';
import { TabSelect } from './TabSelect';
import { useNotify } from './Notifications';
import './ResourceLibrary.css';

type ResourceRef = { resource_id: string; version: string; file: string; kind?: string };
type Version = ResourceRef & { origin: string; producer: string | null; registered_at: string; parent: ResourceRef | null;
  facts: { bytes: number; width?: number; height?: number; duration_seconds?: number; fps?: number };
  media: FileItem; uses: { heading: string; excerpt: string; document: FileItem }[] };
type Family = { resource_id: string; kind: string; name: string; version_count: number; versions: Version[] };
type Listing = { items: Family[]; total: number; page_size: number };
const origins: Record<string, string> = { generated: '生成结果', process: '处理结果', user_upload: '用户上传', import: '导入素材', legacy: '历史资料' };

export function ResourceLibrary({ project, baseUrl = projectUrl(project), active = true }: { project: string; baseUrl?: string; active?: boolean }) {
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState('');
  const [upload, setUpload] = useState<Family | 'new' | null>(null);
  const client = useQueryClient();
  const listing = useQuery({ queryKey: ['project-resources', baseUrl, search, kind, page],
    queryFn: () => get<Listing>(`${baseUrl}/resources?q=${encodeURIComponent(search)}&kind=${encodeURIComponent(kind)}&page=${page}`), enabled: active });
  const detail = useQuery({ queryKey: ['resource-family', baseUrl, selected],
    queryFn: () => get<Family>(`${baseUrl}/resources/${selected}`), enabled: active && !!selected });
  const preview = useContext(PreviewContext);
  return <div className="resource-library">
    <div className="section-heading"><h2>{selected && detail.data ? detail.data.name : '项目资源'}</h2><div className="resource-library-actions">
      {selected && <button onClick={() => setSelected('')}>返回资源列表</button>}
      <button onClick={() => setUpload(selected && detail.data ? detail.data : 'new')}>{selected ? '导入新版本' : '导入参考素材'}</button>
      <button onClick={() => { void listing.refetch(); if (selected) void detail.refetch(); }}>刷新</button>
    </div></div>
    {!selected ? <>
      <div className="resource-library-actions">
        <SearchField label="搜索项目资源" placeholder="搜索名称或资源编号" value={search} onChange={value => { setSearch(value); setPage(1); }} />
        <TabSelect label="资源类型" selected={kind} onChange={value => { setKind(value); setPage(1); }} items={['', '图片', '视频', '音频'].map(value => ({ value, label: value || '全部类型' }))} />
      </div>
      <Result loading={listing.isPending} error={listing.error} retry={listing.refetch} retrying={listing.isFetching} />
      <div className="resource-family-grid">{listing.data?.items.map(item => <button key={item.resource_id} className="resource-family" onClick={() => setSelected(item.resource_id)}>
        <strong>{item.name}</strong><span>{item.kind} · {item.version_count}个版本</span><small>{item.resource_id}</small>
      </button>)}</div>
      {listing.data && !listing.data.total && <p className="muted">暂无符合条件的资源。</p>}
      {listing.data && <Pagination page={page} total={listing.data.total} pageSize={listing.data.page_size} change={setPage} itemLabel="个资源" />}
    </> : <>
      <Result loading={detail.isPending} error={detail.error} retry={detail.refetch} retrying={detail.isFetching} />
      {detail.data && <><p className="muted">{detail.data.resource_id} · {detail.data.kind} · 共{detail.data.versions.length}个版本</p>
        <div className="resource-version-grid">{detail.data.versions.map(version => <article className="resource-version" key={version.version}>
          {detail.data!.kind === '图片'
            ? <AssetMediaCard title={version.version} item={{ media: version.media, version: version.version }} revision={0} />
            : <><h3>{version.version}</h3><FileLink item={version.media} showStatus={false} /></>}
          <p>{origins[version.origin] || version.origin} · {(version.facts.bytes / 1024 / 1024).toFixed(2)} MiB{version.facts.duration_seconds !== undefined && ` · ${version.facts.duration_seconds.toFixed(2)}秒${version.facts.duration_seconds > 60 ? `（${Math.floor(version.facts.duration_seconds / 60)}分${(version.facts.duration_seconds % 60).toFixed(2)}秒）` : ''}`}</p>
          <p className="muted">登记：{version.registered_at}</p>
          {version.parent && <p>来源版本：<button className="link" onClick={() => preview({ kind: ({ 图片: 'image', 视频: 'video', 音频: 'audio' } as Record<string, string>)[version.parent!.kind || ''] || 'file', key: version.parent!.file,
            name: `${version.parent!.resource_id}@${version.parent!.version}`, url: `${baseUrl}/files/${version.parent!.file.split('/').map(encodeURIComponent).join('/')}` })}>
              {version.parent.resource_id}@{version.parent.version}</button></p>}
          <details><summary>引用记录（{version.uses.length}）</summary>{version.uses.map((use, index) => <div key={index}>
            <FileLink item={use.document} showStatus={false} /><p className="muted">{use.excerpt}</p>
          </div>)}{!version.uses.length && <p className="muted">尚无业务引用记录。</p>}</details>
        </article>)}</div>
      </>}
    </>}
    {upload && <ResourceUpload baseUrl={baseUrl} family={upload === 'new' ? null : upload} close={() => setUpload(null)} done={ref => {
      setUpload(null); setSelected(ref.resource_id); void client.invalidateQueries({ queryKey: ['project-resources', baseUrl] });
      void client.invalidateQueries({ queryKey: ['resource-family', baseUrl] });
    }} />}
  </div>;
}

function ResourceUpload({ baseUrl, family, close, done }: { baseUrl: string; family: Family | null; close: () => void; done: (ref: ResourceRef) => void }) {
  const [name, setName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [parent, setParent] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploadKey, setUploadKey] = useState(() => crypto.randomUUID());
  const notify = useNotify();
  return <Dialog title={family ? `导入新版本 · ${family.name}` : '导入参考素材'} close={close} closeDisabled={busy}>
    <form className="resource-upload-form" onSubmit={async event => {
      event.preventDefault(); if (!file || busy) return;
      const body = new FormData(); body.append('file', file);
      body.append('upload_key', uploadKey);
      if (name.trim()) body.append('title', name.trim());
      if (family) body.append('resource_id', family.resource_id);
      if (parent) body.append('parent_version', parent);
      setBusy(true);
      try {
        const response = await fetch(`${baseUrl}/resources`, { method: 'POST', body });
        const value = await response.json();
        if (!response.ok) throw new Error(value.detail || '素材导入失败');
        notify(family ? '新版本已导入' : '参考素材已导入'); done(value);
      } catch (error) { notify(error instanceof Error ? error.message : String(error), 'error'); }
      finally { setBusy(false); }
    }}>
      {!family && <label>资源名称<input value={name} maxLength={200} onChange={event => setName(event.target.value)} placeholder="留空时使用文件名" disabled={busy} /></label>}
      <label>素材文件<input type="file" required accept={family?.kind === '图片' ? 'image/*' : family?.kind === '视频' ? 'video/*' : family?.kind === '音频' ? 'audio/*' : 'image/*,video/*,audio/*'}
        onChange={event => { setFile(event.target.files?.[0] || null); setUploadKey(crypto.randomUUID()); }} disabled={busy} /></label>
      {family && <label>实际来源版本<TabSelect variant="field" label="实际来源版本" selected={parent} onChange={setParent} disabled={busy}
        items={[{ value: '', label: '未指定／独立提供的新版本' }, ...family.versions.map(version => ({ value: version.version, label: version.version }))]} /></label>}
      <p className="muted">原件按用户上传登记，生成与采用由各自记录说明。</p>
      <div className="resource-library-actions"><button type="submit" disabled={!file || busy}>{busy ? '正在导入…' : '导入'}</button><button type="button" onClick={close} disabled={busy}>取消</button></div>
    </form>
  </Dialog>;
}
