import { Rich } from './components';

export interface AssetSection { heading: string; html: string; empty: boolean }

export function ChloeAssetRecords({ sections }: { sections: AssetSection[] }) {
  const content = (heading: string) => {
    const section = sections.find(item=>item.heading===heading)!;
    return section.empty ? <p className="muted">暂无{heading}。</p> : <Rich html={section.html} />;
  };
  return <details className="panel"><summary>资料与制作记录</summary>
    {['关联资料','当前采用','采用变更'].map(heading=><details key={heading}><summary>{heading==='当前采用' ? '采用依据与时间' : heading}</summary>{content(heading)}</details>)}
    <details><summary>执行记录</summary>{['执行记录','输入记录','输出记录','审阅记录','返修记录'].map(heading=><section key={heading}>{heading!=='执行记录' && <h3>{heading}</h3>}{content(heading)}</section>)}</details>
  </details>;
}
