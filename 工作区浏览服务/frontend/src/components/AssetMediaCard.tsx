import { Link } from 'react-router-dom';
import { PointerTooltip } from './PointerTooltip';
import { useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { RecordData } from '../api';
import { PreviewContext, Rich } from '../components';
import { FileActions } from './FileActions';

export function AssetMediaCard({ title, item, revision, formal = false, compact = false, entry = false, hideTitle = false, showFileActions = true, showVersion = true, aspectRatio, to, titleActions, onDetails, children }: { title: string; item: RecordData; revision: number; formal?: boolean; compact?: boolean; entry?: boolean; hideTitle?: boolean; showFileActions?: boolean; showVersion?: boolean; aspectRatio?: number | 'natural'; to?: string; titleActions?: ReactNode; onDetails?: () => void; children?: ReactNode }) {
  const preview = useContext(PreviewContext);
  const [dimensions, setDimensions] = useState('');
  const recordLink = item.recordUrl ? <a href={item.recordUrl} onClick={event => {
        event.preventDefault();
        preview({ kind: 'markdown', name: item.generation || '生成记录', key: decodeURIComponent(item.recordUrl.split('/files/')[1]), url: item.recordUrl });
      }}>{formal ? '生成记录' : item.generation}</a> : null;
  const version = formal ? item.version?.match(/v\d+(?:\.\d+)*/i)?.[0] : item.version || item.media?.key.match(/(?:候选|草稿)-(v\d+(?:\.\d+)*)/i)?.[1];
  const linked = entry && to;
  const linkedActions = linked && !!titleActions;
  const Cover = linked ? 'div' : 'button';
  const fixedRatioStyle = typeof aspectRatio === 'number' ? { aspectRatio, height: 'auto' } : undefined;
  const naturalRatio = aspectRatio === 'natural';
  const imageStyle = naturalRatio ? { height: 'auto', maxHeight: 'none' } : fixedRatioStyle && { maxHeight: 'none' };
  const className = `asset-media-card${compact ? ' asset-media-card-compact' : ''}${entry ? ' asset-media-card-entry' : ''}${linkedActions ? ' asset-media-card-linked-actions' : ''}`;
  const content = <>
    {!hideTitle && (titleActions ? <div className="asset-media-card-heading">
      <PointerTooltip text={title}><h3>{linkedActions ? <Link to={to!} aria-label={title} className="asset-media-card-title-link">{title}</Link> : title}</h3></PointerTooltip>
      <div className="asset-media-card-title-actions">{titleActions}</div>
    </div> : <PointerTooltip text={title}><h3>{title}</h3></PointerTooltip>)}
    <div className="asset-media-item">
      {item.media ? <Cover style={naturalRatio ? { height: 'auto' } : fixedRatioStyle} className="cover" onClick={linked ? undefined : () => preview(item.media)}><img style={imageStyle} className="reference" loading="lazy" src={item.media.url + `?v=${revision}`} alt={item.media.name} onLoad={compact || entry ? undefined : event => {
        const { naturalWidth: width, naturalHeight: height } = event.currentTarget;
        setDimensions(`${width} × ${height}`);
      }} /></Cover> : <div style={fixedRatioStyle} className="cover asset-media-placeholder">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8" cy="8" r="1.5" /><path d="m3 17 6-6 4 4 3-3 5 5" /></svg>
        <span>{item.emptyLabel || '已登记，图片文件缺失。'}</span>
      </div>}
      {!entry && <>
      {!compact && item.media && <p className="asset-media-field"><span className="field-label">尺寸：</span>{dimensions || '读取中'}</p>}
      {showFileActions && !compact && item.media && !onDetails && <div className="asset-media-field file-entry-main"><span className="field-label">文件：</span><FileActions url={item.media.url} /></div>}
      {showVersion && version ? <p className="asset-media-field"><span className="field-label">{compact ? '资源版本' : formal ? '采用版本' : '版本'}：</span>{version}</p> : null}
      {!compact && <>
      {Object.entries(item).filter(([key, content]) => key.endsWith('Html') && !['fileCheckHtml', 'visionScopeHtml', 'visionFindingsHtml'].includes(key) && (!formal || key === 'statusHtml') && typeof content === 'string' && content).map(([key, content]) => <div key={key} className="asset-media-html-field"><p className="field-label">{({ statusHtml: '状态', sourceHtml: '来源', userHtml: '用户决定', userReasonHtml: '原因与依据', agentHtml: '历史初审', technicalHtml: '技术审查', contentHtml: '内容审查', contentFindingsHtml: '审查发现', versionHtml: '采用版本' } as Record<string, string>)[key] || key.replace('Html', '')}：</p><Rich html={String(content)} /></div>)}
      {(formal ? ['scope'] : ['scope', 'retentionPurpose', 'pendingLabel', 'userState']).map(key => item[key] && <p key={key} className={`asset-media-field${key === 'scope' ? ' asset-media-scope' : ''}`}><span className="field-label">{({ scope: '适用范围', retentionPurpose: '留存用途', pendingLabel: '留存状态', userState: '用户决定' } as Record<string, string>)[key]}：</span>{item[key]}</p>)}
      {!formal && item.generation && <p className="asset-media-field"><span className="field-label">生成记录：</span>{recordLink || item.generation}</p>}
      {((formal && recordLink) || onDetails) && <div className="asset-media-footer">{formal && recordLink}{onDetails && <button className="asset-media-details" onClick={onDetails}>查看详情</button>}</div>}
      </>}
      </>}
    </div>
    {children}
  </>;
  return linked && !linkedActions ? <Link className={`${className} asset-media-card-link`} to={to!} aria-label={title}>{content}</Link> : <article className={className} aria-label={hideTitle ? title : undefined}>{content}</article>;
}
