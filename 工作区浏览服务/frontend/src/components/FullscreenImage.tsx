import type { ReactNode } from 'react';
import { Dialog } from '../components';
import './FullscreenImage.css';

export function FullscreenImage({ title, src, alt, close, children }: { title: string; src: string; alt: string; close: () => void; children?: ReactNode }) {
  return <Dialog size="fullscreen" showHeader={false} title={title} close={close}>
    <div className="fullscreen-image">
      <button className="fullscreen-image-close" aria-label="退出全屏看图" onClick={close}><img src={src} alt={alt} /></button>
      {children}
    </div>
  </Dialog>;
}
