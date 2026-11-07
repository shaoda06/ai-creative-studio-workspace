import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { FileItem } from './api';
import { Preview, PreviewContext } from './components';
import { PageHeader } from './components/PageHeader';
import { MessagePanel } from './components/MessagePanel';
import { UnderlineTabs } from './components/UnderlineTabs';
import { ChloeVoiceContent } from './ChloeVoices';
import type { VoiceDetail } from './ChloeVoices';

export default function ChloeVoicesExample() {
  const [state,setState]=useState('adopted');
  const [preview,setPreview]=useState<FileItem | null>(null);
  const media: FileItem={kind:'audio',name:'公共组件示例提示音',key:'tone.wav',url:'/component-samples/tone.wav'};
  const data: VoiceDetail={id:'演示',name:'声音布局示例',description:'声线、语言和口音等补充说明显示在这里。',models:[],
    versions: state==='empty' ? [] : [
      {purpose:'声音原始参考',resource:'AUD-DEMO',version:'V001',adopted:false,media,duration:2,sourceHtml:'<p>已有公共组件示例提示音。</p>',execution:'不适用'},
      ...['V001','V002','V003','V004','V005'].map(version=>({purpose:'声音参考',resource:'AUD-DEMO',version,adopted:state==='adopted' && version==='V005',media,duration:2,sourceHtml:'<p>仅演示来源说明的位置，未执行声音制作。</p>',execution:'不适用'})),
    ],sections:['关联资料','当前采用','采用变更','执行记录','输入记录','输出记录','审阅记录','返修记录'].map(heading=>({heading,html:'',empty:true}))};
  return <div className="home"><PageHeader eyebrow="Chloe · 页面演示" title="声音资产" actions={<Link to="/spaces/chloe?section=assets&asset=voices">返回声音列表</Link>} />
    <MessagePanel messages={[{id:'demo',content:'仅演示页面布局。试听使用已有的公共组件提示音，不代表人物声线；未生成或登记真实声音资产。'}]} />
    <UnderlineTabs label="声音演示状态" items={[{value:'adopted',label:'已采用'},{value:'candidate',label:'待采用'},{value:'empty',label:'无参考'}]} selected={state} onChange={setState} />
    <PreviewContext.Provider value={setPreview}>
      <ChloeVoiceContent key={state} data={data} spaceId="chloe" onOpen={setPreview} active={!preview} />
      {preview && <Preview project="" item={preview} revision={0} close={()=>setPreview(null)} />}
    </PreviewContext.Provider>
  </div>;
}
