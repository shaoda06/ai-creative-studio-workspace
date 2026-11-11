import { useContext } from 'react';
import type { GenerationContext } from '../api';
import { FileActions, PreviewContext } from '../components';

export function SegmentReferences({ context, segmentOnly = false }: {
  context?: Pick<GenerationContext, 'references' | 'issues'>;
  segmentOnly?: boolean;
}) {
  const preview = useContext(PreviewContext);
  const groups = segmentOnly ? ['segment'] as const : ['common', 'segment'] as const;
  return <section className="segment-references" aria-label="参考素材区域">
    {context ? groups.map(group => <div className={`segment-reference-group is-${group}`} key={group}>
      <h3>{group === 'common' ? '公共参考素材' : segmentOnly ? '本段参考素材' : '本组参考素材'}</h3>
      <div className="segment-reference-images">{context.references[group].map((material, index) => <figure key={index}>
        <figcaption>{material.label}</figcaption>
        {material.url ? <button className="reference-preview" onClick={() => preview({ kind: material.kind, name: material.name, url: material.url })} aria-label={`查看 ${material.label} ${material.name}`}>
          {material.kind === 'image' ? <img src={material.url} alt={material.name} loading="lazy" /> : material.kind === 'video' ? <><video src={material.url} muted preload="metadata" /><span className="reference-media-label">视频 ▶</span></> : <span className="reference-audio"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18V5l12-2v13M9 9l12-2" fill="none" stroke="currentColor" strokeWidth="2" /><circle cx="6" cy="18" r="3" fill="currentColor" /><circle cx="18" cy="16" r="3" fill="currentColor" /></svg><span>音频</span></span>}
        </button> : <p className="muted">原素材缺失</p>}
        {material.kind === 'video' && <FileActions url={material.url} downloadOnly />}
      </figure>)}{!context.references[group].length && <p className="muted">{context.issues.length ? '该次参考素材关联尚未完整记录。' : segmentOnly ? '本段未使用参考素材。' : '该次未使用此类参考素材。'}</p>}</div>
    </div>) : <span className="placeholder-label">{segmentOnly ? '本段参考素材' : '参考素材区域'}</span>}
  </section>;
}
