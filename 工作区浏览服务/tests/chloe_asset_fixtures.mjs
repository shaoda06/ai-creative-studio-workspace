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
  if (!params.has('page')) return eligible;
  const type = card => card.type || card.bodyArea;
  const types = [...new Set(eligible.map(type).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
  const active = params.getAll('types');
  const filtered = active.length ? eligible.filter(card => active.includes(type(card))) : eligible;
  const total = filtered.length;
  const page_size = 12;
  const page = Math.min(Number(params.get('page')), Math.max(1, Math.ceil(total / page_size)));
  return {items:filtered.slice((page-1)*page_size,page*page_size),total,page,page_size,types};
}
