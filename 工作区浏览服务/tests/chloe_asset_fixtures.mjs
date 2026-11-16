export function chloeAssetResponse(url, cards) {
  const params = new URL(url).searchParams;
  const models = params.getAll('models');
  const eligible = cards.filter(card =>
    (!params.has('available') || card.status === '可用') &&
    (!params.has('require_media') || card.media || card.videoUrl) &&
    (!params.has('form') || (params.get('form') === '套装' ? card.clothingForm === '套装' :
      params.has('available') ? card.clothingForm === '单件' : card.clothingForm !== '套装')) &&
    (!models.length || models.some(id => card.models.includes(id))));
  if (params.has('ids')) return params.getAll('ids').flatMap(id => eligible.filter(card => card.id === id));
  const typesOf = card => card.outfitStyles ?? [card.type || card.bodyArea].filter(Boolean);
  const active = params.getAll('types');
  const filtered = active.length ? eligible.filter(card => typesOf(card).some(type => active.includes(type))) : eligible;
  if (!params.has('page')) return filtered;
  const types = [...new Set(eligible.flatMap(typesOf))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
  const total = filtered.length;
  const page_size = Number(params.get('page_size') ?? 12);
  const page = Math.min(Number(params.get('page')), Math.max(1, Math.ceil(total / page_size)));
  return {items:filtered.slice((page-1)*page_size,page*page_size),total,page,page_size,types};
}
