import { useChloeScope } from './chloeScope';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { get } from './api';
import type { FileItem } from './api';
import { Preview, PreviewContext, Result } from './components';
import { PageHeader } from './components/PageHeader';
import { Breadcrumbs } from './components/Breadcrumbs';
import { PageCheckStatus } from './components/PageCheckStatus';
import { EntryCard } from './components/EntryCard';
import { TabSelect } from './components/TabSelect';
import { AssetMediaCard } from './components/AssetMediaCard';
import { ReleaseFilmPlayer } from './components/ReleaseFilms';
import { CopyButton } from './components/CopyButton';
import { DownloadButton } from './components/DownloadButton';
import './ChloePublication.css';

type Video = { project: string; id: string; title: string; status: string; finalCount: number };
type Material = { id: string; fields: Record<string, string>; film: FileItem | null; covers: { label: string; media: FileItem | null }[] };
type Publication = { project: string; id: string; title: string; finals: FileItem[]; materials: Material[];
  history: { fields: Record<string, string>; materialId: string | null; url: string | null }[] };
const missing = new Set(['待确定', '待核实', '未取得', '不适用', '无']);

export function ChloePublication({ title, baseUrl, selected, onSelect }: {
  title: string; baseUrl: string; selected: string | null; onSelect: (value: string | null) => void;
}) {
  const { workspacePage, page } = useChloeScope();
  const list = useQuery({ queryKey: ['chloe-publication', baseUrl], queryFn: () => get<Video[]>(`${baseUrl}/publication-videos`), refetchInterval: 5000 });
  return <>
    <PageHeader stacked title={title} actions={<Link to={workspacePage}>返回项目列表</Link>}>
      <Breadcrumbs items={[{ label: '成片与发布', onClick: selected ? () => onSelect(null) : undefined }, ...(selected ? [{ label: selected }] : [])]} />
    </PageHeader>
    {selected ? <PublicationDetail key={`${baseUrl}/${selected}`} baseUrl={baseUrl} project={selected} /> : <section className="panel" aria-label="成片与发布">
      <PageCheckStatus queries={[list]} />
      <Result loading={list.isPending} error={list.error} retry={list.refetch} retrying={list.isFetching} />
      {list.data && (list.data.length ? <div className="chloe-publication-list">{list.data.map(video => <EntryCard key={video.project}
        to={`${page}?section=publication&video=${encodeURIComponent(video.project)}`} title={`${video.id} · ${video.title}`}
        description={`${video.status} · 成片目录内 ${video.finalCount} 个视频`} />)}</div>
        : <p className="muted">暂无视频项目。已有视频的成片和发布资料会显示在这里。</p>)}
    </section>}
  </>;
}

