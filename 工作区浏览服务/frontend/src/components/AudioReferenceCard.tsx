import { AudioPreviewButton } from './AudioPreviewButton';
import { PointerTooltip } from './PointerTooltip';
import './AudioReferenceCard.css';

export function AudioReferenceCard({name,duration,playing,progress,onPlay}: {
  name:string; duration:number|null; playing:boolean; progress:number; onPlay:()=>void;
}) {
  const seconds=duration===null ? null : Math.round(duration*100)/100;
  const label=seconds===null ? '未取得' : seconds>60
    ? `${seconds}秒（${Math.floor(seconds/60)}分${Math.round(seconds%60*100)/100}秒）` : `${seconds}秒`;
  return <article className="audio-reference-card" aria-label={name}>
    <div className="audio-reference-card-heading">
      <PointerTooltip text={name}><h3>{name}</h3></PointerTooltip>
      <AudioPreviewButton name={name} enabled playing={playing} progress={progress} onClick={onPlay} />
    </div>
    <span className="audio-reference-card-duration">时长：{label}</span>
  </article>;
}
