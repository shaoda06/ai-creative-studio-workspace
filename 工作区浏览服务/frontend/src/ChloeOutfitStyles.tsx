import { useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { get } from './api';
import { useChloeScope } from './chloeScope';
import { Dialog } from './components';
import { useNotify } from './components/Notifications';
import { TabSelect } from './components/TabSelect';

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

async function writeStyle<T>(url: string, method: 'POST' | 'PUT', style: string): Promise<T> {
  const response = await fetch(url, {
    method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ style }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : `保存失败（${response.status}）`);
  }
  return response.json();
}

export function AddOutfitStyleDialog({ close }: { close: () => void }) {
  const { api } = useChloeScope();
  const client = useQueryClient();
  const notify = useNotify();
  const nameId = useId();
  const [name, setName] = useState('');
  const mutation = useMutation({
    mutationFn: (style: string) => writeStyle<string[]>(`${clothingUrl(api)}/styles`, 'POST', style),
    onSuccess: async styles => {
      await client.cancelQueries({ queryKey: stylesKey(api) });
      client.setQueryData(stylesKey(api), styles);
      close();
      notify('已新增风格');
    },
    onError: error => notify(error.message, 'error'),
  });
  return <Dialog title="新增风格" close={close} closeDisabled={mutation.isPending}>
    <form className="chloe-outfit-style-form" onSubmit={event => {
      event.preventDefault();
      if (name.trim() && !mutation.isPending) mutation.mutate(name.trim());
    }}>
      <label htmlFor={nameId}>风格名称</label>
      <input id={nameId} value={name} required disabled={mutation.isPending} onChange={event => setName(event.target.value)} />
      <button type="submit" disabled={!name.trim() || mutation.isPending}>{mutation.isPending ? '正在新增…' : '新增'}</button>
    </form>
  </Dialog>;
}

export function OutfitStyleSelect({ id, current, styles }: { id: string; current: string; styles: string[] }) {
  const { api } = useChloeScope();
  const client = useQueryClient();
  const notify = useNotify();
  const mutation = useMutation({
    mutationFn: (style: string) => writeStyle<{ outfitStyle: string }>(`${clothingUrl(api)}/${encodeURIComponent(id)}/style`, 'PUT', style),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['chloe-asset-page'], predicate: query => {
          const url = query.queryKey[1];
          return typeof url === 'string' && url.startsWith(`${clothingUrl(api)}?`);
        } }),
        client.invalidateQueries({ queryKey: ['chloe-reference-detail', 'clothing', api, id] }),
      ]);
      notify('已更新套装风格');
    },
    onError: error => notify(error.message, 'error'),
  });
  const items = [...new Set([current, ...styles])].map(value => ({ value, label: value }));
  return <div className="chloe-outfit-style-select">
    <span>风格</span>
    <TabSelect items={items} selected={current} label={`修改 ${id} 的风格`}
      disabled={mutation.isPending || styles.length === 0} onChange={value => mutation.mutate(value)} size="small" />
  </div>;
}
