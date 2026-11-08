---
name: studio-combat-methods
description: 为武侠和动作场面提供构思、攻防因果、力量反馈、摄影与节奏方法；玄幻和写实专门问题按需进入对应专项。
---

# Studio 通用打戏方法

## 学习与反馈维护

用户要求吸收本领域图文／视频技巧时，调用[创作技法学习与维护](../studio-creative-techniques/SKILL.md)的学习分支，查重后原位更新本专项参考，不复制另一份库。实际采用具体候选写法时按[首次使用提示](../studio-creative-techniques/references/学习与反馈维护规范.md#首次实际使用时的提示)处理；收到针对性实际反馈按[反馈复核](../studio-creative-techniques/references/学习与反馈维护规范.md#实际反馈复核)更新对应写法与条件。日常设计仍按下方方法，不因查用而自动扩库或生成测试。

## 业务接入与方法使用

当前业务的输入、格式、批准和交付由调用方负责；共用接入边界、专项选择及读取范围统一见[调用与阅读](references/调用与阅读规范.md)。

## 完整制作与局部修改

先按[完整制作与局部修改](references/调用与阅读规范.md#完整制作与局部修改)确定本次范围，再执行下列本专项步骤。

1. **明确依据与构思**：核对已确认的剧情目的、人物强弱、开场位置、朝向轴线、持物、伤损、环境和画风。读[打斗构思](references/combat-construction.md)，将双方战法、优势变化、环境作用与结果落实到本阶段正文；按[强度定档](references/tier-and-finisher-system.md)选本场适用档位，不为套节奏改写已确认剧情。
2. **编排动作与镜头**：读[核心铁律](references/combat-iron-laws.md)的铁律0八步链，按“全局视听选择→本镜任务→机位→身体发力链→特效材质及生命周期→接触、受击与环境反馈→运镜因果→转场节律及反向核对”逐步落实。分镜阶段同时落实铁律2的独立画面、7的运镜动机及11的反馈链；具体招式、终结技、群战或法术再从下表取相应方法。
3. **写成可见动作**：分镜阶段读[自然句母版](references/eight-sentence-masters.md)，将实际用到的动作、释放、命中、位移、尺度与收势写入调用业务对应字段；不用招式名或抽象强度词代替过程。需要句法案例时再读syntax-corpus；明确转写Seedance时才进入其模型适配，其他模型由视频提示词技能处理。
4. **合并检查并订正**：用自然句母版的“出稿前每镜自问清单”、核心铁律45的重复与变化判断及构思文件的“构思自查”，检查因果、状态、反馈和整场是否重复平推。分镜阶段按本场档位读取[节奏负载](references/combat-rhythm-and-load-guardrails.md)与[力度与节奏参考](references/combat-intensity-guardrails.md)的适用部分；涉及特效时补[介质与分层](references/vfx-rendering-mandate.md)。问题随当前业务的交付自检一并订正。

局部问题按下表定位，读取边界沿[共用调用规范](references/调用与阅读规范.md#完整制作与局部修改)。

## 按任务选择规则

| 当前问题 | 方法文件 |
| --- | --- |
| 动机、强弱、赌注与环境 | [combat-construction](references/combat-construction.md) |
| 核心动作和摄影原则，按当前问题定位铁律 | [combat-iron-laws](references/combat-iron-laws.md) |
| 具体招式 | [moves-library](references/moves-library.md) |
| 动作句组织 | [eight-sentence-masters](references/eight-sentence-masters.md) |
| 句法与场景案例 | [syntax-corpus](references/syntax-corpus.md) |
| 强度定档、终结技与尺度 | [tier-and-finisher-system](references/tier-and-finisher-system.md) |
| 剑阵法相及大招 | [ultimate-array-library](references/ultimate-array-library.md) |
| 法术与大场面 | [spell-system](references/spell-system.md) |
| 场景与风格选择 | [presets-library](references/presets-library.md) |
| 摄影机、群战与复杂转场 | [combat-cheatsheet](references/combat-cheatsheet.md) |
| 命中反馈与负面表达 | [impact-frame-and-banlist](references/impact-frame-and-banlist.md) |
| 节奏负载；同时读适用条件与验证边界 | [combat-rhythm-and-load-guardrails](references/combat-rhythm-and-load-guardrails.md) |
| 激烈度和节奏零件；同时读默认建议及适用条件 | [combat-intensity-guardrails](references/combat-intensity-guardrails.md) |
| 特效介质与绘画表现 | [vfx-rendering-mandate](references/vfx-rendering-mandate.md) |
| 明确使用Seedance时的专项转译参考 | [seedance-dual-engine](references/seedance-dual-engine.md) |
| 需要补充动作选择与衔接 | [打斗动作与衔接参考库](references/打斗动作与衔接参考库.md) |

跨专项引用按[共用读取范围](references/调用与阅读规范.md#完整制作与局部修改)执行。

## 交付

把方法落实到本次获授权正文，由负责业务技能合并自检；只提出确实影响当前任务的缺项。素材查看、自动重试、模型切换、生成及采用按当前业务与用户授权执行，专项设计本身不授予这些权限。
