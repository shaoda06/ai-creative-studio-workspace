import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { get } from './api';
import type { FileItem } from './api';
import { FileLink, Preview, PreviewContext, Result, Rich } from './components';
import { UnderlineTabs } from './components/UnderlineTabs';
import { TabSelect } from './components/TabSelect';
import { LinkButton } from './components/LinkButton';
import { PageCheckStatus } from './components/PageCheckStatus';
import { useChloeScope } from './chloeScope';
import './ChloeReview.css';

type RecordRow = { id: string; source: string; fields: Record<string, string>; html: Record<string, string>;
  references: { label: string; key: string; section: string; field: string }[] };
type Sample = { id: string; rows: RecordRow[] };
type Video = { project: string; id: string; title: string; status: string; source: string; cover: string | null;
  samples: Sample[]; reviews: RecordRow[]; publications: RecordRow[] };
type Trial = RecordRow & { origin: RecordRow | null };
type ReviewData = { videos: Video[]; conclusions: RecordRow[]; trials: Trial[] };
const tabs = [{ value: 'single', label: '单条复盘' }, { value: 'cross', label: '跨视频结论' }, { value: 'trials', label: '建议验证' }];
const metricFields = ['指标名称', '指标值', '单位', '统计口径', '来源'];
const summary = (text: string) => text.replace(/\[([^\]]+)\]\(<[^>]+>\)/g, '$1').replace(/<br\s*\/?>/gi, ' ');

function Fields({ row, names }: { row: RecordRow; names: string[] }) {
  return <>{names.map(name => <section key={name} aria-label={name}><h3>{name}</h3><Rich html={row.html[name]} /></section>)}</>;
}

