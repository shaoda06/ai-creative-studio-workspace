import { useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
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
}
const purposes = ['正面面部', '全身三视图原图', '全身三视图遮面版', '补充细节'];
const executionSections = ['执行记录', '输入记录', '输出记录', '审阅记录', '返修记录'];

export function ChloeModelDetail({ query, workspaceQuery }: { query: UseQueryResult<ModelDetail>; workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const { spaceId } = useParams();
  const [params, setParams] = useSearchParams();
  const [document, setDocument] = useState<FileItem | null>(null);
  const data = query.data;
  const purpose = params.get('purpose') || purposes[0];
  const view = params.get('view') === 'original' ? 'original' : 'masked';
  const select = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(key); else next.set(key, value);
    setParams(next);
  };
  const preview = data?.images.find(image => `${image.resource}@${image.version}` === params.get('ref'))?.media;
  const open = (item: FileItem) => {
    const image = data?.images.find(image => image.media.url === item.url);
    if (image) select('ref', `${image.resource}@${image.version}`); else setDocument(item);
  };
  const section = (heading: string) => {
    const value = data!.sections.find(section => section.heading === heading)!;
    return value.empty ? <p className="muted">暂无{heading}。</p> : <Rich html={value.html} />;
  };
  const adopted = (purpose: string) => data!.images.find(image => image.adopted && image.purpose === purpose);
  const imageCard = (purpose: string, image?: ModelImage) => <AssetMediaCard title={purpose} formal revision={0}
    item={{ media: image?.media, version: image?.version, scope: image ? `${image.resource}@${image.version}` : undefined, emptyLabel: `尚未采用${purpose}` }} />;
  return <PreviewContext.Provider value={open}>
    <PageCheckStatus queries={[workspaceQuery, query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {data && <div className="chloe-model-detail">
      <section className="panel"><h2>当前采用</h2>
        <div className="chloe-model-current">
          {imageCard('正面面部', adopted('正面面部'))}
          <div><UnderlineTabs label="当前采用三视图" items={[{value:'masked',label:'遮面版'},{value:'original',label:'原图'}]} selected={view} onChange={value => select('view',value)} />
            <div className="chloe-assets-content">{imageCard(view === 'masked' ? purposes[2] : purposes[1], adopted(view === 'masked' ? purposes[2] : purposes[1]))}</div>
          </div>
        </div>
        <details><summary>采用依据与时间</summary>{section('当前采用')}</details>
      </section>
      <section className="panel"><h2>参考版本</h2>
        <UnderlineTabs label="模特图片用途" items={purposes.map(value=>({value,label:value}))} selected={purpose} onChange={value=>select('purpose',value)} />
        <div className="chloe-assets-content">
          {data.images.some(image=>image.purpose.split('/')[0]===purpose) ? <div className="asset-media-grid">
            {data.images.filter(image=>image.purpose.split('/')[0]===purpose).map(image=><div key={`${image.purpose}:${image.resource}@${image.version}`}>
              <AssetMediaCard title={`${image.purpose} · ${image.resource}@${image.version}`} revision={0} item={{media:image.media,version:image.version}} />
              <p>{image.adopted ? '当前采用' : '未作为当前采用'}</p>
              <p>来源或原图引用：</p><Rich html={image.sourceHtml} />
              <p>执行编号：{image.execution}</p>
            </div>)}
          </div> : <p className="muted">暂无{purpose}参考版本。</p>}
        </div>
      </section>
      {['资产身份','人物特征'].map(heading=><section className="panel" key={heading}><h2>{heading}</h2>{section(heading)}</section>)}
      {['关联资料','采用变更'].map(heading=><details className="panel" key={heading}><summary>{heading}</summary>{section(heading)}</details>)}
      <details className="panel"><summary>执行记录</summary>{executionSections.map(heading=><section key={heading}>{heading!=='执行记录' && <h3>{heading}</h3>}{section(heading)}</section>)}</details>
      <FileActions url={data.url} />
    </div>}
    {(document || preview) && <Preview project="" item={document || preview!} baseUrl={`/api/workspaces/${encodeURIComponent(spaceId!)}/shared-models/${encodeURIComponent(data!.id)}`} revision={0}
      close={() => { if (document) setDocument(null); else select('ref',null); }} />}
  </PreviewContext.Provider>;
}
