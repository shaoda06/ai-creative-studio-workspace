import { useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem } from './api';
import { useChloeScope } from './chloeScope';
import type { ModelDetail } from './ChloeModelDetail';
import { referenceAssetKinds } from './ChloeReferenceAssets';
import { Dialog, PreviewContext, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { FullscreenImage } from './components/FullscreenImage';
import { LinkButton } from './components/LinkButton';
import './ChloeAssembly.css';

type AssemblyAsset = { id: string; name: string; media: FileItem | null };
type PickerKind = 'models' | 'clothing' | 'accessories';
type OpenImage = (title: string, src: string) => void;

const accessoryLimit = 5;
const assetTitle = (asset: AssemblyAsset) => `${asset.id} · ${asset.name}`;

function AssemblyPicker({ kind, initial, onConfirm, onClose, onPreview }: {
  kind: PickerKind; initial: AssemblyAsset[]; onConfirm: (assets: AssemblyAsset[]) => void; onClose: () => void; onPreview: OpenImage;
}) {
  const { api } = useChloeScope();
  const [draftIds, setDraftIds] = useState(() => initial.map(asset => asset.id));
  const isModel = kind === 'models';
  const multi = kind === 'accessories';
  const label = isModel ? '模特' : referenceAssetKinds[kind].label;
  const endpoint = isModel ? 'shared-models' : referenceAssetKinds[kind].endpoint;
  const query = useQuery({
    queryKey: isModel ? ['chloe-models', api] : ['chloe-reference-assets', kind, api],
    queryFn: () => get<AssemblyAsset[]>(`${api}/${endpoint}`),
  });
  const selected = draftIds.flatMap(id => {
    const asset = query.data?.find(item => item.id === id && item.media?.url);
    return asset ? [asset] : [];
  });
  const atLimit = multi && selected.length >= accessoryLimit;
  const title = multi ? `选择配饰 ${selected.length}/${accessoryLimit}` : `选择${label}`;
  const canConfirm = !!query.data && !query.error && (selected.length > 0 || initial.length > 0);

  return <Dialog title={title} close={onClose} lockPageScroll>
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && (query.data.length ? <div className="asset-media-grid">
      {query.data.map(asset => {
        const checked = selected.some(item => item.id === asset.id);
        const src = asset.media?.url;
        return <AssetMediaCard key={asset.id} title={assetTitle(asset)} formal entry aspectRatio="natural" revision={0}
          item={{media: asset.media, emptyLabel: isModel ? '尚未采用正面面部图' : `尚未采用${label}展示图`}}
          selection={{selected: checked, disabled: !src || (atLimit && !checked),
            onPreview: src ? () => onPreview(assetTitle(asset), src) : undefined,
            onSelect: () => {
              if (checked) {
                setDraftIds(selected.filter(item => item.id !== asset.id).map(item => item.id));
              } else {
                setDraftIds(multi ? [...selected.map(item => item.id), asset.id] : [asset.id]);
              }
            }}} />;
      })}
    </div> : <p className="muted">暂无{label}资料。</p>)}
    <div className="chloe-assembly-confirm">
      <button type="button" disabled={!canConfirm} onClick={() => onConfirm(selected)}>确认选择</button>
    </div>
  </Dialog>;
}

function AssemblyPreview({ label, media, empty, onPreview }: { label: string; media?: FileItem | null; empty: string; onPreview: OpenImage }) {
  return <figure className="chloe-assembly-preview">
    <figcaption>{label}</figcaption>
    {media?.url ? <button type="button" aria-label={`查看${label}大图`} onClick={() => onPreview(label, media.url!)}>
      <img src={media.url} alt={label} loading="lazy" />
    </button> : <span className="muted">{empty}</span>}
  </figure>;
}

export function ChloeAssembly({ renderNavigation }: { renderNavigation: (reset?: () => void) => ReactNode }) {
  const { api } = useChloeScope();
  const [model, setModel] = useState<AssemblyAsset | null>(null);
  const [clothing, setClothing] = useState<AssemblyAsset | null>(null);
  const [accessories, setAccessories] = useState<AssemblyAsset[]>([]);
  const [picker, setPicker] = useState<PickerKind | null>(null);
  const [preview, setPreview] = useState<{title: string; src: string} | null>(null);
  const openImage: OpenImage = (title, src) => setPreview({title, src});
  const modelId = model?.id;
  const modelQuery = useQuery({
    queryKey: ['chloe-model', api, modelId],
    queryFn: () => get<ModelDetail>(`${api}/shared-models/${encodeURIComponent(modelId!)}`),
    enabled: !!modelId,
  });
  const front = modelQuery.data?.images.find(image => image.adopted && image.purpose === '正面面部')?.media ?? model?.media;
  const body = modelQuery.data?.images.find(image => image.adopted && image.purpose === '全身三视图原图')?.media;
  const currentAsset = picker === 'models' ? model : clothing;
  const initial = picker === 'accessories' ? accessories : currentAsset ? [currentAsset] : [];

  const confirm = (assets: AssemblyAsset[]) => {
    if (picker === 'models') setModel(assets[0] ?? null);
    if (picker === 'clothing') setClothing(assets[0] ?? null);
    if (picker === 'accessories') setAccessories(assets);
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
        <button type="button" aria-label="选择模特" onClick={() => setPicker('models')}>{model ? assetTitle(model) : '选择模特'}</button>
        <div className="chloe-assembly-model-images">
          <AssemblyPreview label="正面基础图" media={front} empty={model ? '尚未采用正面基础图' : '请选择模特'} onPreview={openImage} />
          <AssemblyPreview label="基础三视图" media={body} empty={model ? modelQuery.isPending ? '正在读取基础三视图' : '尚未采用基础三视图' : '请选择模特'} onPreview={openImage} />
        </div>
      </section>
      <section className="chloe-assembly-column" aria-label="服装选择">
        <h2>服装选择</h2>
        <button type="button" aria-label="选择服装" onClick={() => setPicker('clothing')}>{clothing ? assetTitle(clothing) : '选择服装'}</button>
        <AssemblyPreview label="服装图" media={clothing?.media} empty="请选择服装" onPreview={openImage} />
      </section>
    </div>
    {model && <Result loading={false} error={modelQuery.error} retry={modelQuery.refetch} retrying={modelQuery.isFetching} />}

    <section aria-label="配饰选择">
      <div className="chloe-assembly-accessory-heading">
        <h2>配饰选择 {accessories.length}/{accessoryLimit}</h2>
        {accessories.length > 0 && <LinkButton onClick={() => setPicker('accessories')}>编辑配饰</LinkButton>}
      </div>
      <div className="chloe-assembly-accessories">
        <PreviewContext.Provider value={media => { if (media.url) openImage(media.name, media.url); }}>
          {accessories.map((asset, index) => <AssetMediaCard key={asset.id} title={`配饰 ${index + 1} · ${assetTitle(asset)}`} formal entry aspectRatio={1} revision={0}
            item={{media: asset.media}} />)}
        </PreviewContext.Provider>
        {accessories.length < accessoryLimit && <button type="button" className="chloe-assembly-add" aria-label="添加配饰" onClick={() => setPicker('accessories')}>
          <span aria-hidden="true">+</span>添加配饰
        </button>}
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
    {picker && <AssemblyPicker kind={picker} initial={initial} onConfirm={confirm} onClose={() => setPicker(null)} onPreview={openImage} />}
    {preview && <FullscreenImage title={preview.title} src={preview.src} alt={preview.title} close={() => setPreview(null)} />}
    </div>
  </>;
}
