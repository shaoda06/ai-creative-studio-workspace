---
name: nora-serial-drama
description: AI连续短剧一级业务入口，管理全剧与逐集流程、阶段职责和接续，路由业务阶段并说明共用工具使用时机。
---

# Nora AI连续短剧制作

先读取项目AGENTS、README和当前进度，按实际对象和授权进入当前阶段。一级维护流程、阶段职责和跨阶段约定；实际创作、记录和工具输入由对应阶段负责。

## 阶段路由

| 当前工作 | 负责入口 |
| --- | --- |
| D01 定位、画风及建档 | [项目定位与建档](../nora-drama-positioning/SKILL.md) |
| D02 主旨、简介和世界观 | [主旨简介与世界观](../nora-drama-worldbuilding/SKILL.md) |
| D03 全剧故事大纲 | [故事大纲](../nora-drama-story/SKILL.md) |
| D05 分集索引、大纲及拆集 | [分集规划](../nora-drama-episodes/SKILL.md) |
| 人物、场景、道具资料卡和参考音视频 | [资产资料](../nora-drama-assets/SKILL.md) |
| 图片资产、图片提示词、候选及批准后保存 | [图片业务阶段](../nora-drama-images/SKILL.md) |
| 单集剧本、对白、表演 | [剧本](../short-drama-write/SKILL.md) |
| 镜头、P段、首帧需求和导演表内容 | [分镜](../short-drama-storyboard/SKILL.md) |
| 视频提示词、视频制作及返修 | [提示词](../nora-video-prompts/SKILL.md)、[视频执行](../nora-generation/SKILL.md) |
| 专项审查 | [审查](../short-drama-review/SKILL.md) |
| 本集交接、完成与复盘 | [本集收尾](../nora-ai-short-drama/references/流程规范/逐集目录与资产管理规范.md#5-分段交付与本集完成) |
| 运营及发布 | [运营入口](../nora-social-operations/SKILL.md) |

上游、产出和接续关系见[流程表](references/阶段流程与接续规范.md#整体流程)。阶段完成按其实际规则判断，不将阶段路由增加为审批。正式目录、编号和版本按[业务文件规范](../nora-ai-short-drama/references/共用规则/文件版本与工作稿规范.md)执行。

图片阶段调用Imagegen、Qwen、图片处理和任务后台；业务输入资格、类型和规格留在图片阶段。工具结果完成后交回业务登记，技术成功不替代用户采用。需要跨阶段返修时按[返修归属](../nora-ai-short-drama/references/共用规则/制作返修与完整重做规范.md)回到负责阶段。

## 业务内共用约定

- [原稿接续](references/原稿接续规范.md)：各创作阶段实际读取、复用及处理缺项冲突；不要求纯技术操作通读原稿。
- [项目接续](references/项目接续规范.md)：已有项目、正式更名及授权整理；新建交D01。
- [准备文档表达](references/准备文档表达规范.md)：有具体表达问题时润色，保留事实和固定字段。
- [开发方法使用](references/开发方法使用规范.md)：方法资源的适配边界；阶段SKILL维护具体读取时机。

目录、编号、文件版本和项目进度仍引用各自有效业务规范。一级只组织流程、职责和接续；阶段实际做法与脚本由二级维护，共用工具的全局登记由nora-video负责。
