import type { ReactNode } from 'react';
import { Dialog } from '../components';

export function AssetSelectionDialog({ title, close, children, confirm, confirmDisabled = false, actions, toolbar }: {
  title: string; close: () => void; children: ReactNode; confirm?: () => void;
  confirmDisabled?: boolean; actions?: ReactNode; toolbar?: ReactNode;
}) {
  return <Dialog title={title} close={close} lockPageScroll headerToolbar={toolbar}
    headerBeforeClose={confirm ? <>{actions}<button type="button" disabled={confirmDisabled} onClick={confirm}>确认选择</button></> : actions}>
    {children}
  </Dialog>;
}
