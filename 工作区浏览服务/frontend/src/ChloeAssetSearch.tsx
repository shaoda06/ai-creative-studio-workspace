import { useEffect, useState } from 'react';
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
}

export function ChloeAssetSearch() {
  const { api, page } = useChloeScope();
  const [value, setValue] = useState('');
  const [open, setOpen] = useState(false);
  const [settled, setSettled] = useState('');
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
  return <div className="chloe-asset-search" onFocus={() => setOpen(true)}
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}
    onKeyDown={event => { if (event.key === 'Escape') setOpen(false); }}>
    <SearchField size="compact" label="搜索共用资产编号" placeholder="搜索编号，如 O001"
      value={value} onChange={next => { setValue(next); setOpen(true); }} />
    {open && prefix && <section className="chloe-asset-search-results" aria-label="资产搜索结果" tabIndex={-1}>
      <Result loading={!ready || query.isPending} error={ready ? query.error : null} retry={query.refetch} retrying={query.isFetching} />
      {ready && query.data && (query.data.length ? <ul>
        {query.data.map(match => {
          const params = new URLSearchParams({ section: 'assets', ...match.params });
          return <li key={params.toString()}><Link to={`${page}?${params}`} onClick={() => { setValue(''); setOpen(false); }}>
            <span>{match.id} · {match.name}</span><small>{match.category}</small>
          </Link></li>;
        })}
      </ul> : <p className="muted" role="status">未找到匹配的资产编号。</p>)}
    </section>}
  </div>;
}
