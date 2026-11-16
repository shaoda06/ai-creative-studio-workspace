import { assetPaging, useAssetDraft, useAssetPage } from './chloeAssetPages';
import { Activity, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { get } from './api';
import { useChloeScope } from './chloeScope';
import type { ModelDetail } from './ChloeModelDetail';
import { ChloeAccessoryColumns, ChloeAssetTypes, referenceAssetKinds } from './ChloeReferenceAssets';
import type { ReferenceAssetCard } from './ChloeReferenceAssets';
import { PreviewContext, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { AssetSelectionDialog } from './components/AssetSelectionDialog';
import { FullscreenImage } from './components/FullscreenImage';
import { LinkButton } from './components/LinkButton';
import { UnderlineTabs } from './components/UnderlineTabs';
import { AssemblyExport, AssemblyPagination, AssemblyPreview, assetTitle } from './ChloeAssemblyParts';
import type { OpenImage } from './ChloeAssemblyParts';
import { ChloeVideoAssembly } from './ChloeVideoAssembly';
import './ChloeAssembly.css';

type PickerKind = 'models' | 'garments' | 'outfits' | 'hair' | 'accessories' | 'poses';
type AssemblyAsset = Pick<ReferenceAssetCard, 'id' | 'name' | 'media' | 'bodyArea'>;
const accessoryLimit = 5;
const garmentLimit = 5;
const assemblyTabs = [
  { value: 'outfit', label: '套装装配' }, { value: 'look', label: '造型装配' },
  { value: 'poses', label: '姿态装配' }, { value: 'video', label: '视频装配' },
];
type AssemblyProps = { projectName: string; renderNavigation: (reset?: () => void) => ReactNode };

const garmentTitle = (asset: AssemblyAsset) => `${assetTitle(asset)}（${asset.bodyArea}）`;

function AddAssetCard({ label, onClick }: { label: string; onClick: () => void }) {
  return <button type="button" className="chloe-assembly-add" aria-label={label} onClick={onClick}>
    <span aria-hidden="true">+</span>{label}
  </button>;
}

function SelectedAssemblyCard({ asset, title, aspectRatio, onRemove, compact }: {
  asset: AssemblyAsset; title: string; aspectRatio: number | 'natural'; onRemove: () => void; compact?: boolean;
}) {
  return <div className="chloe-assembly-selected-card">
    <AssetMediaCard title={title} formal entry compact={compact} aspectRatio={aspectRatio} revision={0} item={{media: asset.media}} />
    <button type="button" className="danger-button" aria-label={`移除${assetTitle(asset)}`} onClick={onRemove}>移除</button>
  </div>;
}

function AssemblyPicker<T extends AssemblyAsset>({ kind, initial, onConfirm, onClose }: {
  kind: PickerKind; initial: T[]; onConfirm: (assets: T[]) => void; onClose: () => void;
}) {
  const [page, setPage] = useState(1);
  const [types, setTypes] = useState<string[]>([]);
  const isModel = kind === 'models';
  const isAccessory = kind === 'accessories';
  const isGarment = kind === 'garments';
  const isPose = kind === 'poses';
  const form = isGarment ? '单件' : kind === 'outfits' ? '套装' : null;
  const referenceKind = kind === 'hair' || kind === 'accessories' ? kind : 'clothing';
  const limit = isPose ? undefined : isGarment ? garmentLimit : isAccessory ? accessoryLimit : 1;
  const label = isPose ? '姿态' : isModel ? '模特' : form ?? referenceAssetKinds[referenceKind].label;
  const endpoint = isPose ? 'shared-poses' : isModel ? 'shared-models' : referenceAssetKinds[referenceKind].endpoint;
  const filters = { available: true, require_media: true, form: form ?? undefined };
  const query = useAssetPage<T>(endpoint, page, filters, types);
  const draft = useAssetDraft<T>(endpoint, filters, initial.map(asset => asset.id), onConfirm);
  const selected = draft.selected;
  const ready = !!query.data && !query.isFetching && !query.error && !draft.initial.isFetching && !draft.initial.error;
  const atLimit = limit !== undefined && limit > 1 && selected.length >= limit;
  const cards = ready ? query.data!.items.map(asset => {
    const checked = selected.some(item => item.id === asset.id);
    return <AssetMediaCard key={asset.id} title={isGarment ? garmentTitle(asset) : assetTitle(asset)} formal entry compact={isPose} aspectRatio="natural" revision={0}
      item={{media: asset.media, emptyLabel: isModel ? '尚未采用正面面部图' : `尚未采用${label}展示图`}}
      selection={{selected: checked, disabled: draft.confirming || (atLimit && !checked),
        onSelect: () => draft.setSelected(checked ? selected.filter(item => item.id !== asset.id)
          : limit === 1 ? [asset] : [...selected, asset])}} />;
  }) : [];
  const filterTypes = [...new Set([...(query.data?.types ?? []), ...types])];
  const setTypeChecked = (type: string, checked: boolean) => {
    setTypes(checked ? [...types, type] : types.filter(value => value !== type));
    setPage(1);
  };
  const failed = query.error ? query : draft.initial;
  return <AssetSelectionDialog title={`选择${label} ${selected.length}${limit === undefined ? ' 项' : `/${limit}`}`} close={onClose}
    confirm={draft.confirmSelection}
    confirmDisabled={!ready || draft.confirming || (!selected.length && !initial.length)}
    toolbar={filterTypes.length > 0 && <ChloeAssetTypes types={filterTypes} activeTypes={types}
      setTypeChecked={setTypeChecked} label={isPose ? '按分类筛选' : isGarment ? '按部位筛选' : undefined} />}>
    <Result loading={query.isFetching || draft.initial.isFetching} error={failed.error} retry={failed.refetch} retrying={failed.isFetching} />
    {ready && (cards.length ? isAccessory
      ? <ChloeAccessoryColumns cards={cards} />
      : <div className={isPose ? 'asset-media-grid chloe-assembly-poses' : 'asset-media-grid'}>{cards}</div>
      : <p className="muted">暂无可用{label}。</p>)}
    {ready && <AssemblyPagination {...assetPaging(query.data!, setPage)} />}
  </AssetSelectionDialog>;
}

export function ChloeAssembly({ projectName, renderNavigation }: AssemblyProps) {
  const [params, setParams] = useSearchParams();
  const requestedTab = params.get('assemblyTab');
  const tab = assemblyTabs.find(item => item.value === requestedTab)?.value ?? 'outfit';
  const navigation = (reset?: () => void) => <>
    {renderNavigation(reset)}
    <div className="chloe-assets-content">
      <UnderlineTabs label="装配分类" items={assemblyTabs} selected={tab} onChange={value => {
        if (value === tab) return;
        setParams({ section: 'assets', asset: 'assembly', assemblyTab: value });
      }} />
    </div>
  </>;
  return <>
    <Activity mode={tab === 'outfit' ? 'visible' : 'hidden'}>
      <OutfitAssembly projectName={projectName} renderNavigation={navigation} />
    </Activity>
    <Activity mode={tab === 'look' ? 'visible' : 'hidden'}>
      <LookAssembly projectName={projectName} renderNavigation={navigation} />
    </Activity>
    <Activity mode={tab === 'poses' ? 'visible' : 'hidden'}>
      <ListAssembly<AssemblyAsset> kind="poses" renderNavigation={navigation}
        buildHandoff={poses => poses.map(assetTitle).join('\n')} />
    </Activity>
    <Activity mode={tab === 'video' ? 'visible' : 'hidden'}>
      <ChloeVideoAssembly projectName={projectName} renderNavigation={navigation} active={tab === 'video'} />
    </Activity>
  </>;
}

function OutfitAssembly({ projectName, renderNavigation }: AssemblyProps) {
  return <ListAssembly<ReferenceAssetCard> kind="garments" renderNavigation={renderNavigation} buildHandoff={garments => [
    `请为「${projectName}」用以下单件合成一张套装展示图，套装仅包含服装。`,
    '',
    ...garments.map((asset, index) => `${index + 1}. ${assetTitle(asset)}`),
    '',
    '按编号和标题找到各单件正式采用的服装展示图。生成前先逐张打开并查看，核对部位重复、叠穿顺序、缺少的衣物及看不清的结构，给出具体搭配建议。若需要更换单件或调整保留范围，先确认方案再生成。',
    '按 Chloe 服装展示图流程制作与送审。登记时将服装形态填为套装，套装来源填为合成，记录各单件的准确输入版本、实际组成和穿法。',
  ].join('\n')} />;
}

function ListAssembly<T extends AssemblyAsset>({ kind, renderNavigation, buildHandoff }: {
  kind: 'garments' | 'poses'; renderNavigation: AssemblyProps['renderNavigation']; buildHandoff: (assets: T[]) => string;
}) {
  const [selected, setSelected] = useState<T[]>([]);
  const [handoff, setHandoff] = useState('');
  const [picking, setPicking] = useState(false);
  const [preview, setPreview] = useState<{title: string; src: string} | null>(null);
  const isPose = kind === 'poses';
  const label = isPose ? '姿态' : '单件';
  const title = isPose ? assetTitle : garmentTitle;
  const count = isPose ? `${selected.length} 项` : `${selected.length}/${garmentLimit}`;
  const editing = isPose ? selected.length > 0 : selected.length === garmentLimit;
  const readyHint = isPose ? '点击「生成」，列出所选姿态的编号和标题。' : '点击「生成」，整理套装制作交接词。';
  const emptyHint = isPose ? '选定姿态后可导出编号和标题。' : '选定 1–5 项单件后可生成交接词。';

  const changeSelection = (assets: T[]) => {
    setSelected(assets);
    setHandoff('');
    setPicking(false);
  };

  return <>
    {renderNavigation(selected.length ? () => changeSelection([]) : undefined)}
    <div className="chloe-assets-content chloe-assembly">
      <section aria-label={`${label}选择`}>
        <h2>{label}选择 {count}</h2>
        <div className={`chloe-assembly-accessories ${isPose ? 'chloe-assembly-poses' : 'chloe-assembly-garments'}`}>
          <PreviewContext.Provider value={media => { if (media.url) setPreview({title: media.name, src: media.url}); }}>
            {selected.map(asset => <SelectedAssemblyCard key={asset.id} asset={asset} title={title(asset)} aspectRatio="natural" compact={isPose}
              onRemove={() => changeSelection(selected.filter(item => item.id !== asset.id))} />)}
          </PreviewContext.Provider>
          <AddAssetCard label={`${editing ? '编辑' : '添加'}${label}`} onClick={() => setPicking(true)} />
        </div>
      </section>
      <div className="chloe-assembly-summary chloe-assembly-summary-equal">
        <section aria-label="导出信息">
          <h2>导出信息</h2>
          <dl className="chloe-overview-fields" aria-live="polite">
            {selected.length ? selected.map((asset, index) => <div key={asset.id}><dt>{label} {index + 1}</dt><dd>{title(asset)}</dd></div>)
              : <div><dt>{label}</dt><dd>未选择</dd></div>}
          </dl>
        </section>
        <AssemblyExport label="导出文字" canGenerate={selected.length > 0} generate={() => setHandoff(buildHandoff(selected))} handoff={handoff}
          empty={selected.length ? readyHint : emptyHint} />
      </div>
      {picking && <AssemblyPicker kind={kind} initial={selected} onConfirm={changeSelection} onClose={() => setPicking(false)} />}
      {preview && <FullscreenImage title={preview.title} src={preview.src} alt={preview.title} close={() => setPreview(null)} />}
    </div>
  </>;
}

function LookAssembly({ projectName, renderNavigation }: AssemblyProps) {
  const { api } = useChloeScope();
  const [model, setModel] = useState<ReferenceAssetCard | null>(null);
  const [outfit, setOutfit] = useState<ReferenceAssetCard | null>(null);
  const [hair, setHair] = useState<ReferenceAssetCard | null>(null);
  const [accessories, setAccessories] = useState<ReferenceAssetCard[]>([]);
  const [handoff, setHandoff] = useState('');
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
  const currentAsset = picker === 'models' ? model : picker === 'hair' ? hair : outfit;
  const initial = picker === 'accessories' ? accessories : currentAsset ? [currentAsset] : [];
  const canGenerate = !!(model && outfit);

  const generate = () => {
    if (!model || !outfit) return;
    setHandoff([
      `请在「${projectName}」按以下装配开始制作造型图。`,
      '',
      `模特：${assetTitle(model)}`,
      `套装：${assetTitle(outfit)}`,
      ...(hair ? [`发型：${assetTitle(hair)}`] : []),
      ...(accessories.length
        ? ['配饰：', ...accessories.map((asset, index) => `${index + 1}. ${assetTitle(asset)}`)]
        : []),
      '',
      '请按对象编号和标题查找各自正式采用的参考图，按取景使用实际入镜的配饰，保持各视角的造型一致。若鞋履、妆发或搭配有需要确认的取舍，先确认再生成。',
      '请按 Chloe 造型流程从造型面部三视图开始，按顺序送审并接续全身定装三视图原图和遮面版。',
    ].join('\n'));
  };

  const confirm = (assets: ReferenceAssetCard[]) => {
    if (picker === 'models') setModel(assets[0] ?? null);
    if (picker === 'outfits') setOutfit(assets[0] ?? null);
    if (picker === 'hair') setHair(assets[0] ?? null);
    if (picker === 'accessories') setAccessories(assets);
    setHandoff('');
    setPicker(null);
  };
  const removeAccessory = (id: string) => {
    setAccessories(current => current.filter(asset => asset.id !== id));
    setHandoff('');
  };
  const reset = () => {
    setModel(null);
    setOutfit(null);
    setHair(null);
    setAccessories([]);
    setHandoff('');
  };

  return <>
    {renderNavigation(model || outfit || hair || accessories.length ? reset : undefined)}
    <div className="chloe-assets-content chloe-assembly">
    <div className="chloe-assembly-main">
      <section className="chloe-assembly-column" aria-label="模特选择">
        <h2>模特选择 {model ? 1 : 0}/1</h2>
        <button type="button" aria-label="选择模特" onClick={() => setPicker('models')}>{model ? assetTitle(model) : '选择模特'}</button>
        <div className="chloe-assembly-model-images">
          <AssemblyPreview label="正面基础图" media={front} empty={model ? '尚未采用正面基础图' : '请选择模特'} onPreview={openImage} />
          <AssemblyPreview label="基础三视图" media={body} empty={model ? modelQuery.isPending ? '正在读取基础三视图' : '尚未采用基础三视图' : '请选择模特'} onPreview={openImage} />
        </div>
      </section>
      <section className="chloe-assembly-column" aria-label="套装与发型选择">
        <h2>套装选择 {outfit ? 1 : 0}/1</h2>
        <button type="button" aria-label="选择套装" onClick={() => setPicker('outfits')}>{outfit ? assetTitle(outfit) : '选择套装'}</button>
        <div className="chloe-assembly-outfit-images">
          <AssemblyPreview label="套装图" media={outfit?.media} empty="请选择套装" onPreview={openImage} />
          <section className="chloe-assembly-hair" aria-label="发型选择">
            <h2>发型选择 {hair ? 1 : 0}/1</h2>
            <button type="button" aria-label="选择发型" onClick={() => setPicker('hair')}>{hair ? assetTitle(hair) : '选择发型'}</button>
            <AssemblyPreview label="发型图" media={hair?.media} empty="请选择发型" onPreview={openImage} />
          </section>
        </div>
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
          {accessories.map((asset, index) => <SelectedAssemblyCard key={asset.id} asset={asset} title={`配饰 ${index + 1} · ${assetTitle(asset)}`}
            aspectRatio={1} onRemove={() => removeAccessory(asset.id)} />)}
        </PreviewContext.Provider>
        {accessories.length < accessoryLimit && <AddAssetCard label="添加配饰" onClick={() => setPicker('accessories')} />}
      </div>
    </section>

    <div className="chloe-assembly-summary">
      <section aria-label="当前选择">
        <h2>当前选择</h2>
        <dl className="chloe-overview-fields" aria-live="polite">
          <div><dt>模特</dt><dd>{model ? assetTitle(model) : '未选择'}</dd></div>
          <div><dt>套装</dt><dd>{outfit ? assetTitle(outfit) : '未选择'}</dd></div>
          <div><dt>发型</dt><dd>{hair ? assetTitle(hair) : '未选择'}</dd></div>
          {accessories.length ? accessories.map((asset, index) => <div key={index}><dt>配饰 {index + 1}</dt><dd>{assetTitle(asset)}</dd></div>) :
            <div><dt>配饰</dt><dd>未选择</dd></div>}
        </dl>
      </section>
      <AssemblyExport canGenerate={canGenerate} generate={generate} handoff={handoff}
        empty={canGenerate ? '点击「生成」，整理当前选择的造型制作交接词。' : '选定模特和套装后可生成交接词，发型和配饰可选。'} />
    </div>
    {picker && <AssemblyPicker kind={picker} initial={initial} onConfirm={confirm} onClose={() => setPicker(null)} />}
    {preview && <FullscreenImage title={preview.title} src={preview.src} alt={preview.title} close={() => setPreview(null)} />}
    </div>
  </>;
}
