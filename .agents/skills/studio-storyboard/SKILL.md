---
name: studio-storyboard
description: 在根据脚本编写、修订或核对分镜，或制作图文导演表时使用。统一逐镜构图、动作、声音、时码、前后接续及导演表分页。
license: MIT
---

# Studio 共用分镜

收到编写、重做、局部修订或核对分镜的任务时使用。先明确调用业务给定的上游版本、内容范围、画幅、时长、参考及待确认项，再读取[分镜写作规范](references/分镜写作规范.md)，在该业务指定的文件中使用[逐镜正文模板](templates/逐镜正文模板.md)。模板字段和写法在本技能维护一份。

按实际播放顺序组织镜头；制作对象、场次与分段按[共用制作层级](references/分镜写作规范.md#制作对象场次与分段)组织。文件结构、各层编号、保存、审批、轮次与交接由调用业务负责。业务补充字段接在逐镜基础字段后，或在同份文档的业务章节维护，引用相关镜号。现行文稿修订形成新版本，已提交请求继续追溯原执行依据。

## 导演分镜表

把文字分镜制作成图文导演表时，读取[通用制作规则](references/导演分镜表制作规范.md)，使用[唯一版式模板](templates/导演分镜表模板.md)及其制作计划校验。调用业务只提供来源、授权、保存、采用和交付接入，不另定义画法与列结构。

## 按问题选读

需要选择或细化拍法时读[镜头表达](../studio-creative-techniques/SKILL.md#镜头表达)。同一事件涉及连续动作或跨镜头接续时读[完整动作链指南](../studio-creative-techniques/references/完整动作链设计与转写指南.md)。其他问题按下表选读，将采用的方法落实到同一份逐镜正文。

| 问题 | 参考 |
| --- | --- |
| 台词时点、口型、场景文字、叠字与字幕 | [逐镜声源与口型](references/分镜写作规范.md#心理独白与开口对白的切换)、[画面文字与实现归属](references/分镜写作规范.md#画面文字与实现归属) |
| 镜头职责、对白覆盖、切点及镜长 | [镜头手艺](references/shot-craft.md)、[生产镜头语法](references/production-shot-grammar.md) |
| 不同取景方案、多人调度及信息覆盖 | [场次视觉计划](references/scene-visual-plan.md)、[调度方法](references/blocking-playbooks.md)、[覆盖比较](references/coverage-audition.md) |
| 镜头参考、首帧和开场状态 | [镜头参考图与首帧](references/分镜写作规范.md#镜头参考图与首帧) |
| 光影、关键帧及漫剧视觉表达 | [光线设计](references/lighting-craft.md)、[关键帧方法](references/keyframe-craft.md)、[视觉词表](references/comic-keyframe-lexicon.md)、[转写示例](references/screenplay-to-keyframe-example.md) |
| 修订关联与连续性核对 | [镜头修订方法](references/shot-revision-identity.md)、[核对示例](references/review-and-fixtures.md) |
| 打斗、法术或写实格斗 | 按题材使用[通用动作](../studio-combat-methods/SKILL.md)、[玄幻动作](../studio-fantasy-combat/SKILL.md)或[写实格斗](../studio-realistic-combat/SKILL.md) |

方法资料中的编号和时长示例用于说明表达选择，实际文件和字段沿本模板及调用业务。H3等模型的格式、容量、标签和执行由对应模型工具负责，分镜明确的口型、声音与状态在后续转写中保留。

需要结构读取时，[字段读取器](scripts/storyboard_fields.py)从共用模板提取字段顺序，读取明确的逐镜块；业务检查器可传入业务补充字段并核对自身编号。

## 完成核对

按写作规范连读逐镜正文和必要的前后接点，检查来源覆盖、时间、可见范围、声音与口型、动作因果和状态延续。订正写回本稿，未解决项交回调用业务记录。交付指出本次版本、具体范围及关键取舍，由调用业务接续素材、提示词或用户审阅。

根据实际生成效果修订分镜时，遇到针对某项技法的具体反馈，结合对应候选和实际提示词按[反馈复核](../studio-creative-techniques/references/学习与反馈维护规范.md#实际反馈复核)维护相应参考。项目修订及其审阅依据沿调用业务原记录保存。
