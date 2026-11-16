import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { CSSProperties, KeyboardEvent } from 'react';
import { SearchField } from './SearchField';
import './TabSelect.css';

type Props = {
  items: { value: string; label: string; badge?: string; disabled?: boolean }[];
  selected: string;
  onChange: (value: string) => void;
  label: string;
  disabled?: boolean;
  reselect?: boolean;
  iconOnly?: boolean;
  variant?: "default" | "field";
  size?: "default" | "compact" | "small" | "toolbar";
  highlightSelected?: boolean;
};

function menuPosition(trigger: HTMLButtonElement, menu: HTMLDivElement): CSSProperties {
  const rect = trigger.getBoundingClientRect();
  const below = window.innerHeight - rect.bottom - 12;
  const above = rect.top - 12;
  const openAbove = below < 320 && above > below;
  const maxHeight = Math.min(320, openAbove ? above : below);
  menu.style.minWidth = `${Math.min(rect.width, window.innerWidth - 16)}px`;
  menu.style.maxHeight = `${maxHeight}px`;
  const width = menu.getBoundingClientRect().width;
  return { left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
    top: openAbove ? undefined : rect.bottom + 4, bottom: openAbove ? window.innerHeight - rect.top + 4 : undefined, maxHeight };
}

export function TabSelect({ items, selected, onChange, label, disabled, iconOnly, reselect = false, variant = "default", size = "default", highlightSelected = false }: Props) {
  const id = useId();
  const enabledIndices = items.flatMap((item, index) => item.disabled ? [] : [index]);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [active, setActive] = useState(0);
  const [position, setPosition] = useState<CSSProperties>({});
  const positionMenu = useCallback(() => {
    setPosition(menuPosition(trigger.current!, menu.current!));
  }, []);
  useEffect(() => {
    if (!expanded) return;
    window.addEventListener('resize', positionMenu);
    return () => window.removeEventListener('resize', positionMenu);
  }, [expanded, positionMenu]);
  const close = () => { menu.current!.hidePopover(); setExpanded(false); };
  const choose = (index: number) => { const value = items[index].value; close(); trigger.current!.focus(); if (reselect || value !== selected) onChange(value); };
  useEffect(() => {
    if (expanded) menu.current!.children[active]?.scrollIntoView({ block: 'nearest' });
  }, [active, expanded]);
  const keyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!expanded) trigger.current!.click();
      else setActive(index => enabledIndices[(enabledIndices.indexOf(index) + (event.key === 'ArrowDown' ? 1 : -1) + enabledIndices.length) % enabledIndices.length]);
    } else if (expanded && (event.key === 'Home' || event.key === 'End')) {
      event.preventDefault(); setActive(event.key === 'Home' ? enabledIndices[0] : enabledIndices[enabledIndices.length - 1]);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault(); if (expanded) choose(active); else trigger.current!.click();
    } else if (event.key === 'Escape' || event.key === 'Tab') {
      if (expanded) {
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); }
        close();
      }
    }
  };
  return <>
    <button ref={trigger} type="button" className={`tab-select tab-select-marked tab-select-${variant} tab-select-${size}${highlightSelected ? " tab-select-highlight" : ""}${iconOnly ? ' tab-select-icon' : ''}`} role="combobox" aria-label={label}
      aria-haspopup="listbox" aria-controls={id} aria-expanded={expanded} aria-activedescendant={expanded ? `${id}-${active}` : undefined}
      disabled={disabled || enabledIndices.length === 0} data-active={Boolean(selected)} data-value={selected} onKeyDown={keyDown}
      onClick={() => {
        if (expanded) close();
        else {
          menu.current!.showPopover();
          positionMenu();
          const selectedIndex = items.findIndex(item => item.value === selected && !item.disabled);
          setActive(selectedIndex >= 0 ? selectedIndex : enabledIndices[0]);
          setExpanded(true);
        }
      }}>
      {!iconOnly && <span className="tab-select-label">{items.find(item => item.value === selected)?.label || label}{items.find(item => item.value === selected)?.badge && <span className="tab-select-status">{items.find(item => item.value === selected)!.badge}</span>}</span>}
      <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12"><path d="m3 4.5 3 3 3-3" fill="none" stroke="currentColor" /></svg>
    </button>
    <div ref={menu} id={id} popover="auto" role="listbox" aria-label={label} className="tab-select-menu" style={position}
      onToggle={event => setExpanded(event.currentTarget.matches(':popover-open'))}>
      {items.map((item, index) => <button key={item.value} type="button" role="option" id={`${id}-${index}`}
        disabled={item.disabled} aria-selected={item.value === selected} data-active={index === active} tabIndex={-1}
        onMouseEnter={() => { if (!item.disabled) setActive(index); }} onMouseDown={event => event.preventDefault()} onClick={() => choose(index)}>
        <span>{item.label}{item.badge && <span className="tab-select-status">{item.badge}</span>}</span>{item.value === selected && <span className="tab-select-badge">当前</span>}
      </button>)}
    </div>
  </>;
}

export function SearchCreateSelect({ items, selected, label, prompt, searchLabel, disabled, onChange, onCreate }: {
  items: string[]; selected: string; label: string; prompt: string; searchLabel: string; disabled?: boolean;
  onChange: (value: string) => void; onCreate: (value: string) => void;
}) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [position, setPosition] = useState<CSSProperties>({});
  const [input, setInput] = useState('');
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
  return <>
    <button ref={trigger} type="button" aria-label={label} aria-controls={id} aria-expanded={expanded}
      className="tab-select tab-select-marked tab-select-default tab-select-compact" data-active={false} disabled={disabled}
      onClick={() => {
        if (expanded) { close(); return; }
        menu.current!.showPopover();
        reposition();
        menu.current!.querySelector('input')!.focus({ preventScroll: true });
      }}>
      <span className="tab-select-label">{prompt}</span>
      <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12"><path d="m3 4.5 3 3 3-3" fill="none" stroke="currentColor" /></svg>
    </button>
    <div ref={menu} id={id} popover="auto" role="group" aria-label={label} className="tab-select-menu tab-select-menu-search"
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
      <SearchField label={searchLabel} placeholder={searchLabel} size="compact" value={input} onChange={setInput} />
      {matches.length > 0 && <div role="listbox" aria-label={label}>
        {matches.map(item => <button key={item} type="button" role="option" aria-selected={item === selected}
          onClick={() => { close(); if (item !== selected) onChange(item); }}>
          <span>{item}</span>{item === selected && <span className="tab-select-badge">当前</span>}
        </button>)}
      </div>}
      {canCreate && <button type="button" onClick={() => { close(); onCreate(term); }}>新建「{term}」</button>}
    </div>
  </>;
}
