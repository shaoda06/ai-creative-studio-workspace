import { assetPaging, useAssetList } from './chloeAssetPages';
import { Pagination } from './components/Pagination';
import { useChloeScope } from './chloeScope';
import { useModelVoices } from './ChloeModelVoices';
import { AudioPreviewButton, useAudioPreview } from './components/AudioPreviewButton';
import { useParams } from 'react-router-dom';
import type { UseQueryResult } from '@tanstack/react-query';
import type { FileItem, WorkspaceSpace } from './api';
import { Result } from './components';
import { AssetMediaCard } from './components/AssetMediaCard';
import { PageCheckStatus } from './components/PageCheckStatus';

interface ModelCard {
  id: string;
  name: string;
  identity: Record<string, string>;
  features: Record<string, string>;
  media: FileItem | null;
  version: string | null;
}

export function ChloeModels({ workspaceQuery }: { workspaceQuery: UseQueryResult<WorkspaceSpace[]> }) {
  const { spaceId } = useParams();
  const { page } = useChloeScope();
  const { query, list, changePage } = useAssetList<ModelCard>('shared-models');
  const data = query.isPlaceholderData ? undefined : query.data;
  const voices = useModelVoices(data?.items.map(model => model.id) ?? []);
  const audio=useAudioPreview(true,spaceId!,0);
  return <>
    {audio.player}
    <PageCheckStatus queries={[workspaceQuery, query, voices]} />
    <Result loading={query.isPending || query.isPlaceholderData} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    <Result loading={false} error={voices.error} retry={voices.refetch} retrying={voices.isFetching} />
    {data && (data.items.length ? <div className="asset-media-grid">
      {data.items.map(model => <AssetMediaCard key={model.id} title={`${model.id} · ${model.name}`} formal entry aspectRatio="natural" revision={0}
        titleActions={voices.data?.filter(voice=>voice.models.includes(model.id)).length
          ? voices.data.filter(voice=>voice.models.includes(model.id)).map(voice=><AudioPreviewButton key={voice.id} name={`${model.name} · ${voice.name}`} enabled={!!voice.media}
              playing={audio.playingId===voice.id} progress={audio.currentId===voice.id ? audio.progress : 0} onClick={()=>audio.toggle(voice.id,voice.media!.url!)} />)
          : <AudioPreviewButton name={model.name} enabled={false} playing={false} progress={0} onClick={()=>{}} />}
        to={`${page}?${list}&model=${encodeURIComponent(model.id)}`}
        item={{ media: model.media, emptyLabel: '尚未采用正面面部图' }} />)}
    </div> : <p className="muted">暂无模特资料。建立模特资料后，每个模特会在这里显示为一张卡片。</p>)}
    {data && <Pagination {...assetPaging(data, changePage)} />}
  </>;
}
