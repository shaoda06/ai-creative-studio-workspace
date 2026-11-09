import { useChloeScope } from './chloeScope';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, WorkspaceSpace } from './api';
import { Result, PreviewContext, Preview, Rich } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { FullscreenImage } from './components/FullscreenImage';
import { UnderlineTabs } from './components/UnderlineTabs';
import { LinkButton } from './components/LinkButton';
import { PageCheckStatus } from './components/PageCheckStatus';
import { ChloeAssetRecords } from './ChloeAssetRecords';
import type { AssetDetail } from './ChloeModelDetail';

interface ReferenceAssetCard { id: string; name: string; media: FileItem | null }
export interface ReferenceAssetDetail extends AssetDetail { description: string }
export const referenceAssetKinds = {
  hair: {label:'发型', parameter:'hair', endpoint:'shared-hair', ratio:'16:9'},
  clothing: {label:'服装', parameter:'clothing', endpoint:'shared-clothing', ratio:'4:3'},
  scenes: {label:'场景', parameter:'scene', endpoint:'shared-scenes', ratio:'9:16'},
};
export type ReferenceAssetKind = keyof typeof referenceAssetKinds;

export function ChloeReferenceAssets({ kind, workspaceQuery }: { kind: ReferenceAssetKind; workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const {label, parameter, endpoint} = referenceAssetKinds[kind];
  const { api, page } = useChloeScope();
  const query = useQuery({queryKey:['chloe-reference-assets',kind,api],queryFn:()=>get<ReferenceAssetCard[]>(`${api}/${endpoint}`),refetchInterval:5000});
  return <>
    <PageCheckStatus queries={[workspaceQuery,query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && (query.data.length ? <div className="asset-media-grid">{query.data.map(item=><AssetMediaCard key={item.id} title={`${item.id} · ${item.name}`} entry formal revision={0}
      to={`${page}?section=assets&asset=${kind}&${parameter}=${encodeURIComponent(item.id)}`}
      item={{media:item.media,emptyLabel:`尚未采用${label}展示图`}} />)}</div> : <p className="muted">暂无{label}资料。</p>)}
  </>;
}

export function ChloeReferenceAssetDetail({ kind, query, workspaceQuery }: { kind: ReferenceAssetKind; query: UseQueryResult<ReferenceAssetDetail>; workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const {label, endpoint, ratio} = referenceAssetKinds[kind];
  const purposes = [label+'展示图'];
  const aspectRatio = kind === 'hair' ? 16 / 9 : undefined;
  const { api, page } = useChloeScope();
  const [params,setParams] = useSearchParams();
  const [document,setDocument] = useState<FileItem | null>(null);
  const data = query.data;
  const purpose = purposes.includes(params.get('purpose')!) ? params.get('purpose')! : purposes[0];
  const select = (key: string, value: string | null) => {
    const next=new URLSearchParams(params);
    if(value===null) next.delete(key); else next.set(key,value);
    setParams(next);
  };
  const adopted = data?.images.filter(image=>image.adopted && image.purpose.split('/')[0]===purpose) || [];
  const others = data?.images.filter(image=>!image.adopted && image.purpose.split('/')[0]===purpose).reverse().sort((a,b)=>b.version.localeCompare(a.version,undefined,{numeric:true})) || [];
  const references = data?.images.filter(image=>image.purpose===label+'参考图') || [];
  const preview = data?.images.find(image=>`${image.resource}@${image.version}`===params.get('ref'))?.media;
  const open = (file: FileItem) => {
    const image=data?.images.find(image=>image.media.url===file.url);
    if(image) select('ref',`${image.resource}@${image.version}`); else setDocument(file);
  };
  return <PreviewContext.Provider value={open}>
    <PageCheckStatus queries={[workspaceQuery,query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {data && <div className="chloe-model-layout">
      <div className="chloe-model-detail">
        <div className="chloe-look-detail">
          <section className="panel" aria-label={label+'信息'}><h2>{label}信息</h2>
            <dl className="chloe-overview-fields"><div><dt>{label}名称</dt><dd>{data.name}</dd></div><div><dt>{label}说明</dt><dd>{data.description}</dd></div></dl>
            <section aria-label={label+'参考图'}><h3>参考图</h3>
              {references.length ? <ul>{references.map((image,index)=><li key={`${image.resource}@${image.version}`}>
                <LinkButton onClick={()=>open(image.media)}>参考图 {index+1} · {image.resource}@{image.version}</LinkButton>
              </li>)}</ul> : <p>无</p>}
            </section>
          </section>
          <section className="panel chloe-look-images" aria-label={label+'图片'}><h2>{label}图片（{ratio}）</h2>
            <UnderlineTabs label={label+'图片用途'} items={purposes.map(value=>({value,label:value}))} selected={purpose} onChange={value=>select('purpose',value)} />
            {adopted.length ? adopted.map(image=><AssetMediaCard key={`${image.purpose}:${image.resource}@${image.version}`} title={`${image.purpose} · ${image.resource}@${image.version}`} formal aspectRatio={aspectRatio} showFileActions={false} showVersion={false} revision={0} item={{media:image.media,version:image.version}} />)
              : <AssetMediaCard title={purpose} hideTitle formal aspectRatio={aspectRatio} revision={0} item={{emptyLabel:`尚未采用${purpose}`}} />}
            {others.length>0 && <details><summary>其他版本</summary><div className="chloe-model-versions" aria-label={label+'其他版本'} tabIndex={0}>{others.map(image=><div key={`${image.purpose}:${image.resource}@${image.version}`}>
              <AssetMediaCard title={`${image.purpose} · ${image.resource}@${image.version}`} compact revision={0} item={{media:image.media}} />
              <details><summary>来源与执行记录</summary><Rich html={image.sourceHtml} /><p>执行编号：{image.execution}</p></details>
            </div>)}</div></details>}
          </section>
        </div>
        <ChloeAssetRecords sections={data.sections} />
      </div>
    </div>}
    {document ? <Preview project="" item={document} baseUrl={`${api}/${endpoint}/${encodeURIComponent(data!.id)}`} revision={0} close={()=>setDocument(null)} />
      : preview && <FullscreenImage title={preview.name} src={preview.url!} alt={preview.name} close={()=>select('ref',null)} />}
  </PreviewContext.Provider>;
}
