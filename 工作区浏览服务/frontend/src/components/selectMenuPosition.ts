import type { CSSProperties } from 'react';

export function menuPosition(trigger: HTMLButtonElement, menu: HTMLDivElement): CSSProperties {
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