export function ChloeReview() {
  const { api } = useChloeScope();
  const [params, setParams] = useSearchParams();
  const [preview, setPreview] = useState<FileItem | null>(null);
  const query = useQuery({ queryKey: ['chloe-reviews', api], queryFn: () => get<ReviewData>(`${api}/reviews`), refetchInterval: 5000 });
  const tab = tabs.find(item => item.value === params.get('reviewTab'))?.value || 'single';
  const data = query.data;
  const filter = params.get('adoption') || '';
  const videos = data?.videos || [];
  const conclusions = data?.conclusions || [];
  const trials = data?.trials.filter(row => !filter || row.fields['采用状态'] === filter) || [];
  const video = videos.find(v => v.project === params.get('video')) || videos[0];
  const conclusion = conclusions.find(r => r.id === params.get('review')) || conclusions[0];
  const trial = trials.find(r => r.id === params.get('trial')) || trials[0];
  const single = video?.reviews.find(r => r.id === params.get('review')) || video?.reviews.at(-1);
  const analysisRefs = single?.references.filter(ref => ['内容判断', '局限'].includes(ref.field)) || [];
  const linkedIds = single?.fields['采集编号'].split('、') || [];
  const sample = video?.samples.find(s => s.id === params.get('sample')) || video?.samples.filter(s => linkedIds.includes(s.id)).at(-1) || video?.samples.at(-1);
  const publications = video?.publications.filter(p => sample?.rows.some(r => r.fields['发布编号'] === p.id)) || [];
  function select(values: Record<string, string>) {
    setParams({ section: 'review', reviewTab: tab, ...values });
  }
  function openOrigin(origin: RecordRow) {
    const owner = videos.find(v => v.source === origin.source);
    select(owner ? { reviewTab: 'single', video: owner.project, review: origin.id } : { reviewTab: 'cross', review: origin.id });
  }
  function open(file: FileItem) {
    const [key, fragment] = (file.key || '').split('#');
    const section = decodeURIComponent(fragment || '');
    const owner = videos.find(v => v.source === key);
    if (owner && section === '效果数据' && owner.samples.some(s => s.id === file.name)) {
      select({ reviewTab: 'single', video: owner.project, sample: file.name });
    } else if (owner && section === '单条复盘' && owner.reviews.some(r => r.id === file.name)) {
      select({ reviewTab: 'single', video: owner.project, review: file.name });
    } else if (key === '综合资料/运营复盘.md' && section === '建议验证' && data?.trials.some(r => r.id === file.name)) {
      select({ reviewTab: 'trials', trial: file.name });
    } else setPreview(file);
  }
  function related(row: RecordRow) {
    const matches = data!.trials.filter(t => t.origin?.id === row.id && t.origin.source === row.source);
    return matches.length > 0 && <section aria-label="对应建议验证"><h3>对应建议验证</h3><div className="chloe-review-actions">{matches.map(t =>
      <LinkButton key={t.id} onClick={() => select({ reviewTab: 'trials', trial: t.id })}>{t.id} · {t.fields['采用状态']}</LinkButton>)}</div></section>;
  }
  return <PreviewContext value={open}>
    <UnderlineTabs label="运营复盘分类" items={tabs} selected={tab} onChange={value => select({ reviewTab: value })} />
    <PageCheckStatus queries={[query]} />
    <Result loading={query.isPending} error={query.error} retry={query.refetch} retrying={query.isFetching} />
    {data && <div className="chloe-review-layout">
      <aside className="chloe-review-list" aria-label={tabs.find(item => item.value === tab)!.label + '列表'}>
        {tab === 'single' && (videos.length ? videos.map(item => <button key={item.project} className="chloe-review-card" aria-pressed={video?.project === item.project}
          onClick={() => select({ video: item.project })}>
          {item.cover && <img className="chloe-review-thumb" src={item.cover} alt={`${item.id} 封面`} />}
          <span className="chloe-review-card-text"><strong>{item.id} · {item.title}</strong><span>{item.status}</span>
            <span>{item.samples.length ? `${item.samples.length} 次数据采集` : '暂无效果数据'} · {item.reviews.length ? `${item.reviews.length} 条复盘` : '暂无复盘'}</span></span>
        </button>) : <p className="muted">暂无视频项目。</p>)}
        {tab === 'cross' && (conclusions.length ? conclusions.map(row => <button key={row.id} className="chloe-review-card" aria-pressed={conclusion?.id === row.id} onClick={() => select({ review: row.id })}>
          <span className="chloe-review-card-text"><strong>{row.id}</strong><span className="chloe-review-summary">{summary(row.fields['结论'])}</span>
            <span>{Array.from(new Set(row.references.filter(r => r.field === '视频与证据').map(r => videos.find(v => v.source === r.key)?.id).filter(Boolean))).join('、')}</span>
            <span>{row.fields['观察起始时间']} — {row.fields['观察结束时间']}</span></span>
        </button>) : <p className="muted">暂无跨视频结论。</p>)}
        {tab === 'trials' && <>
          <TabSelect label="采用状态" selected={filter} onChange={value => select({ adoption: value })}
            items={[{ value: '', label: '全部采用状态' }, ...Array.from(new Set(data.trials.map(t => t.fields['采用状态']))).map(value => ({ value, label: value }))]} />
          {trials.length ? trials.map(row => <button key={row.id} className="chloe-review-card" aria-pressed={trial?.id === row.id} onClick={() => select({ adoption: filter, trial: row.id })}>
            <span className="chloe-review-card-text"><strong>{row.id} · {row.fields['采用状态']}</strong><span className="chloe-review-summary">{row.origin ? summary(row.origin.fields['调整建议']) : '尚未找到来源建议'}</span>
              <span className="chloe-review-summary">{summary(row.fields['验证对象'])}</span></span>
          </button>) : <p className="muted">{filter ? '没有符合此采用状态的验证记录。' : '暂无建议验证。'}</p>}
        </>}
      </aside>
      <div className="chloe-review-detail">
        {tab === 'single' && video && <>
          <section aria-label="成片与发布对象"><h2>{video.id} · {video.title}</h2><h3>成片与发布对象</h3>
            {single ? <>
              <p className="muted">分析依据以本条复盘引用的具体成片或原分析记录为准。</p>
              {analysisRefs.length ? analysisRefs.map((ref, i) => <FileLink key={i} showStatus={false} item={{ kind: 'file', key: ref.key + (ref.section ? '#' + ref.section : ''), name: ref.label, url: `${api}/reviews/files/${ref.key.split('/').map(encodeURIComponent).join('/')}` }} />) : <p className="muted">尚未提供可打开的成片或原分析记录链接。</p>}
            </> : <p className="muted">暂无复盘记录，尚未明确分析对象。</p>}
            {publications.map(p => <div key={p.id}><p><strong>{p.id} · {p.fields['发布进展']}</strong> · 实际发布时间：{p.fields['实际发布时间']}</p><div className="chloe-review-actions"><Rich html={p.html['发布文件']} /><Rich html={p.html['发布链接']} /></div></div>)}
          </section>
          <section aria-label="效果数据"><h2>效果数据</h2>
            {sample ? <>
              <TabSelect label="采集批次" selected={sample.id} items={video.samples.map(s => ({ value: s.id, label: `${s.id} · ${s.rows[0].fields['采集时间']}` }))}
                onChange={value => select({ video: video.project, review: single?.id || '', sample: value })} />
              <p>采集时间：{sample.rows[0].fields['采集时间']}</p>
              <p>统计范围：{sample.rows[0].fields['统计起始时间']} — {sample.rows[0].fields['统计结束时间']}</p>
              <p>发布编号：{sample.rows[0].fields['发布编号']}</p>
              <div className="prose"><div className="table-scroll"><table aria-label="效果指标"><thead><tr>{metricFields.map(name => <th key={name}>{name}</th>)}</tr></thead>
                <tbody>{sample.rows.map((row, index) => <tr key={index}>{metricFields.map(name => <td key={name}><Rich html={row.html[name]} /></td>)}</tr>)}</tbody></table></div></div>
            </> : <p className="muted">暂未取得效果数据。</p>}
          </section>
          <section aria-label="单条复盘"><h2>单条复盘</h2>
            {single ? <>
              <TabSelect label="复盘记录" selected={single.id} items={video.reviews.map(r => ({ value: r.id, label: r.id }))}
                onChange={value => select({ video: video.project, review: value })} />
              <div className="chloe-review-actions"><span>采集依据：{linkedIds.includes('不适用') ? '不适用（仅内容分析）' : ''}</span>{video.samples.filter(s => linkedIds.includes(s.id)).map(s =>
                <LinkButton key={s.id} onClick={() => select({ video: video.project, review: single.id, sample: s.id })}>{s.id}</LinkButton>)}</div>
              <Fields row={single} names={['内容判断', '商品与转化判断', '局限', '调整建议']} />{related(single)}
            </> : <p className="muted">暂无单条复盘。</p>}
          </section>
        </>}
        {tab === 'cross' && conclusion && <>
          <h2>{conclusion.id} · 跨视频结论</h2><Fields row={conclusion} names={['结论']} />
          <p className="muted">记录时间：{conclusion.fields['记录时间']}<br />观察范围：{conclusion.fields['观察起始时间']} — {conclusion.fields['观察结束时间']}</p>
          <section aria-label="视频与证据"><h3>视频与证据</h3>{conclusion.references.filter(ref => ref.field === '视频与证据').map((ref, index) => {
            const owner = videos.find(v => v.source === ref.key);
            return <div className="chloe-review-actions" key={index}><span>{owner ? `${owner.id} · ${owner.title}` : ref.key}</span>
              <LinkButton onClick={() => open({ kind: 'markdown', name: ref.label, key: ref.key + '#' + ref.section, url: `${api}/reviews/files/${ref.key.split('/').map(encodeURIComponent).join('/')}` })}>{ref.label}</LinkButton></div>;
          })}</section>
          <Fields row={conclusion} names={['比较条件', '局限', '调整建议']} />{related(conclusion)}
        </>}
        {tab === 'trials' && trial && <>
          <h2>{trial.id} · 建议验证</h2>
          <section aria-label="来源建议"><h3>来源建议</h3>{trial.origin ? <><Rich html={trial.origin.html['调整建议']} /><LinkButton onClick={() => openOrigin(trial.origin!)}>查看 {trial.origin.id} 原复盘</LinkButton></> : <Rich html={trial.html['复盘编号']} />}</section>
          <section aria-label="采用决定"><h2>采用决定</h2><Fields row={trial} names={['采用状态', '采用依据']} /></section>
          <section aria-label="验证安排"><h2>验证安排</h2><Fields row={trial} names={['验证对象', '验证方法']} /></section>
          <section aria-label="验证结果"><h2>验证结果</h2>{trial.fields['验证结果'] === '未取得' ? <p className="muted">未取得验证结果。</p> : <Rich html={trial.html['验证结果']} />}<Fields row={trial} names={['结果证据']} /></section>
        </>}
      </div>
    </div>}
    {preview && <Preview project="" item={preview} baseUrl={`${api}/reviews`} revision={0} close={() => setPreview(null)} />}
  </PreviewContext>;
}
