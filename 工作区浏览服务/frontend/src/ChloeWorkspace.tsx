import { useContext } from 'react';
import { createPortal } from 'react-dom';
import { Link, useSearchParams } from 'react-router-dom';
import { HeaderControlsContext } from './components/AppShell';
import { TabNav } from './components/TabNav';

const sections = [
  { value: 'overview', label: '账号概况', description: '账号定位、账号连接、制作概况与当前事项。' },
  { value: 'products', label: '选品与商品', description: '候选选品、商品资料、带货条件与关联视频。' },
  { value: 'assets', label: '共用资产', description: 'AI模特、服装、造型、场景与声音。' },
  { value: 'production', label: '视频制作', description: '单条视频的脚本、参考素材、生成审阅与剪映交接。' },
  { value: 'publication', label: '成片与发布', description: '人工成片、封面文案、关联商品与发布记录。' },
  { value: 'review', label: '运营复盘', description: '单条表现、跨视频结论与调整验证。' },
  { value: 'resources', label: '资源库', description: '共用及视频专属的图片、视频、音频与具体版本。' },
];

export function ChloeWorkspace() {
  const controls = useContext(HeaderControlsContext);
  const [params, setParams] = useSearchParams();
  const current = sections.find(section => section.value === params.get('section')) || sections[0];
  return <>
    {controls && createPortal(<TabNav wide label="Chloe栏目" items={sections} selected={current.value}
      onChange={value => setParams({ section: value })} />, controls)}
    <section className="panel" aria-label={current.label}>
      <h2>{current.label}</h2>
      <p>{current.description}</p>
      <p className="muted">当前为栏目预览，具体内容随后补充。</p>
      {current.value === 'overview' && <Link to="/examples/chloe/overview">查看账号概况演示</Link>}
    </section>
  </>;
}
