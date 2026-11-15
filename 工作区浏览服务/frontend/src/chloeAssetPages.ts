import { useLayoutEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query';
import { get } from './api';
import { useChloeScope } from './chloeScope';
import { useNotify } from './components/Notifications';

export const chloeAssetStatusBadges = {
  制作中: { label: '制作中', tone: 'blue' },
  可用: { label: '可用', tone: 'green' },
} as const;
export type ChloeAssetStatus = keyof typeof chloeAssetStatusBadges;

interface AssetPage<T> { items: T[]; total: number; page: number; page_size: number; types: string[] }
interface AssetFilters { available?: boolean; require_media?: boolean; form?: string }

function assetUrl(api: string, endpoint: string, filters: AssetFilters, page?: number, types: string[] = [], ids: string[] = []) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, String(value));
  if (page) params.set('page', String(page));
  for (const type of types) params.append('types', type);
  for (const id of ids) params.append('ids', id);
  return `${api}/${endpoint}?${params}`;
}

export function useAssetPage<T>(endpoint: string, page: number, filters: AssetFilters = {}, types: string[] = [], browse = false) {
  const { api } = useChloeScope();
  const url = assetUrl(api, endpoint, filters, page, types);
  return useQuery({
    queryKey: ['chloe-asset-page', url],
    queryFn: () => get<AssetPage<T>>(url),
    enabled: !!endpoint,
    refetchOnMount: browse ? true : 'always',
    refetchInterval: browse ? 5000 : false,
    placeholderData: keepPreviousData,
  });
}

export function assetPaging<T>(data: AssetPage<T>, change: (page: number) => void) {
  return { page: data.page, pageSize: data.page_size, total: data.total, change, itemLabel: '条资料' };
}

export function assetListParams(params: URLSearchParams) {
  const list = new URLSearchParams({ section: 'assets', asset: params.get('asset') || 'models' });
  for (const key of ['clothingTab', 'assetPage', 'assetType'])
    for (const value of params.getAll(key)) list.append(key, value);
  return list;
}

let previousListScroll: { key: string; top: number } | undefined;

export function useAssetList<T>(endpoint: string, filters: AssetFilters = {}) {
  const { page: path } = useChloeScope();
  const [params, setParams] = useSearchParams();
  const list = assetListParams(params);
  const key = `${path}?${list}`;
  const [filterEdit, setFilterEdit] = useState<{key: string; types: string[]}>();
  const pendingTypes = filterEdit?.key === key ? filterEdit.types : undefined;
  const requested = Number(list.get('assetPage'));
  const page = !pendingTypes && Number.isSafeInteger(requested) && requested > 0 ? requested : 1;
  const types = pendingTypes ?? list.getAll('assetType');
  const query = useAssetPage<T>(endpoint, page, filters, types, true);
  const ready = !!query.data && !query.isPlaceholderData;

  useLayoutEffect(() => { setFilterEdit(undefined); }, [key]);

  useLayoutEffect(() => {
    if (!ready) return;
    const top = previousListScroll?.key === key ? previousListScroll.top : 0;
    const restore = () => window.scrollTo(0, top);
    restore();
    // Natural-size cards grow as their images load after returning from detail.
    const observer = new ResizeObserver(restore);
    if (window.scrollY < top) observer.observe(document.querySelector('.chloe-assets-content')!);
    const remember = () => {
      if (window.scrollY >= top) observer.disconnect();
      previousListScroll = { key, top: window.scrollY };
    };
    const stopRestoring = () => observer.disconnect();
    window.addEventListener('scroll', remember);
    window.addEventListener('wheel', stopRestoring);
    window.addEventListener('pointerdown', stopRestoring);
    window.addEventListener('keydown', stopRestoring);
    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', remember);
      window.removeEventListener('wheel', stopRestoring);
      window.removeEventListener('pointerdown', stopRestoring);
      window.removeEventListener('keydown', stopRestoring);
    };
  }, [key, ready]);

  const changePage = (next: number) => {
    if (next === 1) list.delete('assetPage');
    else list.set('assetPage', String(next));
    setParams(list);
  };
  const setTypeChecked = (type: string, checked: boolean) => {
    const next = checked ? [...types, type] : types.filter(value => value !== type);
    setFilterEdit({ key, types: next });
    list.delete('assetPage');
    list.delete('assetType');
    for (const value of next) list.append('assetType', value);
    setParams(list);
  };
  return { query, list, changePage, setTypeChecked, activeTypes: types };
}

export function useAssetDraft<T extends { id: string }>(endpoint: string, filters: AssetFilters, initialIds: string[], onConfirm: (items: T[]) => void) {
  const { api } = useChloeScope();
  const notify = useNotify();
  const [changed, setChanged] = useState<T[]>();
  const initialUrl = assetUrl(api, endpoint, filters, undefined, [], initialIds);
  const initial = useQuery({
    queryKey: ['chloe-asset-draft', initialUrl],
    queryFn: () => get<T[]>(initialUrl),
    enabled: !!endpoint && initialIds.length > 0,
    refetchOnMount: 'always',
  });
  const selected = changed ?? (initial.isFetching || initial.error ? [] : initial.data ?? []);
  const confirm = useMutation({
    mutationFn: (items: T[]) => items.length
      ? get<T[]>(assetUrl(api, endpoint, filters, undefined, [], items.map(item => item.id)))
      : Promise.resolve([]),
  });
  const confirmSelection = () => confirm.mutate(selected, {
    onSuccess: items => {
      if (items.length === selected.length) onConfirm(items);
      else {
        setChanged(items);
        notify('部分已选资料已不可用，请重新确认选择。', 'error');
      }
    },
    onError: () => notify('无法核对已选资料，请重试。', 'error'),
  });
  return { selected, setSelected: setChanged, initial, confirmSelection, confirming: confirm.isPending };
}
