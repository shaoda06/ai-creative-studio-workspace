---
name: studio-storyboard
description: 为短剧、商业视频和带货视频编写、修订及核对分镜，统一逐镜字段、时间、构图动作、声音与前后接续，以及导演分镜表制作和分页校验；由各业务阶段提供内容依据、编号和交付位置。
license: MIT
---

# Studio 共用分镜

收到编写、重做、局部修订或核对分镜的任务时使用。先明确调用业务给定的上游版本、内容范围、画幅、时长、参考及待确认项，再读取[分镜写作规范](references/分镜写作规范.md)，在该业务指定的文件中使用[逐镜正文模板](templates/逐镜正文模板.md)。模板字段和写法在本技能维护一份。

按实际播放顺序组织镜头；文件头、整片或场次结构、编号、保存、审批、轮次与交接由调用业务负责。业务补充字段接在逐镜基础字段后，或在同份文档的业务章节维护，引用相关镜号。现行文稿修订形成新版本，已提交请求继续追溯原执行依据。

## 导演分镜表

把文字分镜制作成图文导演表时，读取[通用制作规则](references/导演分镜表制作规范.md)，使用[唯一版式模板](templates/导演分镜表模板.md)及其制作计划校验。调用业务只提供来源、授权、保存、采用和交付接入，不另定义画法与列结构。图文导演表不同于H3原生导演包；后者由模型工具维护。

## 按问题选读

镜头方法查用[创作技法](../studio-creative-techniques/SKILL.md#镜头表达)和其完整动作链指南。涉及下表具体问题时选读对应资料，将选择落实到同一份逐镜正文。

| 问题 | 参考 |
| --- | --- |
| 镜头职责、对白覆盖、切点及镜长 | [镜头手艺](references/shot-craft.md)、[生产镜头语法](references/production-shot-grammar.md) |
| 不同取景方案、多人调度及信息覆盖 | [场次视觉计划](references/scene-visual-plan.md)、[调度方法](references/blocking-playbooks.md)、[覆盖比较](references/coverage-audition.md) |
| 光影、关键帧及漫剧视觉表达 | [光线设计](references/lighting-craft.md)、[关键帧方法](references/keyframe-craft.md)、[视觉词表](references/comic-keyframe-lexicon.md)、[转写示例](references/screenplay-to-keyframe-example.md) |
| 修订关联与连续性核对 | [镜头修订方法](references/shot-revision-identity.md)、[核对示例](references/review-and-fixtures.md) |
| 打斗、法术或写实格斗 | 按题材使用[通用动作](../studio-combat-methods/SKILL.md)、[玄幻动作](../studio-fantasy-combat/SKILL.md)或[写实格斗](../studio-realistic-combat/SKILL.md) |

方法资料中的编号和时长示例用于说明表达选择，实际文件和字段沿本模板及调用业务。H3等模型的格式、容量、标签和执行由对应模型工具负责，分镜明确的口型、声音与状态在后续转写中保留。

需要结构读取时，[字段读取器](scripts/storyboard_fields.py)从共用模板提取字段顺序，读取明确的逐镜块；业务检查器可传入业务补充字段并核对自身编号。

## 完成核对

按写作规范连读逐镜正文和必要的前后接点，检查来源覆盖、时间、可见范围、声音与口型、动作因果和状态延续。订正写回本稿，未解决项交回调用业务记录。交付指出本次版本、具体范围及关键取舍，由调用业务接续素材、提示词或用户审阅。
