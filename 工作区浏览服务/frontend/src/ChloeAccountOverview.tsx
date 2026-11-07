import './chloe-overview.css';

export interface ChloeOverviewData {
  direction: Record<string, string>;
  identity: Record<string, string>;
  connection: Record<string, string>;
  publishing: Record<string, string>;
  decisions: Record<string, string>[];
  videos: { progress: Record<string, string>; published: boolean }[];
}

function Fields({ values, names, labels = {} }: { values: Record<string, string>; names: string[]; labels?: Record<string, string> }) {
  return <dl className="chloe-overview-fields">{names.map(name => <div key={name}>
    <dt>{labels[name] || name}</dt><dd>{values[name]}</dd>
  </div>)}</dl>;
}

export function ChloeAccountOverview({ data }: { data: ChloeOverviewData }) {
  const { direction, identity, connection, decisions, videos } = data;
  const pending = decisions.filter(item => item['当前结论'] === '待确定');
  const waiting = videos.filter(item => item.progress['制作状态'] === '待用户决定');
  const metrics = [
    { label: '视频总数', value: videos.length, note: '已建档的视频项目' },
    { label: '待用户决定', value: waiting.length, note: '需要确认后再继续' },
    { label: '人工后期', value: videos.filter(item => item.progress['当前阶段'] === '人工后期' && item.progress['制作状态'] !== '完成').length, note: '处于剪映人工调整阶段' },
    { label: '已发布视频', value: videos.filter(item => item.published).length, note: '有已发布记录的视频' },
  ];
  return <div className="chloe-overview" aria-label="账号概况内容">
    <section className="panel" aria-label="账号身份与制作概况">
      <div className="chloe-overview-identity">
        <div>
          <p className="eyebrow">{identity['平台']} · {direction['经营方式']}</p>
          <h2>{identity['公开账号名'] === '待核实' ? '账号名称待核实' : identity['公开账号名']}</h2>
          <p className="muted">账号 ID：{identity['平台账号ID']} · {direction['账号阶段']}</p>
        </div>
        <div className="chloe-overview-income"><span className="muted">变现方式</span><p>{direction['变现方式']}</p></div>
      </div>
      <dl className="chloe-overview-metrics">{metrics.map(item => <div key={item.label}>
        <dt>{item.label}</dt><dd>{item.value}</dd><small>{item.note}</small>
      </div>)}</dl>
    </section>

    <div className="chloe-overview-columns">
      <section className="panel" aria-labelledby="chloe-positioning-heading">
        <h2 id="chloe-positioning-heading">账号定位</h2>
        <Fields values={direction} names={['品类范围', '目标人群', '购买需求', '内容风格', '展示形式', '更新节奏']} />
        <details className="chloe-overview-more"><summary>人物、声音与制作约定</summary>
          <Fields values={direction} names={['账号命名方向', '固定人物策略', '声音策略', '制作方式', '制作限制']} />
        </details>
      </section>
      <section className="panel" aria-labelledby="chloe-connection-heading">
        <h2 id="chloe-connection-heading">{identity['平台']}账号接入</h2>
        <Fields values={connection} names={['连接状态', '发布权限', '挂品资格']}
          labels={{ '发布权限': '视频发布', '挂品资格': '商品挂载' }} />
        <small>最近核对：{connection['核对时间'] === '未取得' ? '尚未核对' : connection['核对时间']}</small>
      </section>
    </div>

    <section className="panel" aria-labelledby="chloe-pending-heading">
      <h2 id="chloe-pending-heading">待处理事项</h2>
      {!pending.length && !waiting.length ? <p className="muted">暂无已记录的待决定事项。定位中的“待确定”仍需后续补齐。</p> :
        <div className="chloe-overview-pending">
          {pending.map(item => <article className="chloe-overview-task" key={item['事项编号']}>
            <small>账号定位 · {item['事项编号']}</small><h3>{item['事项']}</h3><p>{item['备选与取舍']}</p>
            <p className="muted">当前结论：{item['当前结论']}</p>
          </article>)}
          {waiting.map(({ progress }) => <article className="chloe-overview-task" key={progress['视频编号']}>
            <small>{progress['视频编号']} · {progress['制作状态']}</small><h3>{progress['当前问题']}</h3>
            <p>{progress['视频名称']}</p><p className="muted">下一步：{progress['下一步']}</p>
          </article>)}
        </div>}
    </section>

    <section className="panel" aria-labelledby="chloe-videos-heading">
      <h2 id="chloe-videos-heading">视频进度</h2>
      <table className="chloe-overview-videos"><thead><tr><th scope="col">视频</th><th scope="col">当前阶段</th><th scope="col">制作状态</th><th scope="col">下一步</th></tr></thead>
          <tbody>{videos.map(({ progress }) => <tr key={progress['视频编号']}>
            <td><small>{progress['视频编号']}</small>{progress['视频名称']}</td><td>{progress['当前阶段']}</td>
            <td>{progress['制作状态']}</td><td>{progress['下一步']}</td>
          </tr>)}{!videos.length && <tr><td colSpan={4} className="muted">还没有视频项目。选定商品和视频主题后，在“视频制作”中查看制作进度。</td></tr>}</tbody></table>
    </section>
    <p className="muted">资料来源：账号定位、账号运营配置、各视频项目 README。统计随这些记录更新。</p>
  </div>;
}
