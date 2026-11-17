import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { SearchField } from './SearchField';
import { menuPosition } from './selectMenuPosition';
import './SearchCreateSelect.css';

export function SearchCreateSelect({ items, selected, exclusive, label, prompt, searchLabel, disabled, renderOption, onChange, onCreate }: {
  items: string[]; selected: string[]; exclusive?: string; label: string; prompt: string; searchLabel: string; disabled?: boolean;
  renderOption?: (name: string) => ReactNode; onChange: (values: string[]) => void; onCreate: (name: string, values: string[]) => void;
}) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [position, setPosition] = useState<CSSProperties>({});
  const [input, setInput] = useState('');
  const [draft, setDraft] = useState<string[]>([]);
  const term = input.trim();
  const normalized = term.toLowerCase();
  const matches = items.filter(item => item.toLowerCase().includes(normalized));
  const canCreate = term !== '' && !matches.some(item => item.toLowerCase() === normalized);
  const reposition = useCallback(() => setPosition(menuPosition(trigger.current!, menu.current!)), []);
  useEffect(() => {
    if (!expanded) return;
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition);
    };
  }, [expanded, reposition]);
  const close = () => {
    menu.current!.hidePopover();
    trigger.current!.focus({ preventScroll: true });
  };
  const toggle = (name: string, checked: boolean) => setDraft(values => {
    if (!checked) return values.filter(value => value !== name);
    if (name === exclusive) return [name];
    return [...values.filter(value => value !== exclusive), name];
  });
  return <>
    <button ref={trigger} type="button" aria-label={label} aria-controls={id} aria-expanded={expanded}
      className="search-create-trigger" disabled={disabled}
      onClick={() => {
        if (expanded) { close(); return; }
        setDraft(selected);
        menu.current!.showPopover();
        reposition();
        menu.current!.querySelector('input')!.focus({ preventScroll: true });
      }}>
      {prompt}
      <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12"><path d="m3 4.5 3 3 3-3" fill="none" stroke="currentColor" /></svg>
    </button>
    <div ref={menu} id={id} popover="auto" role="group" aria-label={label} className="search-create-menu"
      style={position} onToggle={event => {
        const open = event.currentTarget.matches(':popover-open');
        setExpanded(open);
        if (!open) setInput('');
      }}
      onKeyDown={event => {
        if (event.nativeEvent.isComposing) return;
        if (event.key === 'Escape') {
          event.preventDefault();
          event.stopPropagation();
          close();
        }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('input, button')];
          const next = controls.indexOf(event.target as HTMLElement) + (event.key === 'ArrowDown' ? 1 : -1);
          controls[(next + controls.length) % controls.length].focus();
          event.preventDefault();
        }
      }}>
      <SearchField label={searchLabel} placeholder={searchLabel} size="compact" focusStyle="inset" value={input} onChange={setInput} />
      <div className="search-create-options">
        {matches.map(item => <label key={item}><input type="checkbox" checked={draft.includes(item)}
          onChange={event => toggle(item, event.target.checked)} />{renderOption ? renderOption(item) : <span>{item}</span>}</label>)}
      </div>
      <div className="search-create-actions">
        {canCreate && <button type="button" className="search-create-new" onClick={() => {
          close();
          onCreate(term, [...draft.filter(value => value !== exclusive), term]);
        }}>新建并应用「{term}」</button>}
        <button type="button" onClick={() => { close(); onChange(draft); }}>应用</button>
      </div>
    </div>
  </>;
}
