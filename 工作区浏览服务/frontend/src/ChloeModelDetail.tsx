import { ChloeAssetRecords } from './ChloeAssetRecords';
import { FullscreenImage } from './components/FullscreenImage';
import { useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import type { UseQueryResult } from '@tanstack/react-query';
import type { FileItem, WorkspaceSpace } from './api';
import { Preview, PreviewContext, Result, Rich } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { PageCheckStatus } from './components/PageCheckStatus';
import { UnderlineTabs } from './components/UnderlineTabs';

interface ModelImage {
  purpose: string; resource: string; version: string; adopted: boolean;
  media: FileItem; sourceHtml: string; execution: string;
}
export interface AssetDetail {
  id: string; name: string; images: ModelImage[]; url: string;
  sections: {heading: string; html: string; empty: boolean}[];
}
export interface ModelDetail extends AssetDetail {
  looks: (AssetDetail & {media: FileItem | null; description: string; clothing: {reference: string; executions: string[]; media: FileItem}[]})[];
}
const tabs = [{value:'info',label:'模特信息'},{value:'images',label:'模特图片'},{value:'looks',label:'造型'}];
const bodyPurposes = ['全身三视图遮面版', '全身三视图原图'];

export function ChloeModelDetail({ query, workspaceQuery }: { query: UseQueryResult<ModelDetail>; workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const { spaceId } = useParams();
  const [params, setParams] = useSearchParams();
  const [document, setDocument] = useState<FileItem | null>(null);
  const data = query.data;
  const requestedTab = params.get('modelTab');
  const tab = requestedTab==='face' || requestedTab==='body' ? 'images' : tabs.find(item=>item.value===requestedTab)?.value || 'info';
  const view = params.get('view') === 'original' ? 'original' : params.get('view') === 'masked' ? 'masked' : tab==='looks' ? 'original' : 'masked';
  const select = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    next.set('modelTab',tab);
    if (key==='view') next.delete('purpose');
    if (value === null) next.delete(key); else next.set(key, value);
    setParams(next);
  };
  const lookUrl = (id?: string) => {
    const next = new URLSearchParams(params);
    next.set('modelTab','looks'); next.delete('ref');
    next.delete('lookTab'); next.delete('purpose'); next.set('view','original');
    if (id) next.set('look',id); else next.delete('look');
    return `/spaces/${encodeURIComponent(spaceId!)}?${next}`;
  };
  const look = tab==='looks' ? data?.looks.find(item=>item.id===params.get('look')) : undefined;
  const asset = look || data;
  const preview = asset?.images.find(image => `${image.resource}@${image.version}` === params.get('ref'))?.media || look?.clothing.find(item=>item.reference===params.get('ref'))?.media;
  const open = (item: FileItem) => {
    const image = asset?.images.find(image => image.media.url === item.url);
    const clothing = look?.clothing.find(reference=>reference.media.url===item.url);
    if (image) select('ref', `${image.resource}@${image.version}`); else if (clothing) select('ref',clothing.reference); else setDocument(item);
  };
  const section = (heading: string) => {
    const value = asset!.sections.find(section => section.heading === heading)!;
    return value.empty ? <p className="muted">暂无{heading}。</p> : <Rich html={value.html} fieldTable={heading==='人物特征'} />;
  };
  const adopted = (purpose: string) => asset!.images.find(image => image.adopted && image.purpose === purpose);
  const faceImage = data && adopted('正面面部');
  const faceViewsImage = data && adopted('面部三视图');
  const bodyPurpose = view==='masked' ? bodyPurposes[0] : bodyPurposes[1];
  const bodyImage = data && adopted(bodyPurpose);
  const imageCard = (purpose: string, image?: ModelImage, aspectRatio?: number) => <AssetMediaCard aspectRatio={aspectRatio} title={image ? `${purpose} · ${image.resource}@${image.version}` : purpose} formal hideTitle revision={0} showFileActions={false} showVersion={false}
    item={{ media: image?.media, version: image?.version, emptyLabel: `尚未采用${purpose}` }} />;
  const otherVersions = (purpose: string) => asset!.images
    .filter(image=>!image.adopted && image.purpose.split('/')[0]===purpose)
    .reverse().sort((a,b)=>b.version.localeCompare(a.version,undefined,{numeric:true}));
  const references = (purpose: string) => {
    const images = otherVersions(purpose);
    return images.length ? <div className="chloe-model-versions" aria-label={`${purpose}其他版本`} tabIndex={0}>{images.map(image=><div key={`${image.purpose}:${image.resource}@${image.version}`}>
      <AssetMediaCard title={`${image.purpose} · ${image.resource}@${image.version}`} compact revision={0} item={{media:image.media,version:image.version}} />
      <details><summary>来源与执行记录</summary><p>来源或原图引用：</p><Rich html={image.sourceHtml} /><p>执行编号：{image.execution}</p></details>
    </div>)}</div> : <p className="muted">暂无{purpose}其他版本。</p>;
  };
  const bodyImages = () => <>
          <h2>{look ? '全身定装三视图（4:3）' : '基础全身三视图（4:3）'}{bodyImage && <span className="muted"> · {bodyImage.resource}@{bodyImage.version}</span>}</h2>
          <div>
            <UnderlineTabs label="当前采用三视图" items={look ? [{value:'original',label:'原图'},{value:'masked',label:'遮面版'}] : [{value:'masked',label:'遮面版'},{value:'original',label:'原图'}]} selected={view} onChange={value=>select('view',value)} />
          </div>
          <div>{imageCard(bodyPurpose,bodyImage,look ? undefined : 4 / 3)}</div>
          <div>{otherVersions(bodyPurpose).length > 0 && <details><summary>其他版本</summary>
            <div className="chloe-assets-content">{references(bodyPurpose)}</div>
          </details>}</div>
  </>;
  return <PreviewContext.Provider value={open}>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {data && <div className="chloe-model-layout">
      <div className="chloe-model-navigation">
      <UnderlineTabs label="模特详情分类" items={tabs} selected={tab} onChange={value=>{
        const next=new URLSearchParams(params); next.set('modelTab',value); next.delete('ref'); next.delete('look');
        setDocument(null); setParams(next);
      }} />
      </div>
      <div className="chloe-model-detail">
      {tab==='info' && <>
        <section className="panel"><h2>人物特征</h2>{section('人物特征')}</section>
      </>}
      {tab==='images' && <div className="chloe-model-images">
        <section className="panel chloe-model-image-column" aria-label="正面面部图">
          <h2>正面面部图（3:4）{faceImage && <span className="muted"> · {faceImage.resource}@{faceImage.version}</span>}</h2>
          <div><UnderlineTabs label="正面面部图视图" items={[{value:'original',label:'原图'}]} selected="original" onChange={() => {}} /></div>
          <div>{imageCard('正面面部',faceImage)}</div>
          <div>{otherVersions('正面面部').length > 0 && <details><summary>其他版本</summary>{references('正面面部')}</details>}</div>
        </section>
        <section className="panel chloe-model-image-column" aria-label="面部三视图">
          <h2>面部三视图（16:9）{faceViewsImage && <span className="muted"> · {faceViewsImage.resource}@{faceViewsImage.version}</span>}</h2>
          <div><UnderlineTabs label="面部三视图视图" items={[{value:'original',label:'原图'}]} selected="original" onChange={() => {}} /></div>
          <div>{imageCard('面部三视图',faceViewsImage)}</div>
          <div>{otherVersions('面部三视图').length > 0 && <details><summary>其他版本</summary>{references('面部三视图')}</details>}</div>
        </section>
        <section className="panel chloe-model-image-column chloe-model-body-column" aria-label="基础全身三视图">
          {bodyImages()}
        </section>
      </div>}
      {tab==='looks' && (look ? <>
        <div className="chloe-look-detail">
          <section className="panel" aria-label="造型信息"><h2>造型信息</h2>
            <dl className="chloe-overview-fields"><div><dt>造型名称</dt><dd>{look.name}</dd></div><div><dt>所属模特</dt><dd>{data.id} · {data.name}</dd></div><div><dt>造型说明</dt><dd>{look.description}</dd></div></dl>
            <section className="chloe-assets-content" aria-label="服装参考图"><h3>服装参考图</h3>
              {look.clothing.length ? <div className="chloe-look-clothing">{look.clothing.map(item=><div key={item.reference}>
                <AssetMediaCard title={item.reference} compact revision={0} item={{media:item.media}} />
                <p className="muted">执行编号：{item.executions.join('、')}</p>
              </div>)}</div> : <p>无</p>}
            </section>
          </section>
          <section className="panel chloe-look-images" aria-label="全身定装三视图">{bodyImages()}</section>
        </div>
      </> : <section className="panel">
        {data.looks.length ? <div className="asset-media-grid">{data.looks.map(item=><AssetMediaCard key={item.id} title={`${item.id} · ${item.name}`} formal entry revision={0}
          to={lookUrl(item.id)} item={{media:item.media,emptyLabel:'尚未采用全身三视图原图'}} />)}</div> : <p className="muted">暂无该模特的造型资料。</p>}
      </section>)}
      {(tab!=='looks' || look) && <ChloeAssetRecords sections={asset!.sections} />}
      </div>
    </div>}
    {document ? <Preview project="" item={document} baseUrl={`/api/workspaces/${encodeURIComponent(spaceId!)}/shared-models/${encodeURIComponent(data!.id)}`} revision={0} close={() => setDocument(null)} />
      : preview && <FullscreenImage title={preview.name} src={preview.url!} alt={preview.name} close={() => select('ref',null)} />}
  </PreviewContext.Provider>;
}
