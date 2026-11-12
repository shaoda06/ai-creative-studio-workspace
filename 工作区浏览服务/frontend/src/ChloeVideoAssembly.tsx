import { useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem } from './api';
import { useChloeScope } from './chloeScope';
import type { ModelDetail } from './ChloeModelDetail';
import type { ReferenceVideoCard, ReferenceVideoDetail } from './ChloeReferenceVideos';
import { Dialog, Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { FullscreenImage } from './components/FullscreenImage';
import { LinkButton } from './components/LinkButton';
import { ReleaseFilmPlayer } from './components/ReleaseFilms';
import { AssemblyExport, AssemblyPreview, assetTitle } from './ChloeAssemblyParts';
import type { OpenImage } from './ChloeAssemblyParts';

type NamedAsset = { id: string; name: string };
type ImageAsset = NamedAsset & { status: '制作中' | '可用'; media: FileItem | null };
type LookImage = ModelDetail['looks'][number]['images'][number];
type Selection =
  | { kind: 'video'; asset: ReferenceVideoCard }
  | { kind: 'look'; asset: NamedAsset; model: NamedAsset; image: LookImage }
  | { kind: 'scene'; asset: ImageAsset };
type PickerKind = Selection['kind'];
const labels = { video: '参考视频', look: '造型图', scene: '背景' };

function VideoAssemblyPicker({ kind, initial, onConfirm, onClose, onPreview }: {
  kind: PickerKind; initial: Selection | null; onConfirm: (selection: Selection) => void; onClose: () => void; onPreview: OpenImage;
}) {
  const { api } = useChloeScope();
  const [modelId, setModelId] = useState(initial?.kind === 'look' ? initial.model.id : null);
  const [draftId, setDraftId] = useState(initial?.asset.id ?? null);
  const videos = useQuery({ queryKey: ['chloe-reference-videos', api],
    queryFn: () => get<ReferenceVideoCard[]>(`${api}/shared-reference-videos`), enabled: kind === 'video' });
  const scenes = useQuery({ queryKey: ['chloe-reference-assets', 'scenes', api],
    queryFn: () => get<ImageAsset[]>(`${api}/shared-scenes`), enabled: kind === 'scene' });
  const models = useQuery({ queryKey: ['chloe-models', api],
    queryFn: () => get<ImageAsset[]>(`${api}/shared-models`), enabled: kind === 'look' });
  const availableModels = (models.data ?? []).filter(asset => asset.status === '可用');
  const model = models.error ? undefined : availableModels.find(asset => asset.id === modelId);
  const looks = useQuery({ queryKey: ['chloe-model', api, model?.id],
    queryFn: () => get<ModelDetail>(`${api}/shared-models/${encodeURIComponent(model!.id)}`), enabled: kind === 'look' && !!model });
  const selectingModel = kind === 'look' && !model;
  const query = kind === 'video' ? videos : kind === 'scene' ? scenes : selectingModel ? models : looks;
  const label = selectingModel ? '模特' : labels[kind];

  const card = (asset: NamedAsset, media: FileItem | null, onSelect: () => void, selected = false, previewImage = false) => {
    const title = assetTitle(asset);
    const url = media?.url;
    return <AssetMediaCard key={asset.id} title={title} formal entry aspectRatio={kind === 'video' ? 3 / 4 : 'natural'} revision={0}
      item={{ media, emptyLabel: '尚未采用正面面部图' }} selection={{ selected, onSelect,
        onPreview: previewImage && url ? () => onPreview(title, url) : undefined }} />;
  };
  const choices: Selection[] = kind === 'video' ? (videos.data ?? []).filter(asset => asset.status === '可用').map(asset => ({ kind: 'video', asset }))
    : kind === 'scene' ? (scenes.data ?? []).filter(asset => asset.status === '可用' && asset.media?.url).map(asset => ({ kind: 'scene', asset }))
    : model ? (looks.data?.looks ?? []).filter(asset => asset.status === '可用').flatMap(asset => {
      const image = asset.images.find(item => item.adopted && item.purpose === '全身三视图原图' && item.media.url);
      return image ? [{ kind: 'look', model, asset, image }] : [];
    }) : [];
  const draft = choices.find(choice => choice.asset.id === draftId);
  const cards = selectingModel ? availableModels.map(asset => card(asset, asset.media, () => {
    setDraftId(initial?.kind === 'look' && initial.model.id === asset.id ? initial.asset.id : null);
    setModelId(asset.id);
  })) : choices.map(choice => {
    const media = choice.kind === 'video' ? { kind: 'image', key: choice.asset.id, url: choice.asset.coverUrl, name: `${choice.asset.name}的首帧` }
      : choice.kind === 'look' ? choice.image.media : choice.asset.media;
    return card(choice.asset, media, () => setDraftId(choice.asset.id), draft === choice, choice.kind !== 'video');
  });

  return <Dialog title={model ? `选择造型图 · ${assetTitle(model)}` : `选择${label}`} close={onClose} lockPageScroll>
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {query.data && (cards.length ? <div className="asset-media-grid">{cards}</div> : <p className="muted">暂无可选{label}。</p>)}
    {!selectingModel && <div className="chloe-assembly-confirm">
      {model && <LinkButton onClick={() => setModelId(null)}>返回模特列表</LinkButton>}
      <button type="button" disabled={!draft || !query.data || !!query.error} onClick={() => onConfirm(draft!)}>确认选择</button>
    </div>}
  </Dialog>;
}

export function ChloeVideoAssembly({ projectName, renderNavigation, active }: {
  projectName: string; renderNavigation: (reset?: () => void) => ReactNode; active: boolean;
}) {
  const { api } = useChloeScope();
  const [video, setVideo] = useState<Extract<Selection, { kind: 'video' }> | null>(null);
  const [look, setLook] = useState<Extract<Selection, { kind: 'look' }> | null>(null);
  const [scene, setScene] = useState<Extract<Selection, { kind: 'scene' }> | null>(null);
  const [requirements, setRequirements] = useState('');
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
      `造型图：全身定装三视图原图（${look.image.resource}@${look.image.version}）`,
      `造型图文件：${look.image.media.key}`,
      ...(scene ? [`背景：${assetTitle(scene.asset)}`, `背景图文件：${scene.asset.media?.key}`] : ['背景：沿用参考视频的场景。']),
      `额外要求：${requirements.trim() || '无。'}`,
      '',
      '按参考视频的镜头顺序、构图、运镜、人物动作和节奏复刻，由所选模特出镜，保持造型图中的妆发与穿搭一致。已选背景时，按背景图还原场景并匹配镜头透视和光线。',
    ].join('\n'));
  };
  const confirm = (selection: Selection) => {
    if (selection.kind === 'video') setVideo(selection);
    if (selection.kind === 'look') setLook(selection);
    if (selection.kind === 'scene') setScene(selection);
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
      <section className="chloe-video-assembly-choice" aria-label="参考视频选择">
        <h2>参考视频</h2>
        <button type="button" aria-label="选择参考视频" onClick={() => setPicker('video')}>{video ? assetTitle(video.asset) : '选择参考视频'}</button>
        <div className="chloe-video-assembly-preview">
          {active && reference && !videoQuery.error ? <ReleaseFilmPlayer key={reference.media.url} item={reference.media} /> : video ?
            <Result loading={videoQuery.isPending} error={videoQuery.error} retry={videoQuery.refetch} retrying={videoQuery.isFetching} /> :
            <span className="muted">请选择参考视频</span>}
        </div>
      </section>
      <section className="chloe-video-assembly-choice" aria-label="造型图选择">
        <h2>造型图</h2>
        <button type="button" aria-label="选择造型图" onClick={() => setPicker('look')}>{look ? `${assetTitle(look.model)} / ${assetTitle(look.asset)}` : '选择造型图'}</button>
        <AssemblyPreview label="全身定装三视图原图" media={look?.image.media} empty="请选择模特和造型" onPreview={openImage} />
      </section>
      <AssemblyExport canGenerate={canGenerate} generate={generate} handoff={handoff}
        empty={canGenerate ? '点击「生成」，整理当前装配的复刻提示词。' : '选定参考视频和造型图后可生成提示词。'}>
        <label className="chloe-video-assembly-requirements">额外要求（可选）
          <textarea rows={3} value={requirements} onChange={event => { setRequirements(event.target.value); setHandoff(''); }} />
        </label>
      </AssemblyExport>
      <section className="chloe-video-assembly-choice" aria-label="背景选择">
        <div className="chloe-assembly-export-heading">
          <h2>背景 <small>可选</small></h2>
          {scene && <LinkButton onClick={() => { setScene(null); setHandoff(''); }}>清除背景</LinkButton>}
        </div>
        <button type="button" aria-label="选择背景" onClick={() => setPicker('scene')}>{scene ? assetTitle(scene.asset) : '选择背景'}</button>
        <AssemblyPreview label="背景图" media={scene?.asset.media} empty="沿用参考视频的场景" onPreview={openImage} />
      </section>
      {picker && <VideoAssemblyPicker kind={picker} initial={picker === 'video' ? video : picker === 'look' ? look : scene}
        onConfirm={confirm} onClose={() => setPicker(null)} onPreview={openImage} />}
      {preview && <FullscreenImage title={preview.title} src={preview.src} alt={preview.title} close={() => setPreview(null)} />}
    </div>
  </>;
}
