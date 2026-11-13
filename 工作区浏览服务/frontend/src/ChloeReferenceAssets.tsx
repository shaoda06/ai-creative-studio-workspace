import { useChloeScope } from './chloeScope';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem, WorkspaceSpace } from './api';
import { Result, PreviewContext, Preview, Rich } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { FullscreenImage } from './components/FullscreenImage';
import { UnderlineTabs } from './components/UnderlineTabs';
import { PageCheckStatus } from './components/PageCheckStatus';
import { ChloeAssetRecords } from './ChloeAssetRecords';
import type { AssetDetail } from './ChloeModelDetail';

interface ClothingClassification {
  clothingForm?: '单件' | '套装' | null; bodyArea?: string | null;
  outfitSource?: '提取' | '合成' | null;
}
export interface ReferenceAssetCard extends ClothingClassification {
  id: string; name: string; media: FileItem | null; type?: string | null;
}
export interface ReferenceAssetDetail extends AssetDetail, ClothingClassification {
  description: string; type?: string; composition?: string;
}
export const referenceAssetKinds = {
  hair: {label:'发型', parameter:'hair', endpoint:'shared-hair', ratio:'16:9'},
  clothing: {label:'服装', parameter:'clothing', endpoint:'shared-clothing', ratio:'4:3'},
  accessories: {label:'配饰', parameter:'accessory', endpoint:'shared-accessories', ratio:null},
  scenes: {label:'场景', parameter:'scene', endpoint:'shared-scenes', ratio:null},
};
export type ReferenceAssetKind = keyof typeof referenceAssetKinds;
const clothingTabs = [{ value: 'outfits', label: '套装' }, { value: 'garments', label: '单件' }];

export function referenceAssetListParams(kind: ReferenceAssetKind, clothingTab: string | null) {
  const params = new URLSearchParams({ section: 'assets', asset: kind });
  if (kind === 'clothing' && clothingTab === 'outfits') params.set('clothingTab', clothingTab);
  return params;
}

export function useChloeAssetTypeFilter<T>(cards: T[], getType: (card: T) => string | null | undefined) {
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const types = Array.from(new Set(cards.map(getType).filter((type): type is string => !!type)))
    .sort((a, b) => a.localeCompare(b, 'zh-CN'));
  const activeTypes = types.filter(type => selectedTypes.includes(type));
  const visibleCards = activeTypes.length ? cards.filter(card => activeTypes.includes(getType(card) ?? '')) : cards;
  const setTypeChecked = (type: string, checked: boolean) => {
    setSelectedTypes(previous => checked ? [...previous, type] : previous.filter(value => value !== type));
  };
  return { types, activeTypes, visibleCards, setTypeChecked };
}

export function ChloeAssetTypes({ types, activeTypes, setTypeChecked, label = '按类型筛选' }: {
  types: string[]; activeTypes: string[]; label?: string;
  setTypeChecked: (type: string, checked: boolean) => void;
}) {
  return <fieldset className="chloe-asset-types"><legend>{label}</legend>
    {types.map(type => <label key={type}><input type="checkbox" checked={activeTypes.includes(type)}
      onChange={event => setTypeChecked(type, event.target.checked)} />{type}</label>)}
  </fieldset>;
}

export function ChloeAccessoryColumns({ cards }: { cards: ReactNode[] }) {
  return <div className="asset-media-grid chloe-accessory-columns">{[0, 1, 2].map(column =>
    <div className="chloe-accessory-column" key={column}>{cards.filter((_, index) => index % 3 === column)}</div>)}</div>;
}

