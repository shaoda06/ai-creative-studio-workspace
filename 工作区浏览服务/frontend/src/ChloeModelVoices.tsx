import { useChloeScope } from './chloeScope';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { get } from './api';
import { Result } from './components';
import { PageCheckStatus } from './components/PageCheckStatus';
import { AudioReferenceCard } from './components/AudioReferenceCard';
import { useAudioPreview } from './components/AudioPreviewButton';
import type { VoiceCard } from './ChloeVoices';

export function useModelVoices(spaceId:string) {
  const { api } = useChloeScope();
  return useQuery({queryKey:['chloe-voices',api],queryFn:()=>get<VoiceCard[]>(`${api}/shared-voices`),refetchInterval:5000});
}

export function ChloeModelVoices({spaceId,modelId}: {spaceId:string;modelId:string}) {
  const { page } = useChloeScope();
  const query=useModelVoices(spaceId);
  const audio=useAudioPreview(true,modelId,0);
  const voices=query.data?.filter(voice=>voice.models.includes(modelId));
  return <section className="panel" aria-label="声音信息"><h2>声音信息</h2>
    <PageCheckStatus queries={[query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {audio.player}
    {voices && (voices.length ? voices.map(voice=><div className="chloe-model-voice" key={voice.id}>
      <dl className="chloe-overview-fields">
        <div><dt>声音名称</dt><dd><Link to={`${page}?section=assets&asset=voices&voice=${encodeURIComponent(voice.id)}`}>{voice.id} · {voice.name}</Link></dd></div>
        <div><dt>声音说明</dt><dd>{voice.description}</dd></div>
      </dl>
      {voice.reference ? <AudioReferenceCard name={`${voice.reference.resource}@${voice.reference.version}`} duration={voice.reference.duration}
        playing={audio.playingId===voice.id} progress={audio.currentId===voice.id ? audio.progress : 0} onPlay={()=>audio.toggle(voice.id,voice.media!.url!)} /> : <p>尚未采用声音参考。</p>}
    </div>) : <p>无</p>)}
  </section>;
}
