---
name: studio-realistic-combat
description: 为写实格斗、警匪追逐、动作喜剧及小规模多人战斗提供步法、防守、动力链和真实受力方法。
---

# Studio 写实格斗方法

## 学习与反馈维护

用户要求吸收本领域图文／视频技巧时，调用[创作技法学习与维护](../studio-creative-techniques/SKILL.md)的学习分支，查重后原位更新本专项参考，不复制另一份库。实际采用具体候选写法时按[首次使用提示](../studio-creative-techniques/references/学习与反馈维护规范.md#首次实际使用时的提示)处理；收到针对性实际反馈按[反馈复核](../studio-creative-techniques/references/学习与反馈维护规范.md#实际反馈复核)更新对应写法与条件。日常设计仍按下方方法，不因查用而自动扩库或生成测试。

## 业务接入与方法使用

当前业务的输入、格式、批准和交付由调用方负责；共用接入边界、专项选择及读取范围统一见[调用与阅读](../studio-combat-methods/references/调用与阅读规范.md)。

## 完整制作与局部修改

先按[完整制作与局部修改](../studio-combat-methods/references/调用与阅读规范.md#完整制作与局部修改)确定本次范围，再执行下列本专项步骤。

1. **明确依据与写实档位**：核对剧情目的、人物能力、武器持握、开场距离、站位、伤损、环境和风格。读[R1核心](references/r1-combat-core.md)的定位、节拍弧、开局、收尾与招式库从属要求；只有符合对应场景的节奏、情绪和收束方法才采用，不把案例时点套到所有场面。
2. **编排攻防动作**：读[动力链](references/kinetic-chain-11.md)和[基本技法](references/real-fight-techniques.md)，关键打击推导完整发力链，正文压缩到可读要件；过渡动作交代起势、接触与状态即可。结合[防守与闪避](references/defense-evasion-rules.md)写出抵抗、失衡、卸力或反应，不让对手只被动平移；受力不明确时补[impact-physics](references/impact-physics.md)。
3. **落实空间与镜头**：分镜阶段读[camera-action-specs](references/camera-action-specs.md)，让关键接触、步法、重心及防守变化看得清，镜长服从实际动作。用户点名武学或要求细化具体技法时读对应[martial-styles-extended](references/martial-styles-extended.md)；连招需要读[technique-combo-library](references/technique-combo-library.md)，多人战斗读[multi-opponent-rules](references/multi-opponent-rules.md)。执行R1核心“取神不取形”：采用技法的发力方向和接触反馈，不整套照搬招式顺序或箭头串。
4. **合并检查与转写交接**：按R1核心启发式自检和当前使用方法，核对攻防因果、受力、步法、状态接续及节拍变化；分镜阶段直读通用[节奏负载](../studio-combat-methods/references/combat-rhythm-and-load-guardrails.md)与[力度与节奏参考](../studio-combat-methods/references/combat-intensity-guardrails.md)中的R1适用条件，不套R3爆炸强度。只在明确转写Seedance时读[render-adapters](references/render-adapters.md)，其他模型由视频提示词技能转写。订正并入本次业务自检，不新增复验报告。

局部问题按下表定位，读取边界沿[共用调用规范](../studio-combat-methods/references/调用与阅读规范.md#完整制作与局部修改)。

## 按任务选择规则

| 当前问题 | 方法文件 |
| --- | --- |
| 写实定档、节拍与收束 | [r1-combat-core](references/r1-combat-core.md) |
| 关键打击的动力链 | [kinetic-chain-11](references/kinetic-chain-11.md) |
| 基本招式选择 | [real-fight-techniques](references/real-fight-techniques.md) |
| 镜头、空间与景别 | [camera-action-specs](references/camera-action-specs.md) |
| 防守、闪避及受击 | [defense-evasion-rules](references/defense-evasion-rules.md) |
| 受力与环境反馈 | [impact-physics](references/impact-physics.md) |
| 用户点名武学或需要具体技法 | [martial-styles-extended](references/martial-styles-extended.md) |
| 连招、踢击部位、情绪拐点及化劲 | [technique-combo-library](references/technique-combo-library.md) |
| 多人调度 | [multi-opponent-rules](references/multi-opponent-rules.md) |
| 明确采用Seedance时的封装参考 | [render-adapters](references/render-adapters.md) |
| 需要完整范例 | [storyboard-example](references/storyboard-example.md) |

跨专项引用按[共用读取范围](../studio-combat-methods/references/调用与阅读规范.md#完整制作与局部修改)执行。

## 交付

把方法落实到本次获授权正文，由负责业务技能合并自检；只提出确实影响当前任务的缺项。素材查看、自动重试、模型切换、生成及采用按当前业务与用户授权执行，专项设计本身不授予这些权限。
