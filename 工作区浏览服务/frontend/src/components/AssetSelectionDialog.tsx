import type { ReactNode } from 'react';
import { Dialog } from '../components';
import './AssetSelectionDialog.css';

export function AssetSelectionDialog({ title, close, children, confirm, confirmDisabled = false, actions, stickyFooter = false }: {
  title: string; close: () => void; children: ReactNode; confirm?: () => void;
  confirmDisabled?: boolean; actions?: ReactNode; stickyFooter?: boolean;
}) {
  return <Dialog title={title} close={close} lockPageScroll>
    {children}
    {confirm && <div className={stickyFooter ? 'asset-selection-footer asset-selection-footer-sticky' : 'asset-selection-footer'}>
      {actions}
      <button type="button" disabled={confirmDisabled} onClick={confirm}>确认选择</button>
    </div>}
  </Dialog>;
}
