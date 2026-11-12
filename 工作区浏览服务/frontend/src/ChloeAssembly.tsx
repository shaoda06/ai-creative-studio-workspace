import { Activity, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { get } from './api';
import type { FileItem } from './api';
import { useChloeScope } from './chloeScope';
import type { ModelDetail } from './ChloeModelDetail';
import { ChloeAccessoryColumns, ChloeAccessoryTypes, referenceAssetKinds, useChloeAccessoryFilter } from './ChloeReferenceAssets';
import { PreviewContext, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { AssetSelectionDialog } from './components/AssetSelectionDialog';
import { FullscreenImage } from './components/FullscreenImage';
import { LinkButton } from './components/LinkButton';
import { UnderlineTabs } from './components/UnderlineTabs';
import { AssemblyExport, AssemblyPreview, assetTitle } from './ChloeAssemblyParts';
import type { OpenImage } from './ChloeAssemblyParts';
import { ChloeVideoAssembly } from './ChloeVideoAssembly';
import './ChloeAssembly.css';

type AssemblyAsset = {
  id: string; name: string; status: '制作中' | '可用'; media: FileItem | null; type?: string | null;
  clothingForm?: '单件' | '套装' | null; bodyArea?: string | null;
  reference?: { resource: string; version: string } | null;
};
type PickerKind = 'models' | 'garments' | 'outfits' | 'hair' | 'accessories';
const accessoryLimit = 5;
const garmentLimit = 5;
const assemblyTabs = [
  { value: 'outfit', label: '套装装配' }, { value: 'look', label: '造型装配' }, { value: 'video', label: '视频装配' },
];
type AssemblyProps = { projectName: string; renderNavigation: (reset?: () => void) => ReactNode };

const garmentTitle = (asset: AssemblyAsset) => `${assetTitle(asset)}（${asset.bodyArea}）`;
const clothingReference = (asset: AssemblyAsset) => `${asset.reference!.resource}@${asset.reference!.version} · ${asset.media!.key}`;

function AssemblyPicker({ kind, initial, onConfirm, onClose }: {
  kind: PickerKind; initial: AssemblyAsset[]; onConfirm: (assets: AssemblyAsset[]) => void; onClose: () => void;
}) {
  const { api } = useChloeScope();
  const [draftIds, setDraftIds] = useState(() => initial.map(asset => asset.id));
  const isModel = kind === 'models';
  const isAccessory = kind === 'accessories';
  const form = kind === 'garments' ? '单件' : kind === 'outfits' ? '套装' : null;
  const referenceKind = kind === 'hair' || kind === 'accessories' ? kind : 'clothing';
  const limit = kind === 'garments' ? garmentLimit : isAccessory ? accessoryLimit : 1;
  const label = isModel ? '模特' : form ?? referenceAssetKinds[referenceKind].label;
  const endpoint = isModel ? 'shared-models' : referenceAssetKinds[referenceKind].endpoint;
  const query = useQuery({
    queryKey: isModel ? ['chloe-models', api] : ['chloe-reference-assets', referenceKind, api],
    queryFn: () => get<AssemblyAsset[]>(`${api}/${endpoint}`),
    staleTime: 0,
  });
  const available = query.isFetching || query.error ? undefined : query.data?.filter(asset =>
    asset.status === '可用' && (!form || (asset.clothingForm === form && asset.reference)));
  const { visibleCards, ...filter } = useChloeAccessoryFilter(isAccessory ? available ?? [] : []);
  const selected = draftIds.flatMap(id => {
    const asset = available?.find(item => item.id === id && item.media?.url);
    return asset ? [asset] : [];
  });
  const atLimit = limit > 1 && selected.length >= limit;
  const title = `选择${label} ${selected.length}/${limit}`;
  const canConfirm = !!available && (selected.length > 0 || initial.length > 0);
  const cards = (isAccessory ? visibleCards : available ?? []).map(asset => {
    const checked = selected.some(item => item.id === asset.id);
    return <AssetMediaCard key={asset.id} title={kind === 'garments' ? garmentTitle(asset) : assetTitle(asset)} formal entry aspectRatio="natural" revision={0}
      item={{media: asset.media, emptyLabel: isModel ? '尚未采用正面面部图' : `尚未采用${label}展示图`}}
      selection={{selected: checked, disabled: atLimit && !checked,
        onSelect: () => {
          if (checked) {
            setDraftIds(selected.filter(item => item.id !== asset.id).map(item => item.id));
          } else {
            setDraftIds(limit > 1 ? [...selected.map(item => item.id), asset.id] : [asset.id]);
          }
        }}} />;
  });

  return <AssetSelectionDialog title={title} close={onClose} confirm={() => onConfirm(selected)} confirmDisabled={!canConfirm}
    toolbar={filter.types.length > 0 && <ChloeAccessoryTypes {...filter} />}>
    <Result loading={query.isPending || query.isFetching} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {available && (cards.length ? isAccessory
      ? <ChloeAccessoryColumns cards={cards} />
      : <div className="asset-media-grid">{cards}</div>
      : <p className="muted">暂无可用{label}。</p>)}
  </AssetSelectionDialog>;
}

export function ChloeAssembly({ projectName, renderNavigation }: AssemblyProps) {
  const [params, setParams] = useSearchParams();
  const requestedTab = params.get('assemblyTab');
  const tab = requestedTab === 'video' || requestedTab === 'look' ? requestedTab : 'outfit';
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
    <Activity mode={tab === 'video' ? 'visible' : 'hidden'}>
      <ChloeVideoAssembly projectName={projectName} renderNavigation={navigation} active={tab === 'video'} />
    </Activity>
  </>;
}

function OutfitAssembly({ projectName, renderNavigation }: AssemblyProps) {
  const [garments, setGarments] = useState<AssemblyAsset[]>([]);
  const [handoff, setHandoff] = useState('');
  const [picking, setPicking] = useState(false);
  const [preview, setPreview] = useState<{title: string; src: string} | null>(null);

  const changeSelection = (assets: AssemblyAsset[]) => {
    setGarments(assets);
    setHandoff('');
    setPicking(false);
  };
  const generate = () => setHandoff([
    `请为「${projectName}」用以下单件合成一张套装展示图，套装仅包含服装。`,
    '',
    ...garments.map((asset, index) => `${index + 1}. ${garmentTitle(asset)} · ${clothingReference(asset)}`),
    '',
    '生成前先逐张打开并查看以上准确版本，核对部位重复、叠穿顺序、缺少的衣物及看不清的结构，给出具体搭配建议。若需要更换单件或调整保留范围，先确认方案再生成。',
    '按 Chloe 服装展示图流程制作与送审。登记时将服装形态填为套装，套装来源填为合成，记录各单件的准确输入版本、实际组成和穿法。',
  ].join('\n'));

  return <>
    {renderNavigation(garments.length ? () => changeSelection([]) : undefined)}
    <div className="chloe-assets-content chloe-assembly">
      <section aria-label="单件选择">
        <div className="chloe-assembly-accessory-heading">
          <h2>单件选择 {garments.length}/{garmentLimit}</h2>
          <LinkButton onClick={() => setPicking(true)}>{garments.length ? '编辑单件' : '选择单件'}</LinkButton>
        </div>
        <div className="chloe-assembly-accessories">
          <PreviewContext.Provider value={media => { if (media.url) setPreview({title: media.name, src: media.url}); }}>
            {garments.map(asset => <AssetMediaCard key={asset.id} title={garmentTitle(asset)} formal entry aspectRatio={1} revision={0}
              item={{media: asset.media}} />)}
          </PreviewContext.Provider>
        </div>
      </section>
      <AssemblyExport canGenerate={garments.length > 0} generate={generate} handoff={handoff}
        empty={garments.length ? '点击「生成」，整理套装制作交接词。' : '选定 1–5 项单件后可生成交接词。'} />
      {picking && <AssemblyPicker kind="garments" initial={garments} onConfirm={changeSelection} onClose={() => setPicking(false)} />}
      {preview && <FullscreenImage title={preview.title} src={preview.src} alt={preview.title} close={() => setPreview(null)} />}
    </div>
  </>;
}

function LookAssembly({ projectName, renderNavigation }: AssemblyProps) {
  const { api } = useChloeScope();
  const [model, setModel] = useState<AssemblyAsset | null>(null);
  const [outfit, setOutfit] = useState<AssemblyAsset | null>(null);
  const [hair, setHair] = useState<AssemblyAsset | null>(null);
  const [accessories, setAccessories] = useState<AssemblyAsset[]>([]);
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
      `套装：${assetTitle(outfit)} · ${clothingReference(outfit)}`,
      ...(hair ? [`发型：${assetTitle(hair)}`] : []),
      ...(accessories.length
        ? ['配饰：', ...accessories.map((asset, index) => `${index + 1}. ${assetTitle(asset)}`)]
        : []),
      '',
      '请按对象编号查找各自正式采用的参考图，按取景使用实际入镜的配饰，保持各视角的造型一致。若鞋履、妆发或搭配有需要确认的取舍，先确认再生成。',
      '请按 Chloe 造型流程从造型面部三视图开始，按顺序送审并接续全身定装三视图原图和遮面版。',
    ].join('\n'));
  };

  const confirm = (assets: AssemblyAsset[]) => {
    if (picker === 'models') setModel(assets[0] ?? null);
    if (picker === 'outfits') setOutfit(assets[0] ?? null);
    if (picker === 'hair') setHair(assets[0] ?? null);
    if (picker === 'accessories') setAccessories(assets);
    setHandoff('');
    setPicker(null);
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
          {accessories.map((asset, index) => <AssetMediaCard key={asset.id} title={`配饰 ${index + 1} · ${assetTitle(asset)}`} formal entry aspectRatio={1} revision={0}
            item={{media: asset.media}} />)}
        </PreviewContext.Provider>
        {accessories.length < accessoryLimit && <button type="button" className="chloe-assembly-add" aria-label="添加配饰" onClick={() => setPicker('accessories')}>
          <span aria-hidden="true">+</span>添加配饰
        </button>}
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
