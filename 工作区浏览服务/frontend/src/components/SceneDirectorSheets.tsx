import { FullscreenImage } from './FullscreenImage';
import { useProductionAccess } from './ProductionAccess';
import { useContext, useState } from 'react';
import type { DirectorSheetImage, DirectorSheets } from '../api';
import { PreviewContext } from '../components';
import { FileActions } from './FileActions';
import { Pagination } from './Pagination';
import { TabNav } from './TabNav';
import { TabSelect } from './TabSelect';
import './SceneDirectorSheets.css';

export interface DirectorSheetScene {
  id: string;
  sheets?: DirectorSheets;
  storyboardVersion: string;
}

export function SceneDirectorSheets({ sheets, storyboardVersion = '', scenes, sceneId = '', integrated = false, onIntegratedChange, revision }: {
  sheets?: DirectorSheets; storyboardVersion?: string; scenes?: DirectorSheetScene[];
  sceneId?: string; integrated?: boolean; onIntegratedChange?: (value: boolean) => void; revision: number;
}) {
  const access = useProductionAccess();
  const workMode = access.unitKind === 'work';
  const preview = useContext(PreviewContext);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [pageKey, setPageKey] = useState(`${sceneId}/`);
  const [fullscreen, setFullscreen] = useState(false);
  const [scope, setScope] = useState('round');
  const history = scope === 'history';
  const combine = integrated && (scenes?.length || 0) > 1;
  const versionKey = (item: DirectorSheetImage) => history ? `${item.sourceVersion}/${item.version}` : item.version;
  const groups = (scenes ? scenes.filter(scene => combine || scene.id === sceneId) : [{ id: '', sheets, storyboardVersion }]).map(scene => {
    const sourceKey = `${scene.id}/${scene.storyboardVersion}${history ? '/history' : ''}`;
    const registered = scene.sheets?.candidates || [];
    const candidates = history
      ? [...registered.filter(item => !item.sourceVersion || item.sourceVersion !== scene.storyboardVersion), ...(scene.sheets?.history || [])]
      : registered.filter(item => scene.storyboardVersion && item.sourceVersion === scene.storyboardVersion && item.candidateNumber);
    const versions = [...new Set(candidates.map(versionKey))].sort((a, b) =>
      (candidates.find(item => versionKey(item) === b)?.candidateNumber || 0)
      - (candidates.find(item => versionKey(item) === a)?.candidateNumber || 0));
    const options = versions.map(version => {
      const pages = candidates.filter(item => versionKey(item) === version);
      const adopted = pages.filter(item => item.adopted).length;
      const first = pages[0];
      const title = history ? `${first.sourceVersion ? '分镜 ' + first.sourceVersion : '来源分镜未标注'} · 导演表 ${first.version}`
        : `候选${first.candidateNumber}`;
      return { value: version, label: `${title}（${pages.length}张）`,
        badge: adopted === pages.length ? '已采用' : adopted ? '部分已采用' : undefined };
    });
    const selected = options.some(item => item.value === choices[sourceKey]) ? choices[sourceKey]
      : options.find(item => item.badge)?.value || options[0]?.value || '';
    const images = candidates.filter(item => versionKey(item) === selected).sort((a, b) => a.page - b.page).map(item =>
      item.adopted ? scene.sheets!.formal.find(formal => formal.sourceVersion === item.sourceVersion
        && formal.version === item.version && formal.page === item.page)! : item);
    return { ...scene, sourceKey, options, selected, images };
  });
  const pages = groups.flatMap(group => group.images.map((image, index) => ({
    key: `${group.id}/${image.page}`, image, group, index,
  })));
  const exactIndex = pages.findIndex(item => item.key === pageKey);
  const pageIndex = exactIndex >= 0 ? exactIndex : Math.max(0, pages.findIndex(item => item.group.id === pageKey.split('/')[0]));
  const current = pages[pageIndex];
  const active = current?.group || groups[0];
  const record = current?.image.sourceRecord || active?.sheets?.record;
  const selectPage = (page: number) => setPageKey(pages[page - 1].key);
  const count = `${combine ? (workMode ? '整片' : '整集') : ''}第${pageIndex + 1}页 / 共${pages.length}页`;
  const sceneCount = current && combine ? ` · ${current.group.id} 第${current.index + 1}页 / 共${current.group.images.length}页` : '';
  const emptyMessage = (group: typeof groups[number]) => <p className="muted">
    {combine && `场次 ${group.id}：`}
    {history ? '暂无已登记的历史导演分镜表。' : !group.storyboardVersion ? '尚未登记来源分镜版本。'
      : `分镜 ${group.storyboardVersion} 暂无对应导演分镜表。`}
  </p>;
  return <section aria-label={workMode ? '本片导演分镜表' : combine ? '整集导演分镜表' : '本场导演分镜表'}>
    <div className="toolbar director-sheet-toolbar">
      <div className="director-sheet-choice">
        <TabNav compact scrollable label="导演分镜表范围" items={[{ value: 'round', label: '当轮' }, { value: 'history', label: '历史版本' }]}
          selected={scope} onChange={value => { setScope(value); setPageKey(`${sceneId}/`); }} />
        {onIntegratedChange && (scenes?.length || 0) > 1 && <label className="director-sheet-integrate"><input type="checkbox" checked={combine} onChange={event => {
          setPageKey(event.target.checked ? current?.key || `${sceneId}/` : `${sceneId}/`);
          onIntegratedChange(event.target.checked);
        }} />{workMode ? "整合本片" : "整合本集"}</label>}
        {combine && <span className="director-sheet-source">场次 {active.id}</span>}
        {!!active?.options.length && <TabSelect highlightSelected label={history ? '历史导演分镜表版本' : '导演分镜表候选'} selected={active.selected} onChange={value => {
          setChoices(previous => ({ ...previous, [active.sourceKey]: value })); setPageKey(`${active.id}/`);
        }} items={active.options} />}
      </div>
      {current && <div className="director-sheet-pages"><TabNav compact scrollable label="导演分镜表页码"
        items={pages.map((item, index) => ({ value: item.key, label: String(index + 1) }))}
        selected={current.key} onChange={setPageKey} /></div>}
      {(record || current) && <div className="director-sheet-record">
        {record && <button className="link" onClick={() => preview(record)}>查看记录</button>}
        {current && <FileActions url={current.image.url} downloadOnly downloadLabel="下载原图" />}
      </div>}
    </div>
    {current ? <>
      <div className="director-sheet-viewer">
        <button className="director-sheet-image" aria-label={`全屏查看第${String(pageIndex + 1).padStart(2, '0')}页导演分镜表`} onClick={() => setFullscreen(true)}>
          <img src={current.image.url + `?v=${revision}`} alt={current.image.name} />
        </button>
        <Pagination variant="arrows" page={pageIndex + 1} total={pages.length} pageSize={1} change={selectPage} />
      </div>
      {fullscreen && <FullscreenImage title={`导演分镜表 · ${count}${sceneCount}`} src={current.image.url + `?v=${revision}`} alt={current.image.name} close={() => setFullscreen(false)}>
        <Pagination variant="arrows" page={pageIndex + 1} total={pages.length} pageSize={1} change={selectPage} />
      </FullscreenImage>}
    </> : active ? emptyMessage(active) : <div className="scene-empty" role="status"><h3>暂无导演分镜表</h3></div>}
    {combine && groups.filter(group => !group.images.length && group !== active).map(group => <div key={group.id}>
      {emptyMessage(group)}
      {group.sheets?.record && <button className="link" onClick={() => preview(group.sheets!.record!)}>查看 {group.id} 生成与审阅记录</button>}
    </div>)}
  </section>;
}
