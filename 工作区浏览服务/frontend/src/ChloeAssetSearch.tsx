import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { get } from './api';
import { useChloeScope } from './chloeScope';
import { Result } from './components';
import { SearchField } from './components/SearchField';
import './ChloeAssetSearch.css';

interface SearchMatch {
  id: string;
  name: string;
  category: string;
  params: Record<string, string>;
  previewUrl: string | null;
}

export function ChloeAssetSearch() {
  const { api, page } = useChloeScope();
  const [value, setValue] = useState('');
  const [open, setOpen] = useState(false);
  const [settled, setSettled] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const results = useRef<HTMLElement>(null);
  const hovered = useRef<{ row: HTMLAnchorElement; url: string } | null>(null);
  const [preview, setPreview] = useState<{ url: string; top: number; left: number } | null>(null);
  const prefix = value.trim().toLowerCase();
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(prefix), 180);
    return () => window.clearTimeout(timer);
  }, [prefix]);
  const ready = open && !!prefix && settled === prefix;
  const query = useQuery({
    queryKey: ['chloe-asset-search', api, settled],
    queryFn: () => get<SearchMatch[]>(`${api}/shared-asset-search?${new URLSearchParams({ q: settled })}`),
    enabled: ready,
  });
  const clearPreview = () => {
    hovered.current = null;
    setPreview(null);
  };
  const positionPreview = () => {
    if (!hovered.current) return;
    const { row, url } = hovered.current;
    const bounds = row.getBoundingClientRect();
    const list = results.current!.getBoundingClientRect();
    const field = root.current!.getBoundingClientRect();
    setPreview(bounds.bottom > list.top && bounds.top < list.bottom
      ? { url, top: bounds.top - field.top, left: list.right - field.left + 8 }
      : null);
  };
  return <div ref={root} className="chloe-asset-search" onFocus={() => setOpen(true)}
    onBlur={event => {
      if (!event.currentTarget.contains(event.relatedTarget)) { setOpen(false); clearPreview(); }
    }}
    onKeyDown={event => { if (event.key === 'Escape') { setOpen(false); clearPreview(); } }}>
    <SearchField size="compact" label="搜索共用资产编号" placeholder="搜索编号，如 O001"
      value={value} onChange={next => { setValue(next); setOpen(true); clearPreview(); }} />
    {open && prefix && <section ref={results} className="chloe-asset-search-results" aria-label="资产搜索结果" tabIndex={-1}
      onScroll={positionPreview}>
      <Result loading={!ready || query.isPending} error={ready ? query.error : null} retry={query.refetch} retrying={query.isFetching} />
      {ready && query.data && (query.data.length ? <ul>
        {query.data.map(match => {
          const params = new URLSearchParams({ section: 'assets', ...match.params });
          return <li key={params.toString()}><Link to={`${page}?${params}`}
            onMouseEnter={event => {
              if (!match.previewUrl) return;
              hovered.current = { row: event.currentTarget, url: match.previewUrl };
              positionPreview();
            }}
            onMouseLeave={clearPreview}
            onClick={() => { setValue(''); setOpen(false); clearPreview(); }}>
            <span>{match.id} · {match.name}</span><small>{match.category}</small>
          </Link></li>;
        })}
      </ul> : <p className="muted" role="status">未找到匹配的资产编号。</p>)}
    </section>}
    {ready && preview && <img key={preview.url} className="chloe-asset-search-preview" src={preview.url} alt=""
      style={{ top: preview.top, left: preview.left }} onError={clearPreview} />}
  </div>;
}
