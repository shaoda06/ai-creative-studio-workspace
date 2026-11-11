import { AudioReferenceCard } from './AudioReferenceCard';
import { FullscreenImage } from './FullscreenImage';
import { useCallback, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './EpisodeProduction.css';
import type { FileItem, SegmentVideo as VideoItem } from '../api';
import { Document, FileTree, Groups, Preview, PreviewContext, Result, Rich } from '../components';
import { SearchField } from './SearchField';
import { PageHeader } from './PageHeader';
import { EpisodeTitleStatus } from './EpisodeTitleStatus';
import { Breadcrumbs } from './Breadcrumbs';
import { EntryCard } from './EntryCard';
import { PointerTooltip } from './PointerTooltip';
import { DownloadControl } from './DownloadControl';
import { DownloadButton } from './DownloadButton';
import { FileActions, Original } from './FileActions';
import { SyncNotification } from './SyncNotification';
import { TabNav } from './TabNav';
import { AssetMedia } from './AssetMedia';
import { AssetMediaCard } from './AssetMediaCard';
import { AssetCandidateMedia } from './AssetCandidateMedia';
import { ReferenceMediaCard } from './ReferenceMediaCard';
import { AudioPreviewButton, useAudioPreview } from './AudioPreviewButton';
import { EpisodeButton } from './EpisodeButton';
import { SegmentStageStrip } from './SegmentStageStrip';
import { SegmentVideo } from './SegmentVideo';
import { SegmentLayout } from './SegmentLayout';
import type { SegmentVideoHandle } from './SegmentVideo';
import { PromptSections } from './PromptSections';
import { TaskCard } from './TaskCard';
import { LinkButton } from './LinkButton';
import { ReleaseFilms } from './ReleaseFilms';
import { LocalQueueCard } from './LocalQueueCard';

export function ComponentExample({ title, rule, usage, children, fullWidth = false }: { fullWidth?: boolean; title: string; rule: string; usage: string; children: ReactNode }) {
  return <section className={"component-example" + (fullWidth ? " is-full-width" : "")} aria-label={title}>
    <h3>{title}</h3><p className="component-rule">{rule}</p>
    <div className="component-demo">{children}</div>
    <p className="component-usage">使用位置：{usage}</p>
  </section>;
}
const fileUrl = '/api/component-samples/file';
const image: FileItem = { kind: 'image', name: '示例图形', key: 'image.svg', url: '/component-samples/image.svg' };
const audio: FileItem = { kind: 'audio', name: '示例提示音', key: 'tone.wav', url: '/component-samples/tone.wav' };
const video: FileItem = { kind: 'video', name: '示例视频', key: 'video.webm', url: '/component-samples/video.webm' };
const imageDetails: FileItem = { kind: 'document', name: '图片详情示例', key: 'asset-details-demo', doc: { html: '<p>本地图片详情示例。</p>' } };
const imageRecord = { type: '示例参考图', media: image, version: 'v1.0', statusHtml: '<span class="status-badge status-gray">示例</span>', scope: '仅供组件展示' };
const videoRecord: VideoItem = { key: 'sample-video', url: video.url!, stage: '一采', run: 'R001', approved: true, candidateNumber: 1, fileRevision: 'sample-1', deliveryStatus: '已取回', taskStatus: '已完成', checkedAt: '' };
const segments = [{ id: 'P001', duration: 2, scriptHtml: '', videos: [videoRecord] }, { id: 'P002', duration: 3, scriptHtml: '', videos: [] }];
const sampleDoc = { html: '<h2 id="sample-text">正文与代码</h2><p>这是一份示例文档。</p><pre><code>可以复制这段示例文字。</code></pre><h2 id="sample-end">附属资料</h2><p>展开下方其他资料查看目录。</p>', headerHtml: '<p>作者：演示</p><p>用途：查看折叠信息</p>', groups: [{ name: '示例附件', files: [{ kind: 'document', name: '附属说明', doc: { html: '<p>仅供演示的附属说明。</p>' } }] }] };
const liveStatusDoc = { html: '<h2 id="sample-status">示例作品</h2><p>制作状态：作品状态</p>' };
const retainSample = () => () => {};

export function ShowcaseExamples({ category }: { category: string }) {
  const [text, setText] = useState('');
  const [breadcrumbActions, setBreadcrumbActions] = useState<HTMLDivElement | null>(null);
  const [search, setSearch] = useState('');
  const entryTitles = ['公共组件示例', '带有较长标题并可以自然换行的公共组件入口卡片示例，供对照同行卡片的底部入口位置'].filter(title => title.includes(search));
  const [selected, setSelected] = useState('one');
  const [selectedImage, setSelectedImage] = useState('');
  const [fullscreenImage, setFullscreenImage] = useState(false);
  const [preview, setPreview] = useState<FileItem | null>(null);
  const [videoOnlyPreview, setVideoOnlyPreview] = useState(false);
  const close = useCallback(() => setPreview(null), []);
  const [readState, setReadState] = useState('ready');
  const [sync, setSync] = useState<{ error?: string; errorKind?: string; retryAt?: number; updating?: boolean }>({});
  const [wide, setWide] = useState(false);
  const [continuous, setContinuous] = useState(false);
  const [repeat, setRepeat] = useState(false);
  const [time, setTime] = useState(0);
  const [segment, setSegment] = useState('P001');
  const [vertical, setVertical] = useState(false);
  const [queueState, setQueueState] = useState('local_queued');
  const [action, setAction] = useState('尚未操作');
  const [sampleWorkStatus, setSampleWorkStatus] = useState('待启动');
  const [started] = useState(() => new Date().toISOString());
  const playerRef = useRef<SegmentVideoHandle>(null);
  const sound = useAudioPreview(category === 'media', null, 1);
  return <PreviewContext.Provider value={setPreview}>
    {category === 'controls' && <ComponentExample title="下划线链接按钮" rule="LinkButton统一13px字号、下划线、无边框与无悬停底色，保留按钮键盘及禁用行为；此处只更新示例文字。" usage="任务组详情、本镜通过、插入时间及清空"><LinkButton onClick={() => setText('链接示例已点击')}>链接操作示例</LinkButton><LinkButton disabled>禁用链接示例</LinkButton><p role="status">{text}</p></ComponentExample>}
    {category === 'layout' && <>
      <ComponentExample fullWidth title="标题与路径导航" rule="页面标题可带说明和操作区。纵向布局中操作与标题同行，附属内容及路径位于下方；路径右侧操作区可换行。面包屑悬停统一显示小手；点击多层路径前缀可返回上一级，当前位置仍用于定位。示例下载仅保存固定文本。" usage="Nora、Iris、Chloe 项目栏目、资产、风格库、开发记录">
        <PageHeader eyebrow="示例栏目" title="示例页面" description="这里展示公共页面标题。" actions={<button onClick={() => setText('已点击标题操作')}>示例操作</button>} />
        <PageHeader stacked title="带附属内容的示例标题" actions={<button onClick={() => setText('已点击标题操作')}>标题同行操作</button>}><span>示例阶段信息</span><Breadcrumbs items={[{ label: '示例当前栏目' }]} /></PageHeader>
        <Breadcrumbs items={[{ label: '示例列表', href: '#/history', onClick: () => setText('已返回示例列表') }, { label: <>EP001 · 组件演示集 <EpisodeTitleStatus status="最终定名" /></> }]} />
        <Breadcrumbs actionsRef={setBreadcrumbActions} items={[{ label: '剧集制作', href: '#/history', onClick: () => setText('已返回示例列表') }, { label: 'EP001 · 下载操作示例' }]} />
        {breadcrumbActions && createPortal(<div className="episode-heading-actions">
          <span className="muted">本集时长：6秒</span>
          <DownloadButton url={null} label="剪映草稿包" title="固定文本下载示例，不是剪映草稿" file={{ text: '仅供布局与下载交互展示', name: 'draft-example.txt', type: 'text/plain' }} />
          <DownloadButton url={null} label="本集打包下载" title="固定文本下载示例，不读取项目" file={{ text: '仅供布局与下载交互展示', name: 'episode-example.txt', type: 'text/plain' }} />
        </div>, breadcrumbActions)}
        <p role="status">{text || '试试右侧操作或路径链接。'}</p>
      </ComponentExample>
      <ComponentExample fullWidth title="入口卡片与搜索" rule="同行卡片的入口文字和箭头靠底部对齐。搜索框支持长文字、清空与禁用，窄容器不越界。输入文字筛选示例，点击卡片返回网站入口页。" usage="工作区首页和登记空间项目列表；搜索也用于资产与风格库">
        <button onClick={() => setSearch('中文长搜索条件' + 'LongSearchReference'.repeat(8))}>填入长搜索文字</button>
        <div className="component-demo-stack"><SearchField label="搜索示例入口" placeholder="搜索示例与较长的关键词说明…" value={search} onChange={setSearch} />
        <SearchField size="compact" label="紧凑搜索示例" placeholder="紧凑搜索…" value={search} onChange={setSearch} /><SearchField label="禁用搜索示例" placeholder="不可搜索" value="" onChange={setSearch} disabled />
        {entryTitles.length ? <div className="grid">
          {entryTitles.map(title => <EntryCard key={title} to="/" title={title} description="返回网站入口页" icon="▤" />)}
        </div> : <p className="muted">没有匹配的示例。</p>}</div>
      </ComponentExample>
      <ComponentExample fullWidth title="紧凑入口卡片" rule="上下内边距18px，两行间距6px；整卡点击与默认入口相同。长标题可换行，说明与箭头仍贴底。" usage="Chloe成片与发布列表">
        <div className="grid">
          <EntryCard compact to="/" title="V001 · 示例作品" description="制作中 · 成片目录内 1 个视频" />
          <EntryCard compact to="/" title="V002 · 用于检查长作品名称换行与说明对齐的示例作品" description="待发布 · 成片目录内 2 个视频" />
        </div>
      </ComponentExample>
      <ComponentExample title="导航的分组与方向" rule="同一组件支持横排、竖排、紧凑和分组下拉；加宽规格用于项目顶部，竖排示例保持桌面侧栏排列。禁用项不可选择。" usage="顶部栏目、侧栏、制作模式">
        <TabNav wide label="示例分组导航" selected={selected} onChange={setSelected} groups={[{ label: '示例分组', values: ['two', 'three'] }]} items={[{ value: 'one', label: '普通页签' }, { value: 'two', label: '子项甲' }, { value: 'three', label: '子项乙' }, { value: 'disabled', label: '禁用页签', disabled: true }]} />
        <TabNav label="示例竖排导航" vertical compact selected={selected} onChange={setSelected} items={[{ value: 'one', label: '示例甲' }, { value: 'two', label: '示例乙' }]} />
      </ComponentExample>
      <ComponentExample title="悬停与键盘提示" rule="悬停或键盘聚焦显示说明，移开或按Esc关闭；提示不挤动布局。" usage="长标题、播放入口、状态详情">
        <PointerTooltip text="这是公共提示框的完整说明。"><button>查看悬停说明</button></PointerTooltip>
      </ComponentExample>
    </>}
    {category === 'files' && <>
      <ComponentExample fullWidth title="成片交付选集与播放" rule="按实际一级目录提供分类标签，片头、片尾固定排在各集前面；根目录文件显示在其他文件，不猜集数、不移动文件。下方文件树提供该集发布说明、文案及封面入口。各类递归读取视频，沿用原路径自然数字排序及片头／片尾同名视频优先规则，每页5个实际文件名（不带扩展名）。分类不超过5个视频时只显示文件名，超过5个才显示上一页和下一页，末页不足5个也保留翻页。切类卸载原播放器并回到第一页。选集靠左，右侧下载当前选集；窄屏可换行，文件名单行滚动。项目标题显示全部视频总数；视频居中保留原比例，不自动播放。这里只播放和下载固定示例媒体。" usage="项目成片交付；UnderlineTabs、Pagination、TabNav和DownloadButton的既有规格">
        <ReleaseFilms items={[
          { kind: 'group', name: '片头', children: [{ ...video, name: '先导版.webm', key: '示例/片头/先导版.webm' }] },
          { kind: 'group', name: '片尾', children: [{ ...video, name: '结束版.webm', key: '示例/片尾/结束版.webm' }] },
          { kind: 'group', name: 'EP003', children: Array.from({ length: 12 }, (_, index) => ({ ...video, name: `第${index + 1}集.webm`, key: `示例/EP003/成片/第${index + 1}集.webm` })) },
          { ...video, name: '旧导出示例.webm', key: '示例/旧导出示例.webm' },
        ]} />
      </ComponentExample>
      <ComponentExample fullWidth title="只读文件目录" rule="直接使用公共文件树，按文件与子目录浏览，保留空目录。列表保留文件名预览入口，不显示确认状态；视频下载位于目录行，视频弹窗只播放，其他文件操作沿用原样，不提供改名、移动或删除。示例不使用真实项目文件。" usage="仅文件名入口的目录资料">
        <FileTree showOriginal={false} showStatus={false} items={[{ kind: 'video', name: '示例发布成片.webm', url: video.url },
          { kind: 'group', name: '分平台', children: [{ kind: 'video', name: '示例竖屏版本.webm', url: video.url }] },
          { kind: 'group', name: '待导出空目录', children: [] }]} />
      </ComponentExample>
      <ComponentExample title="原文件与下载" rule="下载统一使用描边加图标，14px文字、4px图文间距、7px圆角和相同内边距；准备中替换为转圈图标，禁用状态降低透明度。查看和下载使用固定示例文本。下载会保存component-sample.txt，不读取项目文件；支持自定义文案、仅下载及整行居中。图片预览使用居中的仅下载规格，其他文件默认保留查看和下载。" usage="文件目录、资料卡、制作资源下载">
        <div className="component-demo-row"><Original url={fileUrl} label="示例原文件" /><FileActions url={fileUrl} /></div>
        <DownloadButton url={fileUrl + '?download=true'} label="下载示例文件" title="组件示例文件" />
        <FileActions url={fileUrl} downloadOnly centered />
        <FileActions url={fileUrl} viewLabel="查看原图" downloadLabel="下载原图" />
        <DownloadButton url={null} file={{ text: "本地导出示例。\n", name: "component-export.md", type: "text/markdown;charset=utf-8" }} label="下载本地导出示例" title="本地导出示例" />
        <DownloadButton url={null} label="没有文件时禁用" title="暂无示例文件" />
        <DownloadControl label="正在准备…" busy title="准备中外观示例，不发起下载" />
      </ComponentExample>
      <ComponentExample title="文档信息与附属资料" rule="章节导航可展开并跳转正文。正文前可选的参考入口排在章节导航后，独立于文档章节。" usage="Iris 项目概况与需求参考、项目文档、资料卡、开发记录弹窗">
        <Document value={sampleDoc} showOriginal={false} chaptersInitiallyOpen={false}
          beforeBody={<details><summary>参考资料</summary><p>这里是与示例正文关联的参考资料。</p></details>} />
        <Groups groups={[{ name: '普通分组示例', files: [{ kind: 'document', name: '分组文件', doc: { html: '<p>普通分组中的示例文件。</p>' } }] }]} />
      </ComponentExample>
      <ComponentExample title="文档内的实时状态" rule="正文可以显示来自外部资料的实时字段。点击按钮切换本地示例状态，正文直接更新。" usage="Iris 项目概况的作品状态入口">
        <button type="button" onClick={() => setSampleWorkStatus(status => status === '待启动' ? '待审阅' : '待启动')}>切换示例制作状态</button>
        <Document value={liveStatusDoc} showOriginal={false} chaptersInitiallyOpen={false}
          transformBody={html => html.replace('作品状态', sampleWorkStatus)} />
      </ComponentExample>
      <ComponentExample title="分镜章节留白" rule="spacedHeadings为后续二、三级标题增加40px上间距，首标题和段落行距不变。" usage="三个工作区的视频制作分镜正文">
        <Document spacedHeadings showOriginal={false} chaptersInitiallyOpen={false} value={{html:'<h3>SH001｜展示全貌</h3><p>镜头动作及构图说明。</p><p>下一镜继续展示细节。</p><h3>SH002｜展示细节</h3><p>后续镜头与上一镜之间保留明显留白。</p>'}} />
      </ComponentExample>
      <ComponentExample title="字段表格" rule="Rich的fieldTable规格用于两列字段表：左列40%、右列60%，长文字换行；未启用时保持原表格排版。" usage="Chloe模特人物特征">
        <Rich fieldTable html={'<div class="table-scroll"><table><thead><tr><th>字段</th><th>内容</th></tr></thead><tbody><tr><td>体型与头身比例</td><td>待确定</td></tr><tr><td>长字段名称示例</td><td>'+'连续长内容LongUnbrokenText'.repeat(20)+'</td></tr></tbody></table></div>'} />
      </ComponentExample>
      <ComponentExample title="提示词分节与正文" rule="已识别的提示词字段可折叠。正文中的音视频链接打开播放器，其他附件可查看或下载原文件。" usage="视频提示词、项目资料、制作记录与资产状态">
        <PromptSections language="zh" text={'summary: 示例概述\ndetailed_description: 仅供演示的详细描述\noverall_soundscape: 示例声景'} />
        <Rich html={'<p>示例状态：<span class="status-badge status-gray">待确认</span> <span class="status-badge status-green">已完成</span></p>'} />
        <Rich html={'<p><a href="/component-samples/video.webm" data-doc="video.webm">正文视频示例</a> · <a href="/component-samples/tone.wav" data-doc="tone.wav">正文音频示例</a> · <a href="/component-samples/image.svg" data-doc="image.svg">正文原文件示例</a></p>'} />
      </ComponentExample>
    </>}
    {category === 'states' && <>
      <ComponentExample title="加载与读取重试" rule="手动切换示例状态；失败提示中的重新读取恢复本地示例，不发起资料请求。" usage="各页查询、详情和预览">
        <div className="component-demo-row"><button onClick={() => setReadState('loading')}>显示加载</button><button onClick={() => setReadState('error')}>模拟读取失败</button><button onClick={() => setReadState('ready')}>结束加载</button></div>
        <Result loading={readState === 'loading'} error={readState === 'error' ? new Error('示例读取错误') : null} retry={() => setReadState('ready')} retrying={false} />
        {readState === 'ready' && <p role="status">示例资料已就绪。</p>}
      </ComponentExample>
      <ComponentExample title="同步反馈" rule="倒计时来自示例时间；重试状态与结束由下方按钮控制，不连接项目同步。" usage="项目资料检查">
        <div className="component-demo-row"><button onClick={() => setSync({ error: '示例同步错误', retryAt: Date.now() + 5000 })}>模拟同步失败</button><button onClick={() => setSync({ error: '示例资料变动', errorKind: 'source_changed', retryAt: Date.now() + 5000 })}>模拟资料更新</button><button onClick={() => setSync({ updating: true })}>模拟重试中</button><button onClick={() => setSync({})}>结束同步演示</button></div>
        <SyncNotification {...sync} />
      </ComponentExample>
    </>}
    {category === 'media' && <>
      {sound.player}
      <ComponentExample fullWidth title="图片与候选卡片" rule="尺寸只显示加载图片的真实像素宽×高，不计算或显示比例。点击图片在公共预览中放大，只保留整行居中的下载入口；候选分组按类型展开。图片为随服务提供的示例图形。无图片时保留同高的浅色占位框、图片图标和emptyLabel提示，不提供预览点击。查看详情固定在底部右侧，生成记录保留左侧；下方记录和详情使用本地示例正文。" usage="人物、场景、道具、封面">
        <AssetMedia items={[imageRecord]} revision={1} formal />
        <AssetCandidateMedia items={[imageRecord]} revision={1} />
        <PreviewContext.Provider value={item => setPreview(item.kind === 'markdown' ? { ...item, kind: 'document', doc: { html: '<p>本地示例生成记录。</p>' } } : item)}>
          <div className="asset-media-grid">
            <AssetMediaCard title="仅有查看详情" item={imageRecord} revision={1} formal onDetails={() => setPreview(imageDetails)} />
            <AssetMediaCard title="已登记尚未生成" item={{ emptyLabel: '尚未生成图片' }} revision={1} onDetails={() => setPreview(imageDetails)} />
            <AssetMediaCard title="生成记录与查看详情" item={{ ...imageRecord, recordUrl: '/component-samples/files/示例生成记录.md', generation: '生成记录-示例' }} revision={1} formal onDetails={() => setPreview(imageDetails)} />
          </div>
        </PreviewContext.Provider>
      </ComponentExample>
      <ComponentExample title="含补充信息的图片卡片" rule="children插槽放在原卡片边框内，承载调用方的元信息与操作；不传入时保持原卡片。" usage="Chloe资源库">
        <AssetMediaCard title="资源版本示例" item={imageRecord} revision={1} compact showVersion={false}>
          <p>IMG-DEMO@V001 · 共用资源</p><LinkButton onClick={() => setPreview(imageDetails)}>详情</LinkButton>
        </AssetMediaCard>
      </ComponentExample>
      <ComponentExample title="全屏看图" rule="点击图片进入全屏，图片完整等比显示；再次点击图片、按Esc或关闭按钮退出。可传入分页控件，分页不关闭图片。" usage="导演分镜表、Chloe模特图片">
        <PreviewContext.Provider value={() => setFullscreenImage(true)}><AssetMediaCard title="全屏图片示例" item={imageRecord} revision={1} compact /></PreviewContext.Provider>
        {fullscreenImage && <FullscreenImage title="全屏图片示例" src={imageRecord.media!.url!} alt="全屏图片示例" close={() => setFullscreenImage(false)} />}
      </ComponentExample>
      <ComponentExample title="外层已命名的图片卡片" rule="hideTitle隐藏卡片内部重复标题，仍保留可访问名称、图片预览与资料；其他卡片默认显示标题。" usage="Chloe模特当前图片">
        <AssetMediaCard title="外层已命名的采用图" item={imageRecord} revision={1} formal hideTitle />
        <AssetMediaCard title="外层已命名的空图片" item={{emptyLabel:'尚未采用图片'}} revision={1} formal hideTitle />
      </ComponentExample>
      <ComponentExample title="只显示尺寸的图片卡片" rule="showFileActions与showVersion默认开启，可分别关闭文件操作与版本字段；尺寸与图片预览不受影响。" usage="Chloe模特图片页当前采用图">
        <AssetMediaCard title="仅保留尺寸的采用图" item={{media:image,version:'V003'}} revision={1} formal hideTitle showFileActions={false} showVersion={false} />
        <AssetMediaCard title="仅保留尺寸的空图片" item={{emptyLabel:'尚未采用图片'}} revision={1} formal hideTitle showFileActions={false} showVersion={false} />
      </ComponentExample>
      <ComponentExample title="按比例展示的图片卡片" rule="aspectRatio为数字时使用指定比例，有图与空态同高。natural按原图比例铺满宽度，无图时使用默认占位高度。" usage="Chloe共用资产入口封面、参考图、正式图及其他版本">
        <AssetMediaCard title="16:9图片区域" item={imageRecord} revision={1} formal hideTitle aspectRatio={16 / 9} />
        <AssetMediaCard title="16:9空图片区域" item={{emptyLabel:'尚未采用图片'}} revision={1} formal hideTitle aspectRatio={16 / 9} />
        <AssetMediaCard title="按原图比例展示" item={imageRecord} revision={1} formal hideTitle aspectRatio="natural" />
      </ComponentExample>
      <ComponentExample title="入口图片卡片" rule="entry规格只显示单行名称与图片区域，长标题省略并可悬停查看完整名称；隐藏尺寸、版本、说明和底部操作。默认卡片不变；entry传入to时整卡作为链接，图片不再单独打开预览，未传to时有图仍可预览。" usage="Chloe模特列表">
        <AssetMediaCard title="入口卡片长标题：用于检查名称只占一行且不会挤出卡片边界的完整示例名称" item={{ ...imageRecord, scope: '入口规格不显示此说明', version: 'V003', recordUrl: '/component-samples/files/示例生成记录.md' }} revision={1} formal entry onDetails={() => setPreview(imageDetails)} />
        <AssetMediaCard title="带声音的入口卡片长标题：试听按钮不会跳转" item={imageRecord} revision={1} entry to="/"
          titleActions={<AudioPreviewButton name="入口卡片声音" enabled playing={sound.playingId==='entry'} progress={sound.currentId==='entry' ? sound.progress : 0} onClick={()=>sound.toggle('entry',audio.url!)} />} />
        <AssetMediaCard title="未关联声音的入口卡片" item={{emptyLabel:'尚未采用图片'}} revision={1} entry to="/"
          titleActions={<AudioPreviewButton name="入口卡片声音" enabled={false} playing={false} progress={0} onClick={()=>{}} />} />
        <AssetMediaCard title="入口卡片无图" item={{ emptyLabel: '尚未采用正面面部图' }} revision={1} entry to="/" />
      </ComponentExample>
      <ComponentExample title="图片选择卡片" rule="暂选时显示蒙版与对勾。需要看大图时，点击图片打开预览，用标题旁按钮选择。无可用图片时可禁用。" usage="Chloe 装配资产选择">
        <div className="asset-media-grid">
          <AssetMediaCard title="单选图片甲" item={imageRecord} revision={1} entry selection={{selected:selectedImage==='first',onSelect:()=>setSelectedImage('first')}} />
          <AssetMediaCard title="单选图片乙" item={imageRecord} revision={1} entry selection={{selected:selectedImage==='second',onSelect:()=>setSelectedImage('second')}} />
          <AssetMediaCard title="单选图片未就绪" item={{emptyLabel:'尚未采用图片'}} revision={1} entry selection={{selected:false,disabled:true,onSelect:()=>{}}} />
          <AssetMediaCard title="可放大的选项" item={imageRecord} revision={1} entry
            selection={{selected:selectedImage==='preview',onSelect:()=>setSelectedImage('preview'),onPreview:()=>setFullscreenImage(true)}} />
        </div>
      </ComponentExample>
      <ComponentExample title="紧凑图片卡片" rule="卡片只显示名称、缩略图和资源版本。无图保留紧凑图片区域及提示；有图时点击图片在公共预览中查看和下载。" usage="Iris 已采用素材">
        <AssetMediaCard title="A001 · 已采用示例" item={{ ...imageRecord, version: 'V002' }} revision={1} formal compact />
        <AssetMediaCard title="A002 · 无图示例" item={{}} revision={1} compact />
      </ComponentExample>
      <ComponentExample title="音视频卡片与试听" rule="试听播放2秒轻提示音，可暂停；视频入口打开公共预览。无音频时按钮禁用。" usage="参考音视频、人物音色">
        <ReferenceMediaCard item={{ kind: 'reference', name: audio.name, media: audio, approvalHtml: '<span class="status-badge status-gray">示例</span>' }} audio playing={sound.playingId === 'sample'} progress={sound.progress} onPlay={() => sound.toggle('sample', audio.url!)} onSelect={() => setPreview(audio)} />
        <ReferenceMediaCard item={{ kind: 'reference', name: video.name, media: video }} audio={false} playing={false} progress={0} onPlay={() => setPreview(video)} onSelect={() => setPreview(video)} />
        <FileActions url={video.url} downloadOnly />
        <AudioPreviewButton name="缺少参考音频的示例" enabled={false} playing={false} progress={0} onClick={() => {}} />
      </ComponentExample>
      <ComponentExample title="仅播放的视频预览" rule="视频Preview统一不显示查看和下载，保留播放、关闭和Esc退出；其他类型保留原文件操作。示例只播放本地静态视频。" usage="三个工作区的视频预览弹窗">
        <button onClick={() => setVideoOnlyPreview(true)}>打开仅播放预览</button><FileActions url={video.url} downloadOnly />
        {videoOnlyPreview && <Preview project="" item={video} revision={1} close={() => setVideoOnlyPreview(false)} />}
      </ComponentExample>
      <ComponentExample title="紧凑声音参考" rule="标题、公共试听按钮与右侧时长同排；长标题省略并提供完整提示，时长未知显示未取得。" usage="Chloe声音当前采用、其他版本与模特声音信息">
        <AudioReferenceCard name="AUD-SAMPLE@V001" duration={4} playing={sound.playingId==='reference'} progress={sound.currentId==='reference' ? sound.progress : 0} onPlay={()=>sound.toggle('reference',audio.url!)} />
        <AudioReferenceCard name="长声音标题用于检查容器边界LongAudioReferenceLongAudioReference@V002" duration={null} playing={sound.playingId==='long-reference'} progress={sound.currentId==='long-reference' ? sound.progress : 0} onPlay={()=>sound.toggle('long-reference',audio.url!)} />
      </ComponentExample>
      <ComponentExample fullWidth title="分段播放器" rule="示例使用制作页同一份布局。制作页在同一作品或剧集跨场、换段或换版本时保持播放偏好。重复播放默认关闭，勾选后循环当前视频。开启连续播放时关闭并禁用重复播放，取消后由用户重新开启。示例演示这两个开关的联动。宽屏时显示右侧分段导航。播放器下方仅保留播放与布局控制；视频文件从资源下载获取。" usage="Nora 剧集制作、Iris 视频制作、Chloe 视频制作">
        <SegmentLayout wide={wide} navigation={<SegmentStageStrip segments={segments} selected={segment} onSelect={setSegment} vertical newVideoSegments={new Set(['P001'])} previousEnding={null} previousSelected={false} onPreviousSelect={() => {}} />} player={<SegmentVideo repeatControl={{ checked: repeat, onChange: setRepeat }} current={videoRecord} onTimeChange={setTime} retainSource={retainSample} wide={wide} onToggleWide={() => setWide(!wide)} continuous={continuous} continuousControl={<label className="scene-continuous"><input type="checkbox" checked={continuous} onChange={event => setContinuous(event.target.checked)} />连续播放</label>} playerRef={playerRef} />}>
          <section className="segment-script"><Rich html="<h3>示例分镜</h3><p>切换宽屏可查看播放器与分段导航的共同布局。</p>" /></section>
        </SegmentLayout>
        <p>示例播放位置：{time.toFixed(1)}秒</p><button onClick={() => playerRef.current!.seekTo(1)}>跳到1秒</button>
        <button onClick={() => playerRef.current!.seekTo(1, true)}>从1秒开始播放</button>
      </ComponentExample>
    </>}
    {category === 'production' && <>
      <ComponentExample fullWidth title="选集按钮" rule="点击只更新示例选集；制作页最多两列，窄屏单列。制作列表带时长的按钮统一48px单行，长标题省略并可悬停查看；displayName只控制显示，不改变选择键。可在制作状态前显示时长，*表示含计划值；片头片尾显示默认打开方案的时长，不累加独立方案；大纲不显示时长。集名状态与制作进度独立。" usage="分集大纲、剧集制作">
        <div className="episode-grid episode-grid-pairs">{(['待定集名', '临时集名', '最终定名'] as const).map((titleStatus, i) => <EpisodeButton key={titleStatus} duration={['1分20秒', '2分5.5秒*', undefined][i]} item={{ kind: 'episode', name: `EP00${i + 1}`, title: titleStatus === '待定集名' ? '待定' : '组件演示集与很长的题名显示检查', titleStatus, statusHtml: '<span class="status-badge status-gray">未开始</span>' }} onSelect={setSelected} />)}<EpisodeButton duration="9.4秒" item={{ kind: 'episode', name: '片头', statusHtml: '<span class="status-badge status-green">已完成</span>' }} onSelect={setSelected} /><EpisodeButton displayName="V001" duration="20秒*" item={{kind:'group',name:'V001-穿搭展示',title:'穿搭展示'}} onSelect={setSelected} /></div><p>已选择：{selected === 'one' ? '尚未选集' : selected}</p>
      </ComponentExample>
      <ComponentExample fullWidth title="分段与制作状态" rule="P001标记本轮新生成；可切换分段和横竖布局，悬停状态图标查看详情。整场视频可只显示分段导航。" usage="分段制作、宽屏分段导航、Nora Songssx 整场候选">
        <button onClick={() => setVertical(!vertical)}>{vertical ? '切换横排' : '切换竖排'}</button>
        <SegmentStageStrip segments={segments} selected={segment} onSelect={setSegment} vertical={vertical} newVideoSegments={new Set(['P001'])} previousEnding={null} previousSelected={false} onPreviousSelect={() => {}} />
        <SegmentStageStrip segments={segments} selected={segment} onSelect={setSegment} vertical={vertical} showStages={false} newVideoSegments={new Set(['P001'])} previousEnding={null} previousSelected={false} onPreviousSelect={() => {}} />
        <p>当前分段：{segment}</p>
      </ComponentExample>
    </>}
    {category === 'tasks' && <>
      <ComponentExample fullWidth title="运行任务卡片" rule="显示固定示例进度；“任务组详情”与来源会话同排靠右，长会话名省略并保留悬停全文；入口使用模拟回调。实际入口打开任务详情，查看全组进度与各成员；队列仍逐任务显示和执行。没有提交或轮询生成任务。" usage="全局任务进度">
        <TaskCard task={{ workspace_name: '示例资料区', id: 'showcase-running', group_id: 'showcase-group', project: '示例项目', title: '组件展示任务', task_type: 'image', prompt_id: null, status: 'running', connection: 'connected', node: '示例节点', remote_url: '', progress: { value: 3, max: 10 }, error: null, collected: 0, expected: 1, created_at: started, started_at: started, source_session_name: '本地组件演示' }} onDetails={() => setAction('示例任务组：已完成1 / 2项，真实入口显示各成员状态。')} />
      </ComponentExample>
      <ComponentExample fullWidth title="排队任务卡片" rule="“任务组详情”在标题行右侧，与运行卡片统一命名；暂停、恢复、插队和提交按钮只更新演示状态，不操作真实队列。组成员的详情入口可从排队阶段查看全组；这里仅演示回调。" usage="全局待提交与暂停列表">
        <LocalQueueCard task={{ queue: 'local', workspace_name: '示例资料区', id: 'showcase-queued', group_id: 'showcase-group', project: '示例项目', title: '本地演示队列', task_type: 'image', status: queueState, remote_url: '', created_at: started, source_session_name: '本地组件演示' }} position={1} onDetails={() => setAction('示例任务组：排队和执行仍按单任务进行。')} onAction={(_id, next) => { setAction(({ pause: '已暂停示例', resume: '已恢复示例', immediate: '已模拟立即提交', insert: '已模拟插队' } as Record<string, string>)[next]); if (next === 'pause' || next === 'resume') setQueueState(next === 'pause' ? 'paused' : 'local_queued'); }} />
        <p role="status">{action}</p>
      </ComponentExample>
    </>}
    {category === 'coverage' && <>
      <ComponentExample title="全站框架就在当前页面" rule="这些组件在当前页面已真实运行，不重复嵌套。任务侧栏点击外部收起，侧栏菜单、详情和通知操作不误关；展开时侧栏内滚轮不传给背景，内部列表正常滚动，到顶底不带动背景；本地队列保持排序滚动位置，处理进度及结果使用左下角公共消息。交互回归使用隔离队列，不以演示操作真实任务。" usage="所有页面">
        <ul><li>AppShell：顶部、正文与公共页脚。</li><li>ProjectSwitcher：左上角品牌旁的项目菜单。</li><li>TaskSidebar：左侧任务栏。</li><li>Notifications：左下角消息。</li><li>PageCheckStatus：页脚最近检查时间，使用实际查询结果。</li><li>BottomTools：页面向下滚动后出现的返回顶部按钮，并避让消息。</li></ul>
      </ComponentExample>
      <ComponentExample title="展示范围与业务模块" rule="可复用控件及业务卡片在各分类演示；下列整页业务模块需要真实资料，保留在原页面，不在这里启动真实业务。" usage="项目制作、任务管理与设置">
        <p>EpisodeProduction、EpisodeOutlines、SceneWorkspace、SegmentWorkspace、SceneDirectorSheets、SceneStoryboardEditor、RevisionNoteEditor、SceneDownloads、CoverLibrary、ReferenceLibrary属于业务页面或流程；SegmentWorkspace在候选选择栏下方复用MessagePanel统一展示资料问题、未生成及读取失败，普通和宽屏位置一致，问题默认折叠；SceneDownloads按轮次接入时读取现有轮次说明，画布入口支持分段、阶段、执行编号及工具与模式说明，沿用公共DownloadButton；TaskHistory、TaskDetailDialog、NodeEditor负责真实任务和节点数据。</p>
        <p>它们使用的按钮、导航、文档、媒体、消息、卡片及分页已在对应分类展示。Context、数据查询和缓存Hook属于内部逻辑，随所属组件验证。</p>
        <p>新增或修改公共组件时，必须在同次改动中同步这里的真实演示、说明与相关状态检查。</p>
      </ComponentExample>
    </>}
    {preview && <Preview project="" item={preview} revision={1} close={close} />}
  </PreviewContext.Provider>;
}