export function ChloeReferenceAssets({ kind, workspaceQuery }: { kind: ReferenceAssetKind; workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const {label, parameter, endpoint} = referenceAssetKinds[kind];
  const { api, page } = useChloeScope();
  const [params, setParams] = useSearchParams();
  const isClothing = kind === 'clothing';
  const isOutfit = isClothing && params.get('clothingTab') === 'outfits';
  const clothingTab = isOutfit ? 'outfits' : 'garments';
  const isAccessory = kind === 'accessories';
  const query = useQuery({queryKey:['chloe-reference-assets',kind,api],queryFn:()=>get<ReferenceAssetCard[]>(`${api}/${endpoint}`),refetchInterval:5000});
  const cards = (query.data ?? []).filter(item => !isClothing || (item.clothingForm === '套装') === isOutfit);
  const filterByType = isAccessory || (isClothing && !isOutfit);
  const { visibleCards, ...filter } = useChloeAssetTypeFilter(filterByType ? cards : [], item => isAccessory ? item.type : item.bodyArea);
  const visible = filterByType ? visibleCards : cards;
  const listParams = referenceAssetListParams(kind, clothingTab);
  const renderCard = (item: ReferenceAssetCard) => <AssetMediaCard key={item.id} title={`${item.id} · ${item.name}`} entry formal aspectRatio="natural" revision={0}
    to={`${page}?${listParams}&${parameter}=${encodeURIComponent(item.id)}`}
    item={{media:item.media,emptyLabel:`尚未采用${label}展示图`}} />;
  return <>
    <PageCheckStatus queries={[workspaceQuery,query]} />
    {isClothing && <div className="chloe-clothing-tabs">
      <UnderlineTabs label="服装分类" items={clothingTabs} selected={clothingTab} onChange={value => {
        if (value !== clothingTab) setParams(referenceAssetListParams(kind, value));
      }} />
    </div>}
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {filter.types.length > 0 && <ChloeAssetTypes {...filter} label={isClothing ? '按部位筛选' : undefined} />}
    {query.data && (visible.length ? isAccessory
      ? <ChloeAccessoryColumns cards={visible.map(renderCard)} />
      : <div className="asset-media-grid">{visible.map(renderCard)}</div>
      : <p className="muted">暂无{isClothing ? (isOutfit ? '套装' : '单件') : label}资料。</p>)}
  </>;
}

export function ChloeReferenceAssetDetail({ kind, query, workspaceQuery }: { kind: ReferenceAssetKind; query: UseQueryResult<ReferenceAssetDetail>; workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const {label, endpoint, ratio} = referenceAssetKinds[kind];
  const purposes = [label+'展示图'];
  const { api } = useChloeScope();
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
          <section className="panel chloe-look-info" aria-label={label+'信息'}><h2>{label}信息</h2>
            <dl className="chloe-overview-fields">
              <div><dt>{label}名称</dt><dd>{data.name}</dd></div>
              {kind === 'accessories' && <div><dt>配饰类型</dt><dd>{data.type}</dd></div>}
              {data.clothingForm && <div><dt>服装形态</dt><dd>{data.clothingForm}</dd></div>}
              {data.bodyArea && <div><dt>部位</dt><dd>{data.bodyArea}</dd></div>}
              {data.outfitSource && <div><dt>套装来源</dt><dd>{data.outfitSource}</dd></div>}
              <div><dt>{label}说明</dt><dd>{data.description}</dd></div>
              {data.composition && <div><dt>组成与穿法</dt><dd>{data.composition}</dd></div>}
            </dl>
            <section className="chloe-assets-content chloe-look-references" aria-label={label+'参考图'}><h3>参考图</h3>
              {!references.length ? <p>无</p> : <div className="chloe-look-reference-list" tabIndex={0} aria-label={label+'参考图列表'}>
                {references.map((image,index)=><AssetMediaCard key={`${image.resource}@${image.version}`} title={`参考图 ${index+1} · ${image.resource}@${image.version}`}
                  compact revision={0} aspectRatio="natural" item={{media:image.media}} />)}
              </div>}
            </section>
          </section>
          <section className="panel chloe-look-images chloe-look-image-column" aria-label={label+'图片'}><h2>{label}图片{ratio && `（${ratio}）`}</h2>
            <UnderlineTabs label={label+'图片用途'} items={purposes.map(value=>({value,label:value}))} selected={purpose} onChange={value=>select('purpose',value)} />
            {adopted.length ? adopted.map(image=><AssetMediaCard key={`${image.purpose}:${image.resource}@${image.version}`} title={`${image.purpose} · ${image.resource}@${image.version}`} formal aspectRatio="natural" showFileActions={false} showVersion={false} revision={0} item={{media:image.media,version:image.version}} />)
              : <AssetMediaCard title={purpose} hideTitle formal aspectRatio={kind === 'hair' ? 16 / 9 : undefined} revision={0} item={{emptyLabel:`尚未采用${purpose}`}} />}
            {others.length>0 && <details><summary>其他版本</summary><div className="chloe-model-versions" aria-label={label+'其他版本'} tabIndex={0}>{others.map(image=><div key={`${image.purpose}:${image.resource}@${image.version}`}>
              <AssetMediaCard title={`${image.purpose} · ${image.resource}@${image.version}`} compact revision={0} aspectRatio="natural" item={{media:image.media}} />
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
