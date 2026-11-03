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
| 社交媒体运营及发布 | [运营一级业务](../nora-social-operations/SKILL.md) |
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
| Markdown与实际配图的带水印PDF | [PDF导出](../studio-pdf-export/SKILL.md)，业务批准留调用方 |
| 浏览器任务页、标签组和窗口收尾 | [浏览器操作](../studio-browser-operations/SKILL.md) |
| 视频读取、提示词库和风格库 | [视频读取](../studio-video-study/SKILL.md)、[提示词管理](../studio-prompt-library/SKILL.md)、[风格库](../studio-krea2-style-library/SKILL.md) |

所有业务与公共技能统一在总目录.agents/skills中维护。Nora资料在workspaces/Nora Workspace，Iris资料在workspaces/Iris Workspace；先明确真实项目，读取所属资料区README、项目README和唯一进度或状态文件，再按同库入口接续。用户只需从总工作区新建对话，不要求切换到子目录发现技能。

调用公共脚本时显式传入所属资料空间或实际项目，不以脚本所在总目录判断业务归属。后台查询与通知按[任务空间接续](../studio-workspace-browser/references/浏览服务使用规范.md#项目空间与统一入口)执行。

主入口只维护职责和路由。图种、内容、布局、规格、来源资格、采用及业务完成条件由业务阶段维护；工具文档维护模型和接口要求。Agent负责理解、创作与语义核对，脚本负责确定性装配、文件处理和执行。

## 共用方法与资料

[创作技法](../studio-creative-techniques/SKILL.md)、[通用打戏](../studio-combat-methods/SKILL.md)、[玄幻动作](../studio-fantasy-combat/SKILL.md)、[写实格斗](../studio-realistic-combat/SKILL.md)按任务实际需要引用。它们提供方法，不管理制作阶段或批准；旧表情、镜头入口只跳转同一来源。

维护时使用skill-creator；按所改业务或工具的维护入口执行。跨体系结构及唯一真源要求见[结构维护](维护规范.md#规则真源与引用)，不因本入口改变历史任务或实际授权。


## 工作区说明与项目建档

新增一级子工作区时读取[工作区结构与README规范](references/一级子工作区结构与README规范.md)及其模板。业务项目结构和README由对应业务建档入口维护，具体映射见该规范，不在统一入口复制业务细则。后两层README按实际项目主动读取，AI Creative Studio根AGENTS.md保留全局指令。
