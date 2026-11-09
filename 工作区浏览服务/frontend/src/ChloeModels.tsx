import { useChloeScope } from './chloeScope';
import { useModelVoices } from './ChloeModelVoices';
import { AudioPreviewButton, useAudioPreview } from './components/AudioPreviewButton';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';
import { get } from './api';
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
  const { api, page } = useChloeScope();
  const query = useQuery({ queryKey: ['chloe-models', api],
    queryFn: () => get<ModelCard[]>(`${api}/shared-models`), refetchInterval: 5000 });
  const voices=useModelVoices(spaceId!);
  const audio=useAudioPreview(true,spaceId!,0);
  return <>
    {audio.player}
    <PageCheckStatus queries={[workspaceQuery, query, voices]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    <Result loading={false} error={voices.error} retry={voices.refetch} retrying={voices.isFetching} />
    {query.data && (query.data.length ? <div className="asset-media-grid">
      {query.data.map(model => <AssetMediaCard key={model.id} title={`${model.id} · ${model.name}`} formal entry aspectRatio="natural" revision={0}
        titleActions={voices.data?.filter(voice=>voice.models.includes(model.id)).length
          ? voices.data.filter(voice=>voice.models.includes(model.id)).map(voice=><AudioPreviewButton key={voice.id} name={`${model.name} · ${voice.name}`} enabled={!!voice.media}
              playing={audio.playingId===voice.id} progress={audio.currentId===voice.id ? audio.progress : 0} onClick={()=>audio.toggle(voice.id,voice.media!.url!)} />)
          : <AudioPreviewButton name={model.name} enabled={false} playing={false} progress={0} onClick={()=>{}} />}
        to={`${page}?section=assets&asset=models&model=${encodeURIComponent(model.id)}`}
        item={{ media: model.media, emptyLabel: '尚未采用正面面部图' }} />)}
    </div> : <p className="muted">暂无模特资料。建立模特资料后，每个模特会在这里显示为一张卡片。</p>)}
  </>;
}
