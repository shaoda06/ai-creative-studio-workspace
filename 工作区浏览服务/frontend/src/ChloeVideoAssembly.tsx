import { useId, useState } from 'react';
import type { ReactNode } from 'react';
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
import { AssemblyExport, AssemblyPreview, assetTitle } from './ChloeAssemblyParts';
import type { OpenImage } from './ChloeAssemblyParts';

type NamedAsset = { id: string; name: string };
type ImageAsset = NamedAsset & { status: '制作中' | '可用'; media: FileItem | null };
type LookAsset = ModelDetail['looks'][number];
type LookImage = LookAsset['images'][number];
type Selection =
  | { kind: 'video'; asset: ReferenceVideoCard }
  | { kind: 'look'; asset: Pick<LookAsset, 'id' | 'name' | 'media'>; model: NamedAsset; face: LookImage; masked: LookImage }
  | { kind: 'scene'; asset: ImageAsset };
type PickerKind = Selection['kind'];
const labels = { video: '参考视频', look: '造型图', scene: '背景' };
const faceLabel = '造型面部三视图';
const maskedLabel = '全身定装三视图遮面版';

function VideoAssemblyPicker({ kind, initial, onConfirm, onClose }: {
  kind: PickerKind; initial: Selection | null; onConfirm: (selection: Selection | null) => void; onClose: () => void;
}) {
  const { api } = useChloeScope();
  const [modelId, setModelId] = useState(initial?.kind === 'look' ? initial.model.id : null);
  const [draftId, setDraftId] = useState(initial?.asset.id ?? null);
  const videos = useQuery({ queryKey: ['chloe-reference-videos', api],
    queryFn: () => get<ReferenceVideoCard[]>(`${api}/shared-reference-videos`), enabled: kind === 'video', staleTime: 0 });
  const scenes = useQuery({ queryKey: ['chloe-reference-assets', 'scenes', api],
    queryFn: () => get<ImageAsset[]>(`${api}/shared-scenes`), enabled: kind === 'scene', staleTime: 0 });
  const models = useQuery({ queryKey: ['chloe-models', api],
    queryFn: () => get<ImageAsset[]>(`${api}/shared-models`), enabled: kind === 'look', staleTime: 0 });
  const availableModels = models.isFetching || models.error ? [] : (models.data ?? []).filter(asset => asset.status === '可用');
  const model = availableModels.find(asset => asset.id === modelId);
  const looks = useQuery({ queryKey: ['chloe-model', api, model?.id],
    queryFn: () => get<ModelDetail>(`${api}/shared-models/${encodeURIComponent(model!.id)}`), enabled: kind === 'look' && !!model, staleTime: 0 });
  const selectingModel = kind === 'look' && !model;
  const query = kind === 'video' ? videos : kind === 'scene' ? scenes : selectingModel ? models : looks;
  const ready = !!query.data && !query.isFetching && !query.error;
  const label = selectingModel ? '模特' : labels[kind];

  const card = (asset: NamedAsset, media: FileItem | null, onSelect: () => void, selected = false) =>
    <AssetMediaCard key={asset.id} title={assetTitle(asset)} formal entry aspectRatio={kind === 'video' ? 3 / 4 : 'natural'} revision={0}
      item={{ media, emptyLabel: '尚未采用正面面部图' }} selection={{ selected, onSelect }} />;
  const choices: Selection[] = kind === 'video' ? (videos.data ?? []).filter(asset => asset.status === '可用').map(asset => ({ kind: 'video', asset }))
    : kind === 'scene' ? (scenes.data ?? []).filter(asset => asset.status === '可用' && asset.media?.url).map(asset => ({ kind: 'scene', asset }))
    : model ? (looks.data?.looks ?? []).filter(asset => asset.status === '可用').flatMap(asset => {
      const face = asset.images.find(item => item.adopted && item.purpose === faceLabel && item.media.url);
      const masked = asset.images.find(item => item.adopted && item.purpose === '全身三视图遮面版' && item.media.url);
      return face && masked ? [{ kind: 'look', model, asset, face, masked }] : [];
    }) : [];
  const draft = choices.find(choice => choice.asset.id === draftId);
  const cards = selectingModel ? availableModels.map(asset => card(asset, asset.media, () => {
    setDraftId(initial?.kind === 'look' && initial.model.id === asset.id ? initial.asset.id : null);
    setModelId(asset.id);
  })) : choices.map(choice => {
    const media = choice.kind === 'video' ? { kind: 'video', key: choice.asset.id, url: choice.asset.videoUrl, thumbnailUrl: choice.asset.coverUrl, name: choice.asset.name }
      : choice.asset.media;
    return card(choice.asset, media, () => setDraftId(id => id === choice.asset.id ? null : choice.asset.id), draft === choice);
  });

  return <AssetSelectionDialog title={`选择${label} ${ready && draft ? 1 : 0}/1${model ? ` · ${assetTitle(model)}` : ''}`} close={onClose}
    confirm={selectingModel ? undefined : () => onConfirm(draft ?? null)} confirmDisabled={!ready || (!draft && !initial)}
    actions={model && <LinkButton onClick={() => setModelId(null)}>返回模特列表</LinkButton>}>
    <Result loading={query.isPending || query.isFetching} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {ready && (cards.length ? <div className="asset-media-grid">{cards}</div> : <p className="muted">暂无可选{label}。</p>)}
  </AssetSelectionDialog>;
}

export function ChloeVideoAssembly({ projectName, renderNavigation, active }: {
  projectName: string; renderNavigation: (reset?: () => void) => ReactNode; active: boolean;
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
      `视频文件：${reference.media.key}`,
      `出镜模特：${assetTitle(look.model)}`,
      `造型：${assetTitle(look.asset)}`,
      `${faceLabel}：${look.face.resource}@${look.face.version}`,
      `${faceLabel}文件：${look.face.media.key}`,
      `${maskedLabel}：${look.masked.resource}@${look.masked.version}`,
      `${maskedLabel}文件：${look.masked.media.key}`,
      ...(scene ? [`背景：${assetTitle(scene.asset)}`, `背景图文件：${scene.asset.media?.key}`] : ['背景：沿用参考视频的场景。']),
      `额外要求：${requirements.trim() || '无。'}`,
      '',
      '按参考视频的镜头顺序、构图、运镜、人物动作和节奏复刻，由所选模特出镜。五官与妆发参考造型面部三视图，身形与穿搭参考全身定装三视图遮面版。已选背景时，按背景图还原场景并匹配镜头透视和光线。',
    ].join('\n'));
  };
  const confirm = (selection: Selection | null) => {
    if (picker === 'video') setVideo(selection?.kind === 'video' ? selection : null);
    if (picker === 'look') setLook(selection?.kind === 'look' ? selection : null);
    if (picker === 'scene') setScene(selection?.kind === 'scene' ? selection : null);
    setHandoff('');
    setPicker(null);
  };
  const reset = () => {
    setVideo(null);
    setLook(null);
    setScene(null);
    setRequirements('');
    setHandoff('');
  };

  return <>
    {renderNavigation(video || look || scene || requirements ? reset : undefined)}
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
  </>;
}
