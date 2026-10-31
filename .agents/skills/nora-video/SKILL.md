---
name: nora-video
description: Nora AI视频创作与制作统一入口，识别业务类型并路由一级业务技能，登记共用工具及其开发维护入口；不规定具体业务阶段的制作规则。
---

# Nora AI视频创作与制作

先识别当前业务、项目和实际动作，再进入对应业务入口。项目已有明确阶段时直接进入该阶段，不重新走全流程。用户授权和项目约定按原适用范围执行。

## 业务入口

| 任务 | 入口 |
| --- | --- |
| AI连续短剧及其单集制作 | [连续短剧业务](../nora-serial-drama/SKILL.md) |
| 商业视频订单 | 按项目AGENTS和README指定的商业业务入口，不套短剧目录；业务技能由实际工作区提供 |
| 独立剧情短片或其他视频 | 先确定实际业务及交付范围，已有项目规则优先；不因调用图片工具初始化短剧 |

## 共用工具登记

| 能力 | 入口 |
| --- | --- |
| 内置图片生成与编辑 | [Imagegen](../nora-imagegen/SKILL.md) |
| 远端Qwen图片提示词和装配 | [Qwen图片工具](../nora-qwen-image/SKILL.md) |
| 明确音频区间的本地裁剪与技术核对 | [本地音频工具](../nora-audio-processing/SKILL.md) |
| 图片尺寸处理、RTX及技术文件核对 | [图片处理工具](../nora-image-processing/SKILL.md) |
| 提交、查询、取回和服务开发维护 | [浏览服务与任务后台](../nora-workspace-browser/SKILL.md) |
| ComfyUI通信、配置及诊断依赖 | [ComfyUI工具](../nora-comfyui/SKILL.md) |
| H3视频任务 | 使用现行[视频执行入口](../nora-generation/SKILL.md)及[提示词入口](../nora-video-prompts/SKILL.md) |
| 视频读取、提示词库和风格库 | [视频读取](../video-study/SKILL.md)、[提示词管理](../nora-prompt-library/SKILL.md)、[风格库](../krea2-style-library/SKILL.md) |

主入口只维护职责和路由。图种、内容、布局、规格、来源资格、采用及业务完成条件由业务阶段维护；工具文档维护模型和接口要求。Agent负责理解、创作与语义核对，脚本负责确定性装配、文件处理和执行。

维护时使用skill-creator；按所改业务或工具的维护入口执行。跨体系结构及唯一真源要求见[结构维护](../nora-ai-short-drama/维护规范.md#规则真源与引用)，不因本入口改变历史任务或实际授权。
