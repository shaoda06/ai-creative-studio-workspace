import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import type { UseQueryResult } from '@tanstack/react-query';
import type { FileItem, WorkspaceSpace } from './api';
import { Preview, PreviewContext, Result, Rich } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { PageCheckStatus } from './components/PageCheckStatus';
import { UnderlineTabs } from './components/UnderlineTabs';
import { FileActions } from './components/FileActions';

interface ModelImage {
  purpose: string; resource: string; version: string; adopted: boolean;
  media: FileItem; sourceHtml: string; execution: string;
}
export interface ModelDetail {
  id: string; name: string; images: ModelImage[]; url: string;
  sections: {heading: string; html: string; empty: boolean}[];
  looks: {id: string; name: string; media: FileItem | null; html: string; url: string}[];
}
const tabs = [{value:'info',label:'模特信息'},{value:'images',label:'模特图片'},{value:'looks',label:'造型'}];
const bodyPurposes = ['全身三视图遮面版', '全身三视图原图', '补充细节'];
const executionSections = ['执行记录', '输入记录', '输出记录', '审阅记录', '返修记录'];

export function ChloeModelDetail({ query, workspaceQuery }: { query: UseQueryResult<ModelDetail>; workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const { spaceId } = useParams();
  const [params, setParams] = useSearchParams();
  const [document, setDocument] = useState<FileItem | null>(null);
  const data = query.data;
  const requestedTab = params.get('modelTab');
  const tab = requestedTab==='face' || requestedTab==='body' ? 'images' : tabs.find(item=>item.value===requestedTab)?.value || 'info';
  const purpose = bodyPurposes.includes(params.get('purpose')!) ? params.get('purpose')! : bodyPurposes[0];
  const view = params.get('view') === 'original' ? 'original' : 'masked';
  const select = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    next.set('modelTab',tab);
    if (value === null) next.delete(key); else next.set(key, value);
    setParams(next);
  };
  const lookUrl = (id?: string) => {
    const next = new URLSearchParams(params);
    next.set('modelTab','looks'); next.delete('ref');
    if (id) next.set('look',id); else next.delete('look');
    return `/spaces/${encodeURIComponent(spaceId!)}?${next}`;
  };
  const look = data?.looks.find(item=>item.id===params.get('look'));
  const preview = data?.images.find(image => `${image.resource}@${image.version}` === params.get('ref'))?.media;
  const open = (item: FileItem) => {
    const image = data?.images.find(image => image.media.url === item.url);
    if (image) select('ref', `${image.resource}@${image.version}`); else setDocument(item);
  };
  const section = (heading: string) => {
    const value = data!.sections.find(section => section.heading === heading)!;
    return value.empty ? <p className="muted">暂无{heading}。</p> : <Rich html={value.html} fieldTable={heading==='人物特征'} />;
  };
  const adopted = (purpose: string) => data!.images.find(image => image.adopted && image.purpose === purpose);
  const imageCard = (purpose: string, image?: ModelImage) => <AssetMediaCard title={image ? `${purpose} · ${image.resource}@${image.version}` : purpose} formal hideTitle revision={0}
    item={{ media: image?.media, version: image?.version, emptyLabel: `尚未采用${purpose}` }} />;
  const otherVersions = (purpose: string) => data!.images
    .filter(image=>!image.adopted && image.purpose.split('/')[0]===purpose)
    .reverse().sort((a,b)=>b.version.localeCompare(a.version,undefined,{numeric:true}));
  const references = (purpose: string) => {
    const images = otherVersions(purpose);
    return images.length ? <div className="chloe-model-versions" aria-label={`${purpose}其他版本`} tabIndex={0}>{images.map(image=><div key={`${image.purpose}:${image.resource}@${image.version}`}>
      <AssetMediaCard title={`${image.purpose} · ${image.resource}@${image.version}`} compact revision={0} item={{media:image.media,version:image.version}} />
      <details><summary>来源与执行记录</summary><p>来源或原图引用：</p><Rich html={image.sourceHtml} /><p>执行编号：{image.execution}</p></details>
    </div>)}</div> : <p className="muted">暂无{purpose}其他版本。</p>;
  };
  return <PreviewContext.Provider value={open}>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {data && <div className="chloe-model-detail">
      <UnderlineTabs label="模特详情分类" items={tabs} selected={tab} onChange={value=>{
        const next=new URLSearchParams(params); next.set('modelTab',value); next.delete('ref'); next.delete('look');
        setDocument(null); setParams(next);
      }} />
      {tab==='info' && <>
        <section className="panel"><h2>人物特征</h2>{section('人物特征')}</section>
      </>}
      {tab==='images' && <div className="chloe-model-images">
        <section className="panel chloe-model-image-column" aria-label="正面面部图">
          <h2>正面面部图</h2>
          <div><UnderlineTabs label="正面面部图视图" items={[{value:'original',label:'原图'}]} selected="original" onChange={() => {}} /></div>
          <div>{imageCard('正面面部',adopted('正面面部'))}</div>
          <div>{otherVersions('正面面部').length > 0 && <details><summary>其他版本</summary>{references('正面面部')}</details>}</div>
        </section>
        <section className="panel chloe-model-image-column" aria-label="基础全身三视图">
          <h2>基础全身三视图</h2>
          <div>
            <UnderlineTabs label="当前采用三视图" items={[{value:'masked',label:'遮面版'},{value:'original',label:'原图'}]} selected={view} onChange={value=>select('view',value)} />
          </div>
          <div>{imageCard(view==='masked' ? bodyPurposes[0] : bodyPurposes[1],adopted(view==='masked' ? bodyPurposes[0] : bodyPurposes[1]))}</div>
          <div>{bodyPurposes.some(value=>otherVersions(value).length > 0) && <details><summary>其他版本</summary>
            <UnderlineTabs label="模特图片用途" items={bodyPurposes.map(value=>({value,label:value}))} selected={purpose} onChange={value=>select('purpose',value)} />
            <div className="chloe-assets-content">{references(purpose)}</div>
          </details>}</div>
        </section>
      </div>}
      {tab==='looks' && (look ? <section className="panel">
        <Link to={lookUrl()}>返回造型列表</Link><Rich html={look.html} /><FileActions url={look.url} />
      </section> : <section className="panel">
        {data.looks.length ? <div className="asset-media-grid">{data.looks.map(item=><AssetMediaCard key={item.id} title={`${item.id} · ${item.name}`} formal entry revision={0}
          to={lookUrl(item.id)} item={{media:item.media,emptyLabel:'尚未采用全身三视图遮面版'}} />)}</div> : <p className="muted">暂无该模特的造型资料。</p>}
      </section>)}
      {tab!=='looks' && <details className="panel"><summary>资料与制作记录</summary>
        {['关联资料','当前采用','采用变更'].map(heading=><details key={heading}><summary>{heading==='当前采用' ? '采用依据与时间' : heading}</summary>{section(heading)}</details>)}
        <details><summary>执行记录</summary>{executionSections.map(heading=><section key={heading}>{heading!=='执行记录' && <h3>{heading}</h3>}{section(heading)}</section>)}</details>
      </details>}
    </div>}
    {(document || preview) && <Preview project="" item={document || preview!} baseUrl={`/api/workspaces/${encodeURIComponent(spaceId!)}/shared-models/${encodeURIComponent(data!.id)}`} revision={0}
      close={() => { if (document) setDocument(null); else select('ref',null); }} />}
  </PreviewContext.Provider>;
}
