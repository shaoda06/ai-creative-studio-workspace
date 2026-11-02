---
name: nora-drama-images
description: 连续短剧图片业务阶段，规定人物、服装、场景、道具和集内图片的类型、内容、布局、规格、来源、候选及采用；Agent编写提示词，业务脚本整理记录，共用工具负责执行。
---

# Nora 图片资产制作

以当前项目资料卡、定位或分镜需求为依据完成本次图片任务。本阶段是二级业务技能，内部使用规则、模板和脚本模块，不再嵌套业务子技能。资料设计缺项回[资产资料](../nora-drama-assets/SKILL.md)，镜头需求回[分镜](../nora-drama-storyboard/SKILL.md)。

## 按对象和动作读取

| 任务 | 规则 |
| --- | --- |
| 图片制作范围与阶段依赖 | [核心参考图](references/核心参考图制作规范.md) |
| 人物、服装及穿衣角色图片 | [人物图片](references/人物参考图制作与记录规范.md) |
| 场景与机位、道具与虚拟界面 | [场景业务](references/场景图片制作规范.md)、[道具业务](references/道具图片制作规范.md) |
| 首帧与逐集专用图 | [首帧需求](../nora-drama-storyboard/references/首帧参考图规范.md)、[专用素材](references/逐集专用素材规范.md) |
| 类型模板、业务种子和状态图 | [Qwen业务适配](references/Qwen-Image-2.1-提示词规范.md) |
| 能力选择、参考资格及内容修订 | [图片提示词业务规则](references/图片提示词规范.md) |
| 内置生成交接及原图送审 | [内置图片接续](references/内置图片制作接续规范.md) |
| 获批尺寸处理与正式保存 | [批准后处理](references/图片批准后处理规范.md)、[后处理业务](references/图片后处理业务规范.md) |
| 固定脚本、参数及结果恢复 | [业务执行接口](references/图片业务执行规范.md) |

## Agent和脚本分工

Agent理解任务，确定图种及布局、写作并核对实际提示词，选择获授权的具体参考和顺序，处理真实设计缺项。业务脚本读取明确资料、核对来源资格、分配候选、维护原工作稿和批准关联。模型工具脚本原样装配已备正文及参考；后台排队、提交、监控和取回。用户审阅画面并选择采用。

按[业务能力选择](references/图片提示词规范.md#当前参考图生成选型)进入[Imagegen](../studio-imagegen/SKILL.md)或[Qwen](../studio-qwen-image/SKILL.md)，获批后调用[图片处理](../studio-image-processing/SKILL.md)。[浏览后台](../studio-workspace-browser/SKILL.md)提供执行及展示，不替本阶段决定图种或采用。已备提示词只做原样执行，不由脚本重新创作。

技术完成、业务登记、网页同步和用户采用分别记录。文件核对不等于画面已符合目标，查看范围沿[媒体查看边界](../nora-serial-drama/references/业务工作约定.md#看图能力调用边界)。恢复只处理失败步骤，不重复生成。修改本阶段及资源时按[维护规范](../studio-entry/维护规范.md)完成适用复查。
