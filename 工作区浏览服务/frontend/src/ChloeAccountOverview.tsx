import './chloe-overview.css';

export interface ChloeOverviewData {
  direction: Record<string, string>;
}

export function ChloeAccountOverview({ data }: { data: ChloeOverviewData }) {
  return <div className="chloe-overview">
    <section className="panel" aria-labelledby="chloe-direction-heading">
      <h2 id="chloe-direction-heading">账号方向</h2>
      <dl className="chloe-overview-fields">{Object.entries(data.direction).map(([name, value]) =>
        <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
      )}</dl>
    </section>
  </div>;
}
