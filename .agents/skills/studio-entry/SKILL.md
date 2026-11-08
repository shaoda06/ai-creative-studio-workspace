---
name: studio-entry
description: AI创作与制作统一入口，识别业务类型并路由一级业务技能，登记共用工具及其开发维护入口；不规定具体业务阶段的制作规则。
---

# Studio 创作与制作总入口

先识别当前业务、项目和实际动作，再进入对应业务入口。项目已有明确阶段时直接进入该阶段，不重新走全流程。用户授权和项目约定按原适用范围执行。

## 业务入口

| 任务 | 入口 |
| --- | --- |
| AI连续短剧及其单集制作 | [连续短剧业务](../nora-serial-drama/SKILL.md) |
| 商业视频订单 | [Iris商业一级业务](../iris-commercial-video/SKILL.md)，不套短剧目录 |
| 自营账号AI视频带货、精选联盟选品与单条视频制作 | [Chloe带货一级业务](../chloe-commerce-video/SKILL.md) |
| 各业务账号及独立项目的社交媒体运营与发布 | [Studio运营一级业务](../studio-social-operations/SKILL.md) |
| 独立剧情短片或其他视频 | 先确定实际业务及交付范围，已有项目规则优先；不因调用图片工具初始化短剧 |

## 共用工具登记

| 能力 | 入口 |
| --- | --- |
| 内置图片生成与编辑 | [Imagegen](../studio-imagegen/SKILL.md) |
| 远端Qwen图片提示词和装配 | [Qwen图片工具](../studio-qwen-image/SKILL.md) |
| 明确音频区间的本地裁剪与技术核对 | [本地音频工具](../studio-audio-processing/SKILL.md) |
| 图片尺寸处理、RTX及技术文件核对 | [图片处理工具](../studio-image-processing/SKILL.md) |
| 提交、查询、取回和服务开发维护 | [浏览服务与任务后台](../studio-workspace-browser/SKILL.md) |
| ComfyUI通信、配置及诊断依赖 | [ComfyUI工具](../studio-comfyui/SKILL.md) |
| H3模型提示词、时间线、缓存与导演包 | [H3工具](../studio-h3/SKILL.md) |
| 视频RIFE/RTX装配及客观媒体信息 | [视频处理](../studio-video-processing/SKILL.md) |
| 明确清单的剪映草稿与ZIP/jypack | [剪映工具](../studio-jianying/SKILL.md) |
| 实拍剪辑、口播包装与配音解说动画 | [按需剪辑与动效工具](#按需剪辑与动效工具) |
| Markdown与实际配图的带水印PDF | [PDF导出](../studio-pdf-export/SKILL.md)，业务批准留调用方 |
| 整个项目归档／恢复、浏览分类及关联 Codex 对话收尾 | [项目归档](../studio-archive/SKILL.md) |
| 浏览器任务页、标签组和窗口收尾 | [浏览器操作](../studio-browser-operations/SKILL.md) |
| 视频读取、提示词库和风格库 | [视频读取](../studio-video-study/SKILL.md)、[提示词管理](../studio-prompt-library/SKILL.md)、[风格库](../studio-krea2-style-library/SKILL.md) |

所有业务与公共技能统一在总目录.agents/skills中维护。Nora资料在workspaces/Nora Workspace，Iris资料在workspaces/Iris Workspace，Chloe资料在workspaces/Chloe Workspace；先明确真实项目，读取所属资料区README、项目README和唯一进度或状态文件，再按同库入口接续。用户只需从总工作区新建对话，不要求切换到子目录发现技能。

调用公共脚本时显式传入所属资料空间或实际项目，不以脚本所在总目录判断业务归属。后台查询与通知按[任务空间接续](../studio-workspace-browser/references/浏览服务使用规范.md#项目空间与统一入口)执行。

主入口只维护职责和路由。图种、内容、布局、规格、来源资格、采用及业务完成条件由业务阶段维护；工具文档维护模型和接口要求。Agent负责理解、创作与语义核对，脚本负责确定性装配、文件处理和执行。

### 按需剪辑与动效工具

收到实际剪辑或动效任务后，先按项目授权确定可改动的音画、交付形式和主工具。沿用已确认字幕样式、仅换母片重对轴时，优先用项目已有的转写、ASS 和 FFmpeg 流程。需要下表能力时，只读取命中的工具入口，按授权补用其他工具。

| 入口 | 触发情况及调用条件 |
| --- | --- |
| [Herk Edit Kit（外部依赖）](维护规范.md#6-依赖获取与适配资料) | 已有口播底片，需复杂动效字幕、字卡或图形包装。底片和视觉方向明确，且需要 HyperFrames 预览或渲染时调用。 |
| [video-use（外部依赖）](维护规范.md#6-依赖获取与适配资料) | 已有多段实拍素材，获授权选镜头、排顺序或做初剪。探店、赶集等先看画面选段；访谈、对白剪辑可用转写和停顿辅助定切点。 |
| [Ghost Editor（外部依赖）](维护规范.md#6-依赖获取与适配资料) | 真人口播要做逐词弹字或特定风格包装，且已有明确的视觉参考或模板选择。先用短段核对中文字体、画幅和字幕避脸，再做整条。 |
| [video-talkcraft（外部依赖）](维护规范.md#6-依赖获取与适配资料) | 已有定稿和配音，需用 Remotion 制作解说图解、动态图表或整片动画。按原许可证仅用于非商业任务，商业使用须已有作者授权。 |

项目规则优先于上游示例的默认剪法、调色、音乐及交付位置。执行前核对所选分支的实际运行环境、素材范围和输出路径。新增外部转写、素材上传、付费服务、依赖升级或发布按对应任务授权处理。上述四项是另装依赖，链接通往公共来源登记；执行时按名称发现并读取实际安装入口。来源、固定版本和环境准备见[剪辑与动效工具来源](维护规范.md#剪辑与动效工具来源)。

## 共用方法与资料

逐镜编写、修订、导演分镜表制作与核对使用[共用分镜](../studio-storyboard/SKILL.md)，Nora、Iris、Chloe 的阶段入口提供内容依据与业务接续。

[创作技法](../studio-creative-techniques/SKILL.md)、[通用打戏](../studio-combat-methods/SKILL.md)、[玄幻动作](../studio-fantasy-combat/SKILL.md)、[写实格斗](../studio-realistic-combat/SKILL.md)按任务实际需要引用。它们提供方法，不管理制作阶段或批准；现行调用直达对应维护者，已退役入口不参与路由。

维护时使用skill-creator；按所改业务或工具的维护入口执行。跨体系结构及唯一真源要求见[结构维护](维护规范.md#规则真源与引用)，不因本入口改变历史任务或实际授权。


## 工作区说明与项目建档

首次下载或新增一级子工作区时，按[各业务初始化入口](references/一级子工作区结构与README规范.md#初始化与分发)创建本地资料区；已有工作区直接接续。新增一级子工作区时读取[工作区结构与README规范](references/一级子工作区结构与README规范.md)及其模板。业务项目结构和README由对应业务建档入口维护，具体映射见该规范，不在统一入口复制业务细则。后两层README按实际项目主动读取，AI Creative Studio根AGENTS.md保留全局指令。
