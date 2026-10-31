---
name: nora-drama-positioning
description: 连续短剧D01项目定位与建档阶段，确定受众、题材、基调、制作规格和画风，按授权初始化目录与管理入口；不展开世界观、大纲或视频执行。
license: MIT
---

# Nora 项目定位与建档

先读取项目已有AGENTS、README和进度；新项目先确定实际根目录与当前授权。原稿、格式和跨阶段接续按[一级业务入口](../nora-serial-drama/SKILL.md)所指共用约定，已有有效决定直接复用。

## 当前动作

| 动作 | 规则与落实位置 |
| --- | --- |
| 确定受众、题材、背景、基调与制作形态 | [定位与画风](references/项目定位与画风规范.md)、[创作定位](references/创作定位规范.md)；填写[定位模板](templates/项目基本定位模板.md)，不提前展开完整剧情 |
| 选择画风、整理外部视觉描述或补齐画风依据 | [画风展开与验证](references/项目定位与画风规范.md#项目画风展开示例验证与复用)；完整正文、视频短版、必要语言适配和实际确认范围同页维护 |
| 确认封面、片头、片尾是否启用 | [可选配套](references/项目定位与画风规范.md#封面与片头片尾的可选安排)；逐项记录真实选择，不从选择推定生成授权 |
| 新建项目或获授权补齐目录 | [初始化规范](references/项目初始化规范.md)；调用所属scripts/project_init.py，登记总索引，不预填后续创作正文 |
| 已有项目接续、正式更名或旧结构整理 | [一级业务项目接续](../nora-serial-drama/references/项目接续规范.md)，不重复初始化 |

## 方法与工具

方向新写或实质修订时，按问题读取[故事方法](../nora-drama-story/references/story-craft.md)、[题材卡](references/genre-cards.md)或[导演阐述](references/director-brief-craft.md)，将受众兴趣、题材机制和视觉倾向落实到定位既有字段。采用方法前遵循[开发方法使用规范](../nora-serial-drama/references/开发方法使用规范.md)，不另建外部简报或引擎。

风格库仅在选择画风时调用[krea2-style-library](../krea2-style-library/SKILL.md)。获授权制作画风样例时，按本阶段验证规则调用[图片阶段](../nora-drama-images/SKILL.md)与其共用图片工具；样例属于定位验证，不登记为正式人物资产。浏览与同步使用[浏览工具](../nora-workspace-browser/SKILL.md)，不把网页实现写进定位规则。

## 输入输出与接续

输入是用户想法、相关原稿和已确认方向；正式创作产出只有`00-项目定位/项目基本定位.md`，项目进度属于跨阶段管理。Agent负责方向、画风正文和真实选择，脚本只按明确参数建目录及维护索引。交付按定位规则核对五章、字段、批准范围及适用的网页同步；文字确认、样图验证和媒体执行授权分别记录。

定位完成后进入[D02主旨简介与世界观](../nora-drama-worldbuilding/SKILL.md)。只完成局部修订时交回当前接续，不自动启动下一阶段或生成。
