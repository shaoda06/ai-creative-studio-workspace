import { Fragment } from 'react';
import type { ReactNode } from 'react';
import { PointerTooltip } from './PointerTooltip';

export function UnderlineTabs<T extends string>({ items, selected, onChange, label, disabled = false, compact = false, scrollable = false, alignLastToEnd = false, endAction }: {
  items: { value: T; label: string; icon?: ReactNode; tooltip?: string }[];
  selected: T;
  onChange: (value: T) => void;
  label: string;
  disabled?: boolean;
  compact?: boolean;
  scrollable?: boolean;
  alignLastToEnd?: boolean;
  endAction?: ReactNode;
}) {
  return <nav className={`underline-tabs${compact ? ' underline-tabs-compact' : ''}${scrollable ? ' underline-tabs-scroll' : ''}${alignLastToEnd ? ' underline-tabs-align-end' : ''}`} aria-label={label}>
    {items.map((item, index) => <Fragment key={item.value}>
      {alignLastToEnd && index === items.length - 1 && endAction && <span className="underline-tabs-end-action">{endAction}</span>}
      <PointerTooltip text={item.tooltip}><button disabled={disabled} aria-current={selected === item.value ? 'page' : undefined} onClick={() => onChange(item.value)}>{item.icon}{item.label}</button></PointerTooltip>
    </Fragment>)}
  </nav>;
}
