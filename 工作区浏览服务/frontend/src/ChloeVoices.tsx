import { assetPaging, useAssetList } from './chloeAssetPages';
import { Pagination } from './components/Pagination';
import { useChloeScope } from './chloeScope';
import { AudioReferenceCard, formatAudioDuration } from './components/AudioReferenceCard';
import { CheckboxFilters } from './components/CheckboxFilters';
import { SearchField } from './components/SearchField';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { UseQueryResult } from '@tanstack/react-query';
import type { FileItem, WorkspaceSpace } from './api';
import { Preview, PreviewContext, Result, Rich } from './components';
import { PageCheckStatus } from './components/PageCheckStatus';
import { ReferenceMediaCard } from './components/ReferenceMediaCard';
import { useAudioPreview } from './components/AudioPreviewButton';
import { LinkButton } from './components/LinkButton';
import { ChloeAssetRecords } from './ChloeAssetRecords';
import type { AssetSection } from './ChloeAssetRecords';

export interface VoiceCard { id: string; name: string; description: string; models: string[]; type: string; media: FileItem | null; reference: {resource: string; version: string; duration: number | null} | null }
export interface VoiceVersion { purpose: string; resource: string; version: string; adopted: boolean; media: FileItem; duration: number | null; sourceHtml: string; execution: string }
export interface VoiceDetail { id: string; name: string; description: string; type: string; voiceReference: boolean; source: string; tags: string; models: {id: string; name: string}[]; versions: VoiceVersion[]; sections: AssetSection[] }

export function ChloeVoices({ workspaceQuery }: { workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const {spaceId} = useParams();
  const { page } = useChloeScope();
  const navigate = useNavigate();
  const { query, list, changePage, activeTypes, setActiveTypes, search, setSearch } = useAssetList<VoiceCard>('shared-voices', {}, true);
  const data = query.isPlaceholderData ? undefined : query.data;
  const types = [...new Set([...(query.data?.types ?? []), ...activeTypes])];
  const audio = useAudioPreview(true, `${spaceId}/${list}`, 0);
  return <>
    <div className="toolbar">
      <SearchField label="搜索声音" placeholder="按名称或标签搜索" value={search} onChange={setSearch} size="compact" />
    </div>
    <PageCheckStatus queries={[workspaceQuery,query]} />
    <CheckboxFilters options={types} selected={activeTypes} onChange={setActiveTypes} />
    <Result loading={query.isPending || query.isPlaceholderData} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {audio.player}
    {data && (data.items.length ? <div className="reference-media-list">{data.items.map(item=>{
      const name = `${item.id} · ${item.name}`;
      const duration = item.reference ? formatAudioDuration(item.reference.duration) : '暂无试听音频';
      return <ReferenceMediaCard key={item.id} audio item={{kind:'reference',name,media:item.media ? {...item.media,name} : undefined,approvalHtml:`<span>${item.type} · ${duration}</span>`}}
        playing={audio.playingId===item.id} progress={audio.currentId===item.id ? audio.progress : 0}
        onPlay={()=>audio.toggle(item.id,item.media!.url!)} onSelect={()=>navigate(`${page}?${list}&voice=${encodeURIComponent(item.id)}`)} />;
    })}</div> : <p className="muted">暂无声音资料。</p>)}
    {data && <Pagination {...assetPaging(data, changePage)} />}
  </>;
}

export function ChloeVoiceContent({data,spaceId,onOpen,active=true}: {data: VoiceDetail; spaceId: string; onOpen: (file: FileItem)=>void; active?: boolean}) {
  const { page } = useChloeScope();
  const audio=useAudioPreview(active,data.id,0);
  const current=data.versions.filter(item=>item.adopted && item.purpose==='声音参考');
  const others=data.versions.filter(item=>!item.adopted && item.purpose==='声音参考').reverse().sort((a,b)=>b.version.localeCompare(a.version,undefined,{numeric:true}));
  const originals=data.versions.filter(item=>item.purpose==='声音原始参考');
  const voice = data.voiceReference !== false;
  const playable = voice || current.length ? current : originals.filter(item => item.media.kind === 'audio');
  const recording=(item: VoiceVersion)=>{
    const id=`${item.resource}@${item.version}`;
    return <AudioReferenceCard key={id} name={id} duration={item.duration} playing={audio.playingId===id}
      progress={audio.currentId===id ? audio.progress : 0} onPlay={()=>audio.toggle(id,item.media.url!)} />;
  };
  return <div className="chloe-model-detail">
    {audio.player}
    <div className="chloe-look-detail chloe-voice-detail">
      <section className="panel" aria-label="声音信息"><h2>声音信息</h2>
        <dl className="chloe-overview-fields">
          <div><dt>声音名称</dt><dd>{data.name}</dd></div>
          {data.type && <div><dt>声音分类</dt><dd>{data.type}</dd></div>}
          {data.source && <div><dt>来源</dt><dd>{data.source}</dd></div>}
          {data.tags && data.tags !== '无' && <div><dt>标签</dt><dd>{data.tags}</dd></div>}
          <div><dt>声音说明</dt><dd>{data.description}</dd></div>
          {voice && <div><dt>关联模特</dt><dd>{data.models.length ? data.models.map(model=><div key={model.id}><Link to={`${page}?section=assets&asset=models&model=${encodeURIComponent(model.id)}`}>{model.name}</Link></div>) : '无'}</dd></div>}
        </dl>
        <section className="chloe-voice-originals" aria-label="原始参考"><h3>原始参考</h3>{originals.length ? <ul>{originals.map((item,index)=><li key={`${item.resource}@${item.version}`}><LinkButton onClick={()=>onOpen(item.media)}>参考 {index+1} · {item.resource}@{item.version}</LinkButton></li>)}</ul> : <p>无</p>}</section>
      </section>
      <section className="panel" aria-label={voice ? '声音参考' : '试听'}><h2>{voice ? '声音参考' : '试听'}</h2>
        {playable.length ? playable.map(recording) : <p className="muted">{voice ? '尚未采用声音参考。' : '暂无试听音频。'}</p>}
        {others.length>0 && <details><summary>其他版本</summary><div className="chloe-model-versions chloe-voice-versions" aria-label="声音其他版本" tabIndex={0}>{others.map(item=><div key={`${item.resource}@${item.version}`}>
          {recording(item)}<details><summary>来源与执行记录</summary><Rich html={item.sourceHtml} /><p>执行编号：{item.execution}</p></details>
        </div>)}</div></details>}
      </section>
    </div>
    <ChloeAssetRecords sections={data.sections} />
  </div>;
}

export function ChloeVoiceDetail({query,workspaceQuery}: {query: UseQueryResult<VoiceDetail>; workspaceQuery: UseQueryResult<WorkspaceSpace[]>}) {
  const {spaceId}=useParams();
  const { api, page } = useChloeScope();
  const [preview,setPreview]=useState<FileItem | null>(null);
  return <PreviewContext.Provider value={setPreview}>
    <PageCheckStatus queries={[workspaceQuery,query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && <ChloeVoiceContent data={query.data} spaceId={spaceId!} onOpen={setPreview} active={!preview} />}
    {preview && <Preview project="" item={preview} baseUrl={`${api}/shared-voices/${encodeURIComponent(query.data!.id)}`} revision={0} close={()=>setPreview(null)} />}
  </PreviewContext.Provider>;
}
