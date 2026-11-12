import type { FileItem } from './api';
import { CopyButton } from './components/CopyButton';

export type OpenImage = (title: string, src: string) => void;
export const assetTitle = (asset: { id: string; name: string }) => `${asset.id} · ${asset.name}`;

export function AssemblyPreview({ label, media, empty, onPreview }: { label: string; media?: FileItem | null; empty: string; onPreview: OpenImage }) {
  return <figure className="chloe-assembly-preview">
    <figcaption>{label}</figcaption>
    {media?.url ? <button type="button" aria-label={`查看${label}大图`} onClick={() => onPreview(label, media.url!)}>
      <img src={media.thumbnailUrl || media.url} alt={label} loading="lazy" />
    </button> : <span className="muted">{empty}</span>}
  </figure>;
}

export function AssemblyExport({ canGenerate, generate, handoff, empty }: {
  canGenerate: boolean; generate: () => void; handoff: string; empty: string;
}) {
  return <section aria-label="导出">
    <div className="chloe-assembly-export-heading">
      <h2>导出</h2>
      <div className="chloe-assembly-export-actions">
        <button type="button" disabled={!canGenerate} onClick={generate}>生成</button>
        {handoff ? <CopyButton label="复制" text={handoff} /> : <button type="button" disabled>复制</button>}
      </div>
    </div>
    <p className="chloe-assembly-export-template">{handoff || <span className="muted">{empty}</span>}</p>
  </section>;
}
