import { assetPaging, useAssetDraft, useAssetPage } from './chloeAssetPages';
import { useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem } from './api';
import { useChloeScope } from './chloeScope';
import type { ModelDetail } from './ChloeModelDetail';
import type { ReferenceVideoCard, ReferenceVideoDetail } from './ChloeReferenceVideos';
import { Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { AssetSelectionDialog } from './components/AssetSelectionDialog';
import { FullscreenImage } from './components/FullscreenImage';
import { LinkButton } from './components/LinkButton';
import { ReleaseFilmPlayer } from './components/ReleaseFilms';
import { AssemblyExport, AssemblyPagination, AssemblyPreview, assetTitle } from './ChloeAssemblyParts';
import type { OpenImage } from './ChloeAssemblyParts';

type NamedAsset = { id: string; name: string };
type ImageAsset = NamedAsset & { status: '制作中' | '可用'; media: FileItem | null };
type LookAsset = ModelDetail['looks'][number];
type LookImage = LookAsset['images'][number];
type Selection =
  | { kind: 'video'; asset: ReferenceVideoCard }
  | { kind: 'look'; asset: Pick<LookAsset, 'id' | 'name' | 'media'>; model: NamedAsset; face: LookImage; masked: LookImage }
  | { kind: 'scene'; asset: ImageAsset };
type PickerCard = ReferenceVideoCard | ImageAsset | (Pick<LookAsset, 'id' | 'name' | 'media'> & { face: LookImage; masked: LookImage });
type PickerKind = Selection['kind'];
const labels = { video: '参考视频', look: '造型图', scene: '背景' };
const faceLabel = '造型面部三视图';
const maskedLabel = '全身定装三视图遮面版';

function VideoAssemblyPicker({ kind, initial, onConfirm, onClose }: {
  kind: PickerKind; initial: Selection | null; onConfirm: (selection: Selection | null) => void; onClose: () => void;
}) {
  const [model, setModel] = useState<NamedAsset | null>(initial?.kind === 'look' ? initial.model : null);
  if (kind === 'look' && !model) {
    return <VideoAssemblyChoices key="models" endpoint="shared-models" label="模特" onClose={onClose}
      selectingModel={asset => setModel(asset)} />;
  }
  const endpoint = model ? `shared-models/${encodeURIComponent(model.id)}/assembly-looks`
    : kind === 'video' ? 'shared-reference-videos' : 'shared-scenes';
  return <VideoAssemblyChoices key={endpoint} endpoint={endpoint} label={labels[kind]} model={model}
    initialId={initial?.kind !== 'look' || initial.model.id === model?.id ? initial?.asset.id : undefined}
    back={model ? () => setModel(null) : undefined} onClose={onClose} onConfirm={asset => {
      if (!asset) onConfirm(null);
      else if ('face' in asset) onConfirm({kind: 'look', model: model!, asset, face: asset.face, masked: asset.masked});
      else if ('videoUrl' in asset) onConfirm({kind: 'video', asset});
      else onConfirm({kind: 'scene', asset});
    }} />;
}

function VideoAssemblyChoices({ endpoint, label, model, initialId, back, onClose, onConfirm, selectingModel }: {
  endpoint: string; label: string; model?: NamedAsset | null; initialId?: string; back?: () => void;
  onClose: () => void; onConfirm?: (asset: PickerCard | null) => void; selectingModel?: (asset: NamedAsset) => void;
}) {
  const [page, setPage] = useState(1);
  const filters = { available: true, require_media: true };
  const query = useAssetPage<PickerCard>(endpoint, page, filters);
  const draft = useAssetDraft<PickerCard>(endpoint, filters, initialId ? [initialId] : [], items => onConfirm!(items[0] ?? null));
  const selected = draft.selected[0];
  const ready = !!query.data && !query.isFetching && !query.error && !draft.initial.isFetching && !draft.initial.error;
  const failed = query.error ? query : draft.initial;
  const cards = ready ? query.data!.items.map(asset => {
    const video = 'videoUrl' in asset;
    const media: FileItem | null = video ? { kind: 'video', key: asset.id, url: asset.videoUrl, thumbnailUrl: asset.coverUrl, name: asset.name } : asset.media;
    return <AssetMediaCard key={asset.id} title={assetTitle(asset)} entry formal revision={0} aspectRatio={video ? 3 / 4 : 'natural'}
      item={{ media, emptyLabel: '尚未采用正面面部图' }}
      selection={{ selected: selected?.id === asset.id, disabled: draft.confirming, onSelect: () => {
        if (selectingModel) selectingModel(asset);
        else draft.setSelected(selected?.id === asset.id ? [] : [asset]);
      } }} />;
  }) : [];
  return <AssetSelectionDialog title={`选择${label} ${selected ? 1 : 0}/1${model ? ` · ${assetTitle(model)}` : ''}`} close={onClose}
    confirm={onConfirm && draft.confirmSelection}
    confirmDisabled={!ready || draft.confirming || (!selected && !initialId)}
    actions={back && <LinkButton onClick={back}>返回模特列表</LinkButton>}>
    <Result loading={query.isFetching || draft.initial.isFetching} error={failed.error} retry={failed.refetch} retrying={failed.isFetching} />
    {ready && (cards.length ? <div className="asset-media-grid">{cards}</div> : <p className="muted">暂无可选{label}。</p>)}
    {ready && <AssemblyPagination {...assetPaging(query.data!, setPage)} />}
  </AssetSelectionDialog>;
}

export function ChloeVideoAssembly({ projectName, active }: {
  projectName: string; active: boolean;
}) {
  const { api } = useChloeScope();
  const [video, setVideo] = useState<Extract<Selection, { kind: 'video' }> | null>(null);
  const [look, setLook] = useState<Extract<Selection, { kind: 'look' }> | null>(null);
  const [scene, setScene] = useState<Extract<Selection, { kind: 'scene' }> | null>(null);
  const [requirements, setRequirements] = useState('');
  const requirementsId = useId();
  const [handoff, setHandoff] = useState('');
  const [picker, setPicker] = useState<PickerKind | null>(null);
  const [preview, setPreview] = useState<{ title: string; src: string } | null>(null);
  const openImage: OpenImage = (title, src) => setPreview({ title, src });
  const videoId = video?.asset.id;
  const videoQuery = useQuery({ queryKey: ['chloe-reference-video', api, videoId],
    queryFn: () => get<ReferenceVideoDetail>(`${api}/shared-reference-videos/${encodeURIComponent(videoId!)}`),
    enabled: active && !!videoId });
  const reference = videoQuery.data;
  const canGenerate = !!(reference?.status === '可用' && look && !videoQuery.error);

  const generate = () => {
    if (!reference || !look) return;
    setHandoff([
      `请在「${projectName}」用以下素材复刻参考视频。`,
      '',
      `参考视频：${assetTitle(reference)}`,
      `出镜模特：${assetTitle(look.model)}`,
      `造型：${assetTitle(look.asset)}`,
      scene ? `背景：${assetTitle(scene.asset)}` : '背景：沿用参考视频的场景。',
      `额外要求：${requirements.trim() || '无。'}`,
      '',
      `按编号和标题查找参考视频的已登记播放版本，以及该造型正式采用的${faceLabel}和${maskedLabel}。`,
      `按参考视频的镜头顺序、构图、运镜、人物动作和节奏复刻，由所选模特出镜。五官与妆发参考${faceLabel}，身形与穿搭参考${maskedLabel}。`,
      ...(scene ? ['按编号和标题查找该背景正式采用的场景展示图，还原场景并匹配镜头透视和光线。'] : []),
    ].join('\n'));
  };
  const confirm = (selection: Selection | null) => {
    if (picker === 'video') setVideo(selection?.kind === 'video' ? selection : null);
    if (picker === 'look') setLook(selection?.kind === 'look' ? selection : null);
    if (picker === 'scene') setScene(selection?.kind === 'scene' ? selection : null);
    setHandoff('');
    setPicker(null);
  };
  return (
    <div className="chloe-assets-content chloe-assembly chloe-video-assembly">
      <div className="chloe-video-assembly-inputs">
        <section className="chloe-video-assembly-choice" aria-label="参考视频选择">
          <h2>参考视频 {video ? 1 : 0}/1</h2>
          <button type="button" aria-label="选择参考视频" onClick={() => setPicker('video')}>{video ? assetTitle(video.asset) : '选择参考视频'}</button>
          <figure className="chloe-assembly-preview chloe-video-assembly-preview">
            <figcaption>参考视频</figcaption>
            {active && reference && !videoQuery.error ? <ReleaseFilmPlayer key={reference.media.url} item={reference.media} /> : video ?
              <Result loading={videoQuery.isPending} error={videoQuery.error} retry={videoQuery.refetch} retrying={videoQuery.isFetching} /> :
              <span className="muted">请选择参考视频</span>}
          </figure>
        </section>
        <section className="chloe-video-assembly-choice" aria-label="造型图选择">
          <h2>造型图 {look ? 1 : 0}/1</h2>
          <button type="button" aria-label="选择造型图" onClick={() => setPicker('look')}>{look ? `${assetTitle(look.model)} / ${assetTitle(look.asset)}` : '选择造型图'}</button>
          <div className="chloe-video-assembly-look-images">
            <AssemblyPreview label={faceLabel} media={look?.face.media} empty="请选择模特和造型" onPreview={openImage} />
            <AssemblyPreview label={maskedLabel} media={look?.masked.media} empty="请选择模特和造型" onPreview={openImage} />
          </div>
        </section>
        <section className="chloe-video-assembly-choice" aria-label="背景选择">
          <div className="chloe-assembly-export-heading">
            <h2>背景 {scene ? 1 : 0}/1 <small>可选</small></h2>
            {scene && <LinkButton onClick={() => { setScene(null); setHandoff(''); }}>清除背景</LinkButton>}
          </div>
          <button type="button" aria-label="选择背景" onClick={() => setPicker('scene')}>{scene ? assetTitle(scene.asset) : '选择背景'}</button>
          <AssemblyPreview label="背景图" media={scene?.asset.media} empty="沿用参考视频的场景" onPreview={openImage} />
        </section>
      </div>
      <div className="chloe-video-assembly-output">
        <section aria-label="额外要求">
          <h2><label htmlFor={requirementsId}>额外要求（可选）</label></h2>
          <textarea id={requirementsId} rows={3} value={requirements} onChange={event => { setRequirements(event.target.value); setHandoff(''); }} />
        </section>
        <AssemblyExport canGenerate={canGenerate} generate={generate} handoff={handoff}
          empty={canGenerate ? '点击「生成」，整理当前装配的复刻提示词。' : '选定参考视频和造型图后可生成提示词。'} />
      </div>
      {picker && <VideoAssemblyPicker kind={picker} initial={picker === 'video' ? video : picker === 'look' ? look : scene}
        onConfirm={confirm} onClose={() => setPicker(null)} />}
      {preview && <FullscreenImage title={preview.title} src={preview.src} alt={preview.title} close={() => setPreview(null)} />}
    </div>
  );
}
