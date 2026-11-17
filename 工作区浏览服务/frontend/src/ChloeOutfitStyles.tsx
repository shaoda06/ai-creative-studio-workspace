import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import { get } from './api';
import { useChloeScope } from './chloeScope';
import { Dialog } from './components';
import { useNotify } from './components/Notifications';
import { SearchCreateSelect } from './components/SearchCreateSelect';

const unclassified = '未分类';
const styleTones = ['blue', 'green', 'purple', 'orange', 'teal', 'rose', 'red', 'indigo'] as const;

export function OutfitStyleBadge({ style, catalog }: { style: string; catalog: string[] }) {
  const index = catalog.filter(name => name !== unclassified).indexOf(style);
  const tone = index < 0 ? 'gray' : styleTones[index % styleTones.length];
  return <span className={`status-badge status-${tone} chloe-outfit-style-badge`}>{style}</span>;
}

const stylesKey = (api: string) => ['chloe-outfit-styles', api];
const clothingUrl = (api: string) => `${api}/shared-clothing`;

export function useOutfitStyles(enabled: boolean) {
  const { api } = useChloeScope();
  return useQuery({
    queryKey: stylesKey(api), enabled,
    queryFn: () => get<string[]>(`${clothingUrl(api)}/styles`),
    refetchOnMount: 'always',
  });
}

async function writeStyle<T>(url: string, method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', payload: { style: string; name?: string } | { styles: string[] }): Promise<T> {
  const response = await fetch(url, {
    method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : `保存失败（${response.status}）`);
  }
  return response.json();
}

async function refreshOutfitStyleViews(client: QueryClient, api: string) {
  await Promise.all([
    client.invalidateQueries({ predicate: ({queryKey: [kind, url]}) =>
      (kind === 'chloe-asset-page' || kind === 'chloe-asset-draft') &&
      typeof url === 'string' && url.startsWith(`${clothingUrl(api)}?`) }),
    client.invalidateQueries({ queryKey: ['chloe-reference-detail', 'clothing', api] }),
  ]);
}

async function acceptCatalog(client: QueryClient, api: string, catalog: string[]) {
  const queryKey = stylesKey(api);
  await client.cancelQueries({ queryKey });
  client.setQueryData(queryKey, catalog);
  void client.invalidateQueries({ queryKey });
}

export function OutfitStyleSelect({ id, current, styles }: { id: string; current: string[]; styles: string[] }) {
  const { api } = useChloeScope();
  const client = useQueryClient();
  const notify = useNotify();
  const mutation = useMutation({
    mutationFn: (selected: string[]) => writeStyle<{ outfitStyles: string[] }>(
      `${clothingUrl(api)}/${encodeURIComponent(id)}/style`, 'PUT', { styles: selected }),
    onSuccess: async () => {
      await refreshOutfitStyleViews(client, api);
      notify('已更新套装风格');
    },
    onError: error => notify(error.message, 'error'),
  });
  const createStyle = async (name: string) => {
    try {
      const catalog = await writeStyle<string[]>(`${clothingUrl(api)}/styles`, 'POST', { style: name });
      await acceptCatalog(client, api, catalog);
      return catalog.at(-1)!;
    } catch (error) {
      notify(error instanceof Error ? error.message : '新建风格失败', 'error');
      return null;
    }
  };
  const items = [...new Set([...styles, ...current])];
  const styleBadge = (style: string) => <OutfitStyleBadge style={style} catalog={styles} key={style} />;
  return <div className="chloe-outfit-style-select">
    <div className="chloe-outfit-style-current">{items.filter(style => current.includes(style)).map(styleBadge)}</div>
    <SearchCreateSelect items={items} selected={current} label={`修改 ${id} 的风格`} prompt="搜索或新建风格"
      searchLabel="输入风格名称" disabled={mutation.isPending || styles.length === 0}
      exclusive={unclassified} renderOption={styleBadge} onChange={selected => mutation.mutate(selected)} onCreate={createStyle} />
  </div>;
}

export function OutfitStyleManager({ styles, close, onChange }: {
  styles: string[]; close: () => void; onChange: (style: string, name?: string) => void;
}) {
  const { api } = useChloeScope();
  const client = useQueryClient();
  const notify = useNotify();
  const [action, setAction] = useState<{ style: string; type: 'rename' | 'delete' }>();
  const [input, setInput] = useState('');
  const name = input.trim();
  const mutation = useMutation({
    mutationFn: ({ style, name }: { style: string; name?: string }) => writeStyle<string[]>(
      `${clothingUrl(api)}/styles`, name === undefined ? 'DELETE' : 'PATCH', { style, name }),
    onSuccess: async (catalog, { style, name }) => {
      await acceptCatalog(client, api, catalog);
      onChange(style, name);
      setAction(undefined);
      await refreshOutfitStyleViews(client, api);
      notify(name === undefined ? '已删除风格' : '已重命名风格');
    },
    onError: error => notify(error.message, 'error'),
  });
  const busy = mutation.isPending;
  return <Dialog title="管理套装风格" size="compact" lockPageScroll close={close} closeDisabled={busy}>
    {action?.type === 'rename' ? <form onSubmit={event => {
      event.preventDefault();
      if (!busy && name && name !== action.style) mutation.mutate({ style: action.style, name });
    }}>
      <label className="chloe-outfit-style-rename">风格名称
        <input autoFocus value={input} disabled={busy} onChange={event => setInput(event.target.value)} />
      </label>
      <div className="chloe-outfit-style-manager-actions">
        <button type="button" disabled={busy} onClick={() => setAction(undefined)}>取消</button>
        <button type="submit" disabled={busy || !name || name === action.style}>保存名称</button>
      </div>
    </form> : action?.type === 'delete' ? <>
      <p>删除「{action.style}」后，所有套装都会移除此风格。没有其他风格的套装会归入「未分类」。</p>
      <div className="chloe-outfit-style-manager-actions">
        <button type="button" disabled={busy} onClick={() => setAction(undefined)}>取消</button>
        <button type="button" className="danger-button" disabled={busy} onClick={() => mutation.mutate({ style: action.style })}>确认删除</button>
      </div>
    </> : <ul className="chloe-outfit-style-manager-list">
      {styles.map(style => <li key={style}>
        <OutfitStyleBadge style={style} catalog={styles} />
        {style === unclassified ? <span className="muted">默认风格</span> : <div className="chloe-outfit-style-manager-actions">
          <button type="button" aria-label={`重命名 ${style}`} disabled={busy} onClick={() => {
            setInput(style);
            setAction({ style, type: 'rename' });
          }}>重命名</button>
          <button type="button" className="danger-button" aria-label={`删除 ${style}`} disabled={busy}
            onClick={() => setAction({ style, type: 'delete' })}>删除</button>
        </div>}
      </li>)}
    </ul>}
  </Dialog>;
}
