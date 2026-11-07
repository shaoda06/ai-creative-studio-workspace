import './chloe-overview.css';

export interface ChloeOverviewData {
  direction: Record<string, string>;
  videos: { progress: Record<string, string>; published: boolean }[];
}

export function ChloeAccountOverview({ data }: { data: ChloeOverviewData }) {
  const { videos } = data;
  const waiting = videos.filter(item => item.progress['制作状态'] === '待用户决定');
  const metrics = [
    { label: '视频总数', value: videos.length, note: '已建档的视频项目' },
    { label: '待用户决定', value: waiting.length, note: '需要确认后再继续' },
    { label: '人工后期', value: videos.filter(item => item.progress['当前阶段'] === '人工后期' && item.progress['制作状态'] !== '完成').length, note: '处于剪映人工调整阶段' },
    { label: '已发布视频', value: videos.filter(item => item.published).length, note: '有已发布记录的视频' },
  ];
  return <div className="chloe-overview">
    <section className="panel" aria-labelledby="chloe-summary-heading">
      <h2 id="chloe-summary-heading">制作概况</h2>
      <dl className="chloe-overview-metrics">{metrics.map(item => <div key={item.label}>
        <dt>{item.label}</dt><dd>{item.value}</dd><small>{item.note}</small>
      </div>)}</dl>
    </section>

    <section className="panel" aria-labelledby="chloe-direction-heading">
      <h2 id="chloe-direction-heading">账号方向</h2>
      <dl className="chloe-overview-fields">{Object.entries(data.direction).map(([name, value]) =>
        <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
      )}</dl>
    </section>

    <section className="panel" aria-labelledby="chloe-pending-heading">
      <h2 id="chloe-pending-heading">待处理事项</h2>
      {!waiting.length ? <p className="muted">暂无需要用户决定的视频事项。</p> :
        <div className="chloe-overview-pending">
          {waiting.map(({ progress }) => <article className="chloe-overview-task" key={progress['视频编号']}>
            <small>{progress['视频编号']} · {progress['制作状态']}</small><h3>{progress['当前问题']}</h3>
            <p>{progress['视频名称']}</p><p className="muted">下一步：{progress['下一步']}</p>
          </article>)}
        </div>}
    </section>

    <section className="panel" aria-labelledby="chloe-videos-heading">
      <h2 id="chloe-videos-heading">定位与当前进度</h2>
      <table className="chloe-overview-videos"><thead><tr><th scope="col">视频</th><th scope="col">当前阶段</th><th scope="col">制作状态</th><th scope="col">下一步</th></tr></thead>
          <tbody>{videos.map(({ progress }) => <tr key={progress['视频编号']}>
            <td><small>{progress['视频编号']}</small>{progress['视频名称']}</td><td>{progress['当前阶段']}</td>
            <td>{progress['制作状态']}</td><td>{progress['下一步']}</td>
          </tr>)}{!videos.length && <tr><td colSpan={4} className="muted">还没有视频项目。选定商品和视频主题后，在“视频制作”中查看制作进度。</td></tr>}</tbody></table>
    </section>
    <p className="muted">账号方向来自账号定位；制作统计、待处理事项与进度来自各视频项目 README。</p>
  </div>;
}
