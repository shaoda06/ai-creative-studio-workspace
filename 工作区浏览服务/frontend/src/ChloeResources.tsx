import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, WorkspaceSpace } from './api';
import { Dialog, FileLink, Preview, PreviewContext, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { AudioReferenceCard } from './components/AudioReferenceCard';
import { useAudioPreview } from './components/AudioPreviewButton';
import { FileActions } from './components/FileActions';
import { LinkButton } from './components/LinkButton';
import { Pagination } from './components/Pagination';
import { SearchField } from './components/SearchField';
import { TabSelect } from './components/TabSelect';
import { UnderlineTabs } from './components/UnderlineTabs';
import { PageCheckStatus } from './components/PageCheckStatus';
import { useChloeScope } from './chloeScope';
import './chloe-resources.css';

type ResourceVersion = {
  key: string; resource_id: string; version: string; kind: string; name: string; title: string;
  owner: string; owner_label: string; file: string; registered_at: string; origin: string;
  facts: { width?: number; height?: number; duration_seconds?: number; bytes: number; fps?: number };
  source_range?: { start_seconds?: number; end_seconds?: number }; media: FileItem | null;
};
type ResourceList = { items: ResourceVersion[]; owners: {value:string;label:string}[]; total:number; page:number; page_size:number };
type ResourceDetail = ResourceVersion & { versions: ResourceVersion[]; parent_entry: ResourceVersion | null;
  producer_path: string | null; producer_file: string | null; uses: {heading:string;path:string;excerpt:string;to:string|null}[] };
const origins: Record<string,string> = {generated:'生成结果',process:'处理结果',user_upload:'用户上传',import:'导入素材',legacy:'历史资料'};
const label = (item: ResourceVersion) => `${item.resource_id}@${item.version}`;
const duration = (seconds: number) => `${seconds}秒${seconds>60 ? `（${Math.floor(seconds/60)}分${Math.round(seconds%60*100)/100}秒）` : ''}`;

export function ChloeResources({workspaceQuery}: {workspaceQuery:UseQueryResult<WorkspaceSpace[]>}) {
  const {api} = useChloeScope();
  const base = api+'/resource-library';
  const [kind,setKind] = useState('');
  const [owner,setOwner] = useState('');
  const [search,setSearch] = useState('');
  const [page,setPage] = useState(1);
  const [selected,setSelected] = useState<ResourceVersion|null>(null);
  const [preview,setPreview] = useState<FileItem|null>(null);
  const listing = useQuery({queryKey:['chloe-resources',api,kind,owner,search,page],
    queryFn:()=>get<ResourceList>(`${base}?${new URLSearchParams({kind,owner,q:search,page:String(page)})}`),refetchInterval:5000});
  const detail = useQuery({queryKey:['chloe-resource-detail',api,selected?.key],enabled:!!selected,
    queryFn:()=>get<ResourceDetail>(`${base}/detail?${new URLSearchParams({owner:selected!.owner,resource_id:selected!.resource_id,version:selected!.version})}`)});
  const audio = useAudioPreview(!preview && !selected, `${kind}/${owner}/${search}/${page}`,0);
  const document = (path:string,name:string):FileItem => ({kind:path.endsWith('.md')?'markdown':'json',key:path,name,url:base+'/files/'+path.split('/').map(encodeURIComponent).join('/')});
  return <PreviewContext.Provider value={setPreview}>
    <PageCheckStatus queries={[workspaceQuery,listing,...(selected?[detail]:[])]} />
    {audio.player}
    <section className="panel" aria-label="资源库">
      <UnderlineTabs label="资源类型" items={['','图片','视频','音频'].map(value=>({value,label:value||'全部'}))} selected={kind} onChange={value=>{setKind(value);setPage(1);}} />
      <div className="toolbar">
        <TabSelect label="资源归属" selected={owner} onChange={value=>{setOwner(value);setPage(1);}} items={[{value:'',label:'全部归属'},...(listing.data?.owners||[])]} />
        <SearchField label="搜索资源" placeholder="搜索文件名或资源编号" value={search} onChange={value=>{setSearch(value);setPage(1);}} />
        {listing.data && <span className="muted">共 {listing.data.total} 个版本</span>}
      </div>
      <Result loading={listing.isPending} error={listing.error} retry={listing.refetch} retrying={listing.isFetching} />
      {listing.data && <>
        <div className="chloe-resource-grid">{listing.data.items.map(item=>{
          const description = <div className="chloe-resource-description">
            <p>{label(item)}</p><p className="muted">{item.owner_label}</p>
            <p className="muted">{[item.facts.width && item.facts.height ? `${item.facts.width} × ${item.facts.height}` : '',item.kind!=='图片' && item.facts.duration_seconds!==undefined ? duration(item.facts.duration_seconds) : ''].filter(Boolean).join(' · ')}</p>
            <div className="chloe-resource-actions"><LinkButton onClick={()=>setSelected(item)}>详情</LinkButton><FileActions url={item.media?.url} downloadOnly /></div>
          </div>;
          return item.kind==='图片' ? <div className="chloe-resource-item" key={item.key}>
            <AssetMediaCard title={item.name} item={{media:item.media||undefined,emptyLabel:'原文件缺失'}} revision={0} compact showVersion={false}>{description}</AssetMediaCard>
          </div> : <article className={`chloe-resource-item${item.kind==='音频'?' is-audio':''}`} key={item.key} aria-label={item.name}>
            {item.kind==='音频' && item.media ?
              <AudioReferenceCard name={item.name} duration={item.facts.duration_seconds??null} playing={audio.playingId===item.key} progress={audio.currentId===item.key?audio.progress:0} onPlay={()=>audio.toggle(item.key,item.media!.url!)} /> :
              <div><h3>{item.name}</h3>{item.media ? <button className="cover" aria-label={`播放 ${item.name}`} onClick={()=>setPreview(item.media!)}>
                <video className="chloe-resource-video" src={item.media.url} preload="metadata" muted playsInline aria-hidden="true" />
              </button> : <p className="muted">原文件缺失</p>}</div>}
            {description}
          </article>;
        })}</div>
        {!listing.data.total && <p className="muted">暂无符合条件的资源。</p>}
        <Pagination page={listing.data.page} total={listing.data.total} pageSize={listing.data.page_size} change={setPage} itemLabel="个版本" />
      </>}
    </section>
    {selected && <Dialog title={`资源详情 · ${label(selected)}`} close={()=>setSelected(null)}>
      <Result loading={detail.isPending} error={detail.error} retry={detail.refetch} retrying={detail.isFetching} />
      {detail.data && <div className="chloe-resource-detail">
        <h3>{detail.data.name}</h3>
        {detail.data.media ? <LinkButton onClick={()=>setPreview(detail.data!.media!)}>预览</LinkButton> : <p className="muted">原文件缺失</p>}
        <FileActions url={detail.data.media?.url} downloadOnly />
        <dl className="chloe-resource-fields">
          <div><dt>归属</dt><dd>{detail.data.owner_label}</dd></div>
          <div><dt>文件路径</dt><dd>{detail.data.file}</dd></div>
          <div><dt>登记时间</dt><dd>{detail.data.registered_at}</dd></div>
          <div><dt>来源</dt><dd>{origins[detail.data.origin]||detail.data.origin}</dd></div>
          <div><dt>文件大小</dt><dd>{(detail.data.facts.bytes/1024/1024).toFixed(2)} MiB</dd></div>
          {detail.data.facts.width && <div><dt>实际尺寸</dt><dd>{detail.data.facts.width} × {detail.data.facts.height}</dd></div>}
          {detail.data.facts.duration_seconds!==undefined && <div><dt>时长</dt><dd>{duration(detail.data.facts.duration_seconds)}</dd></div>}
          {detail.data.facts.fps!==undefined && <div><dt>帧率</dt><dd>{detail.data.facts.fps} fps</dd></div>}
        </dl>
        <TabSelect label="资源版本" selected={detail.data.version} items={detail.data.versions.map(v=>({value:v.version,label:`${v.version} · ${v.name}`}))} onChange={version=>setSelected(detail.data!.versions.find(v=>v.version===version)!)} />
        <h3>来源与制作记录</h3>
        {detail.data.parent_entry && <p>来源版本：<LinkButton onClick={()=>setSelected(detail.data!.parent_entry!)}>{label(detail.data.parent_entry)}</LinkButton></p>}
        {detail.data.producer_path && <p className="muted">{detail.data.producer_path}</p>}
        {detail.data.producer_file ? <FileLink item={document(detail.data.producer_file,'查看生成／处理记录')} showOriginal={false} showStatus={false} /> : <p className="muted">{detail.data.producer_path ? '原记录文件缺失。' : '未登记生成或处理记录。'}</p>}
        <h3>已记录的关联与引用（{detail.data.uses.length}）</h3>
        {detail.data.uses.map((use,index)=><div key={use.path+index} className="chloe-resource-use">
          <FileLink item={document(use.path,use.heading)} showOriginal={false} showStatus={false} />
          <p className="muted">{use.excerpt}</p>
          {use.to && <Link to={use.to} onClick={()=>setSelected(null)}>进入对应资产／作品</Link>}
        </div>)}
        {!detail.data.uses.length && <p className="muted">未发现已记录的引用，不代表该版本未使用。</p>}
      </div>}
    </Dialog>}
    {preview && <Preview project="" item={preview} baseUrl={base} revision={0} close={()=>setPreview(null)} />}
  </PreviewContext.Provider>;
}