function PublicationDetail({ baseUrl, project }: { baseUrl: string; project: string }) {
  const query = useQuery({ queryKey: ['chloe-publication-detail', baseUrl, project],
    queryFn: () => get<Publication>(`${baseUrl}/publication-videos/${encodeURIComponent(project)}`), refetchInterval: 5000 });
  const [materialId, setMaterialId] = useState('');
  const [preview, setPreview] = useState<FileItem | null>(null);
  const data = query.data;
  const material = data?.materials.find(item => item.id === materialId) || data?.materials.at(-1);
  const used = data?.history.some(item => item.materialId === material?.id);
  const product = material ? ['商品', '款式或SKU', '挂品链接'].filter(field => !missing.has(material.fields[field]))
    .map(field => `${field}：${material.fields[field]}`).join('\n') : '';
  return <PreviewContext value={setPreview}>
    <section className="panel chloe-publication-detail" aria-label="视频发布资料">
      <PageCheckStatus queries={[query]} />
      <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
      {data && <>
        {material ? <>
          <div className="chloe-publication-toolbar">
            <TabSelect label="选择发布资料" items={data.materials.map(item => ({ value: item.id, label: `${item.id} · ${item.fields['平台']} · ${item.fields['账号']}` }))}
              selected={material.id} onChange={setMaterialId} />
            <span>{used ? '已有发布记录引用此资料' : '发布准备资料'}</span>
            <span>发布执行：{material.fields['发布执行']}</span>
          </div>
          <div className="chloe-publication-media">
            <section aria-label="本次成片" className="chloe-publication-film">
              <h2>本次成片</h2>
              {material.film ? <>
                <p className="chloe-publication-text">{material.film.name}</p>
                <ReleaseFilmPlayer key={material.film.url} item={material.film} />
                <DownloadButton url={material.film.url!} filename={material.film.name} label="下载成片" title={material.film.name} />
              </> : <p className="muted">尚未指定本次发布使用的成片。</p>}
            </section>
            <div className="chloe-publication-covers">{material.covers.map(cover => <section key={cover.label} aria-label={cover.label} className="chloe-publication-cover">
              <h2>{cover.label}</h2>
              <AssetMediaCard key={cover.media?.url || cover.label} title={cover.label} hideTitle item={{ media: cover.media, emptyLabel: `尚未准备${cover.label}。` }} revision={0} showVersion={false} showFileActions={false} />
              <DownloadButton url={cover.media?.url || null} filename={cover.media?.name} label={`下载${cover.label}`} title={cover.media?.name || cover.label} />
            </section>)}</div>
          </div>
          <div className="chloe-publication-copy">{['标题', '正文', '话题'].map(field => <section key={field} aria-label={field}>
            <div className="chloe-publication-toolbar"><h2>{field}</h2>
              {!missing.has(material.fields[field]) && <CopyButton text={material.fields[field]} label={`复制${field}`} successMessage={`${field}已复制`} />}
            </div>
            <p className="chloe-publication-text">{material.fields[field]}</p>
          </section>)}</div>
          <section aria-label="挂品信息">
            <div className="chloe-publication-toolbar"><h2>挂品信息</h2>{product && <CopyButton text={product} label="复制挂品信息" />}</div>
            {['商品', '款式或SKU', '挂品链接'].map(field => <div className="chloe-publication-product" key={field}>
              <strong>{field}：</strong><span className="chloe-publication-text">{field === '挂品链接' && /^https?:\/\//.test(material.fields[field])
                ? <a href={material.fields[field]} target="_blank" rel="noopener noreferrer">{material.fields[field]}</a> : material.fields[field]}</span>
              {!missing.has(material.fields[field]) && <CopyButton text={material.fields[field]} label={`复制${field}`} />}
            </div>)}
          </section>
          <p>建议发布时间：{material.fields['建议发布时间']}（具体发布安排以确认结果为准）</p>
        </> : <p className="muted">尚未准备发布资料。进入发布环节后，Agent会结合成片及制作资料准备封面、文案、话题和挂品信息。</p>}
        <details open={!material}>
          <summary>成片目录（{data.finals.length} 个视频）</summary>
          {!data.finals.length ? <p className="muted">成片目录内暂无视频，请将剪映导出的成片放入本视频的成片目录。</p> : <>
            <p className="muted">这里可查看目录文件；本次发布使用的文件以上方发布资料为准。</p>
            <div className="chloe-publication-files">{data.finals.map(file => <div className="chloe-publication-toolbar" key={file.key}>
              <span className="chloe-publication-text">{file.name}</span>
              <button onClick={() => setPreview(file)}>预览成片</button>
              <DownloadButton url={file.url!} filename={file.name} label="下载" title={file.name} />
            </div>)}</div>
          </>}
        </details>
        <section aria-label="发布记录"><h2>发布记录</h2>
          {!data.history.length ? <p className="muted">暂无发布安排或结果。</p> : data.history.map(record => <article key={record.fields['发布编号']} className="chloe-publication-history">
            <h3>{record.fields['发布编号']} · {record.fields['发布进展']}</h3>
            {record.materialId && <button onClick={() => setMaterialId(record.materialId!)}>查看 {record.materialId} 发布资料</button>}
            {['发布方式', '计划发布时间', '实际发布时间', '平台作品ID'].map(field => <p key={field}>{field}：{record.fields[field]}</p>)}
            {record.url && <a href={record.url} target="_blank" rel="noopener noreferrer">打开已发布作品</a>}
          </article>)}
        </section>
      </>}
    </section>
    {preview && <Preview project={project} item={preview} revision={0} close={() => setPreview(null)} />}
  </PreviewContext>;
}
