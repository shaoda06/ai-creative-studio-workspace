import './chloe-overview.css';
import { Link } from 'react-router-dom';
import { useChloeScope } from './chloeScope';
import { PointerTooltip } from './components/PointerTooltip';

const statusColors: Record<string, string> = {
  制作中: 'blue', 待发布: 'orange', 已发布: 'green',
  正常: 'green', 待用户决定: 'orange', 受阻: 'red',
};

export interface ChloeOverviewData {
  direction: Record<string, string>;
  videos: { project: string; progress: Record<string, string> }[];
}

export function ChloeAccountOverview({ data }: { data: ChloeOverviewData }) {
  const { videos } = data;
  const { page } = useChloeScope();
  const waiting = videos.filter(item => item.progress['处理状态'] === '待用户决定');
  const blocked = videos.filter(item => item.progress['处理状态'] === '受阻');
  const attention = videos.filter(item => item.progress['处理状态'] !== '正常');
  const metrics = [
    { label: '视频总数', value: videos.length, note: '已建档的视频项目' },
    { label: '制作中', value: videos.filter(item => item.progress['视频状态'] === '制作中').length, note: '从策划到人工后期' },
    { label: '待发布', value: videos.filter(item => item.progress['视频状态'] === '待发布').length, note: '已做完，尚未发布成功' },
    { label: '已发布', value: videos.filter(item => item.progress['视频状态'] === '已发布').length, note: '已有实际发布成功记录' },
  ];
  return <div className="chloe-overview">
    <section className="panel" aria-labelledby="chloe-summary-heading">
      <div className="chloe-overview-heading">
        <h2 id="chloe-summary-heading">制作概况</h2>
        <p className="chloe-overview-attention muted">待用户决定：{waiting.length} · 受阻：{blocked.length}</p>
      </div>
      <dl className="chloe-overview-metrics">{metrics.map(item => <div key={item.label}>
        <dt>{item.label}</dt><dd>{item.value}</dd><small>{item.note}</small>
      </div>)}</dl>
    </section>

    <div className="chloe-overview-columns">
    <section className="panel" aria-labelledby="chloe-direction-heading">
      <h2 id="chloe-direction-heading">账号方向</h2>
      <dl className="chloe-overview-fields">{Object.entries(data.direction).map(([name, value]) =>
        <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
      )}</dl>
    </section>

    <section className="panel" aria-labelledby="chloe-pending-heading">
      <h2 id="chloe-pending-heading">待处理事项</h2>
      {!attention.length ? <p className="muted">暂无待用户决定或受阻的视频事项。</p> :
        <div className="chloe-overview-pending">
          {attention.map(({ progress }) => <article className="chloe-overview-task" key={progress['视频编号']}>
            <small>{progress['视频编号']} · {progress['视频名称']} · {progress['处理状态']}</small><h3>{progress['当前问题']}</h3>
            <p className="muted">下一步：{progress['下一步']}</p>
          </article>)}
        </div>}
    </section>
    </div>

    <section className="panel" aria-labelledby="chloe-videos-heading">
      <h2 id="chloe-videos-heading">作品进度</h2>
      <table className="chloe-overview-videos"><thead><tr><th scope="col">作品</th><th scope="col">当前阶段</th><th scope="col">视频状态</th><th scope="col">处理状态</th></tr></thead>
          <tbody>{videos.map(({ project, progress }) => <tr key={progress['视频编号']}>
            <td><Link className="chloe-overview-work-link" title={`${progress['视频编号']} ${progress['视频名称']}`} to={`${page}?section=production&video=${encodeURIComponent(project)}`}>{progress['视频编号']} {progress['视频名称']}</Link></td><td>{progress['当前阶段']}</td>
            {['视频状态', '处理状态'].map(field => <td key={field}>
              <PointerTooltip text={field === '处理状态' && ['待用户决定', '受阻'].includes(progress[field]) ? progress['当前问题'] : undefined}>
                <span className={`status-badge status-${statusColors[progress[field]]}`} tabIndex={field === '处理状态' && ['待用户决定', '受阻'].includes(progress[field]) ? 0 : undefined}>{progress[field]}</span>
              </PointerTooltip>
            </td>)}
          </tr>)}{!videos.length && <tr><td colSpan={4} className="muted">还没有视频项目。确定视频主题并建档后，在“视频制作”中查看制作进度。</td></tr>}</tbody></table>
    </section>
    <p className="muted">账号方向来自账号定位；制作统计、待处理事项与进度来自各视频项目 README。</p>
  </div>;
}
