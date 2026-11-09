import { useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem } from './api';
import { useChloeScope } from './chloeScope';
import type { ModelDetail } from './ChloeModelDetail';
import { referenceAssetKinds } from './ChloeReferenceAssets';
import { Dialog, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import './ChloeAssembly.css';

type AssemblyAsset = { id: string; name: string; media: FileItem | null };
type PickerTarget = { kind: 'models' | 'clothing' } | { kind: 'accessories'; index: number };

const assetTitle = (asset: AssemblyAsset) => `${asset.id} · ${asset.name}`;

function AssemblyPicker({ kind, initialId, onConfirm, onClose }: {
  kind: PickerTarget['kind']; initialId?: string; onConfirm: (asset: AssemblyAsset) => void; onClose: () => void;
}) {
  const { api } = useChloeScope();
  const [draftId, setDraftId] = useState(initialId);
  const isModel = kind === 'models';
  const label = isModel ? '模特' : referenceAssetKinds[kind].label;
  const endpoint = isModel ? 'shared-models' : referenceAssetKinds[kind].endpoint;
  const query = useQuery({
    queryKey: isModel ? ['chloe-models', api] : ['chloe-reference-assets', kind, api],
    queryFn: () => get<AssemblyAsset[]>(`${api}/${endpoint}`),
  });
  const selected = query.data?.find(asset => asset.id === draftId && asset.media?.url);

  return <Dialog title={`选择${label}`} close={onClose} lockPageScroll>
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && (query.data.length ? <div className="asset-media-grid">
      {query.data.map(asset => <AssetMediaCard key={asset.id} title={assetTitle(asset)} formal entry aspectRatio="natural" revision={0}
        item={{media: asset.media, emptyLabel: isModel ? '尚未采用正面面部图' : `尚未采用${label}展示图`}}
        selection={{selected: selected?.id === asset.id, disabled: !asset.media?.url, onSelect: () => setDraftId(asset.id)}} />)}
    </div> : <p className="muted">暂无{label}资料。</p>)}
    <div className="chloe-assembly-confirm">
      <button type="button" disabled={!selected || !!query.error} onClick={() => { if (selected) onConfirm(selected); }}>确认选择</button>
    </div>
  </Dialog>;
}

function AssemblyPreview({ label, media, empty }: { label: string; media?: FileItem | null; empty: string }) {
  return <figure className="chloe-assembly-preview">
    <figcaption>{label}</figcaption>
    {media?.url ? <img src={media.url} alt={label} loading="lazy" /> : <span className="muted">{empty}</span>}
  </figure>;
}

export function ChloeAssembly({ renderNavigation }: { renderNavigation: (reset?: () => void) => ReactNode }) {
  const { api } = useChloeScope();
  const [model, setModel] = useState<AssemblyAsset | null>(null);
  const [clothing, setClothing] = useState<AssemblyAsset | null>(null);
  const [accessories, setAccessories] = useState<AssemblyAsset[]>([]);
  const [picker, setPicker] = useState<PickerTarget | null>(null);
  const modelId = model?.id;
  const modelQuery = useQuery({
    queryKey: ['chloe-model', api, modelId],
    queryFn: () => get<ModelDetail>(`${api}/shared-models/${encodeURIComponent(modelId!)}`),
    enabled: !!modelId,
  });
  const front = modelQuery.data?.images.find(image => image.adopted && image.purpose === '正面面部')?.media ?? model?.media;
  const body = modelQuery.data?.images.find(image => image.adopted && image.purpose === '全身三视图原图')?.media;
  const pickerId = picker?.kind === 'models' ? model?.id : picker?.kind === 'clothing' ? clothing?.id :
    picker?.kind === 'accessories' ? accessories[picker.index]?.id : undefined;

  const confirm = (asset: AssemblyAsset) => {
    if (picker?.kind === 'models') setModel(asset);
    if (picker?.kind === 'clothing') setClothing(asset);
    if (picker?.kind === 'accessories') {
      const { index } = picker;
      setAccessories(previous => index === previous.length ? [...previous, asset] : previous.map((item, i) => i === index ? asset : item));
    }
    setPicker(null);
  };
  const reset = () => {
    setModel(null);
    setClothing(null);
    setAccessories([]);
  };

  return <>
    {renderNavigation(model || clothing || accessories.length ? reset : undefined)}
    <div className="chloe-assets-content chloe-assembly">
    <div className="chloe-assembly-main">
      <section className="chloe-assembly-column" aria-label="模特选择">
        <h2>模特选择</h2>
        <button type="button" aria-label="选择模特" onClick={() => setPicker({kind: 'models'})}>{model ? assetTitle(model) : '选择模特'}</button>
        <div className="chloe-assembly-model-images">
          <AssemblyPreview label="正面基础图" media={front} empty={model ? '尚未采用正面基础图' : '请选择模特'} />
          <AssemblyPreview label="基础三视图" media={body} empty={model ? modelQuery.isPending ? '正在读取基础三视图' : '尚未采用基础三视图' : '请选择模特'} />
        </div>
      </section>
      <section className="chloe-assembly-column" aria-label="服装选择">
        <h2>服装选择</h2>
        <button type="button" aria-label="选择服装" onClick={() => setPicker({kind: 'clothing'})}>{clothing ? assetTitle(clothing) : '选择服装'}</button>
        <AssemblyPreview label="服装图" media={clothing?.media} empty="请选择服装" />
      </section>
    </div>
    {model && <Result loading={false} error={modelQuery.error} retry={modelQuery.refetch} retrying={modelQuery.isFetching} />}

    <section aria-label="配饰选择">
      <h2>配饰选择</h2>
      <div className="chloe-assembly-accessories">
        {accessories.map((asset, index) => <AssetMediaCard key={index} title={`配饰 ${index + 1} · ${assetTitle(asset)}`} formal entry aspectRatio={1} revision={0}
          item={{media: asset.media}} selection={{selected: false, onSelect: () => setPicker({kind: 'accessories', index})}} />)}
        <button type="button" className="chloe-assembly-add" aria-label="添加配饰" onClick={() => setPicker({kind: 'accessories', index: accessories.length})}>
          <span aria-hidden="true">+</span>添加配饰
        </button>
      </div>
    </section>

    <section aria-label="当前选择" className="chloe-assembly-summary">
      <h2>当前选择</h2>
      <dl className="chloe-overview-fields" aria-live="polite">
        <div><dt>模特</dt><dd>{model ? assetTitle(model) : '未选择'}</dd></div>
        <div><dt>服装</dt><dd>{clothing ? assetTitle(clothing) : '未选择'}</dd></div>
        {accessories.length ? accessories.map((asset, index) => <div key={index}><dt>配饰 {index + 1}</dt><dd>{assetTitle(asset)}</dd></div>) :
          <div><dt>配饰</dt><dd>未选择</dd></div>}
      </dl>
    </section>
    {picker && <AssemblyPicker kind={picker.kind} initialId={pickerId} onConfirm={confirm} onClose={() => setPicker(null)} />}
    </div>
  </>;
}
