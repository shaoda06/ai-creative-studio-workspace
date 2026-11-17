import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { get } from './api';
import { useChloeScope } from './chloeScope';
import { useNotify } from './components/Notifications';
import { SearchCreateSelect } from './components/SearchCreateSelect';

const unclassified = '未分类';
const styleTones = ['blue', 'green', 'purple', 'orange', 'teal', 'rose', 'red', 'indigo'] as const;

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

async function writeStyle<T>(url: string, method: 'POST' | 'PUT', payload: { style: string } | { styles: string[] }): Promise<T> {
  const response = await fetch(url, {
    method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === 'string' ? error.detail : `保存失败（${response.status}）`);
  }
  return response.json();
}

export function OutfitStyleSelect({ id, current, styles }: { id: string; current: string[]; styles: string[] }) {
  const { api } = useChloeScope();
  const client = useQueryClient();
  const notify = useNotify();
  const mutation = useMutation({
    mutationFn: async ({ selected, create }: { selected: string[]; create?: string }) => {
      if (create) {
        const catalog = await writeStyle<string[]>(`${clothingUrl(api)}/styles`, 'POST', { style: create });
        await client.cancelQueries({ queryKey: stylesKey(api) });
        client.setQueryData(stylesKey(api), catalog);
      }
      try {
        await writeStyle<{ outfitStyles: string[] }>(`${clothingUrl(api)}/${encodeURIComponent(id)}/style`, 'PUT', { styles: selected });
      } catch (error) {
        if (create && error instanceof Error) throw new Error(`已新增风格。应用到套装失败：${error.message}`);
        throw error;
      }
    },
    onSuccess: async (_, { create }) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['chloe-asset-page'], predicate: query => {
          const url = query.queryKey[1];
          return typeof url === 'string' && url.startsWith(`${clothingUrl(api)}?`);
        } }),
        client.invalidateQueries({ queryKey: ['chloe-reference-detail', 'clothing', api, id] }),
      ]);
      notify(create ? '已新增并应用风格' : '已更新套装风格');
    },
    onError: error => notify(error.message, 'error'),
  });
  const items = [...new Set([...styles, ...current])];
  const catalog = styles.filter(style => style !== unclassified);
  const styleBadge = (style: string) => {
    const index = catalog.indexOf(style);
    const tone = index < 0 ? 'gray' : styleTones[index % styleTones.length];
    return <span className={`status-badge status-${tone}`} key={style}>{style}</span>;
  };
  return <div className="chloe-outfit-style-select">
    <div className="chloe-outfit-style-current">{current.map(styleBadge)}</div>
    <SearchCreateSelect items={items} selected={current} label={`修改 ${id} 的风格`} prompt="搜索或新建风格"
      searchLabel="输入风格名称" disabled={mutation.isPending || styles.length === 0}
      exclusive={unclassified} renderOption={styleBadge} onChange={selected => mutation.mutate({ selected })}
      onCreate={(create, selected) => mutation.mutate({ selected, create })} />
  </div>;
}
