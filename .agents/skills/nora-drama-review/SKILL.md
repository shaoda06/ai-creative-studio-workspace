---
name: nora-drama-review
description: 连续短剧D12专项审查与合并自检，对 Nora 的原稿分析、故事、剧本、资产、分镜及图片视频提示词进行专项审查，或为当前作者提供合并自检方法；媒体内容审查须有实际查看授权。
license: MIT
---

# Nora 专项审查与自检

本技能承担 Nora 的当前业务交付；直接调用遵循[业务技能共同约定](../nora-serial-drama/references/主控操作规范.md#业务技能共同约定)，按下方当前任务入口接续。

## 合并自检与专项审查

创作者按[文本自检与订正](references/文本自检与订正规范.md)在当前任务合并检查并按授权改回来源；不为使用本技能增加新会话、独立审查报告或批准阶段。只受托审查时按[问题交付](references/文本审查与返修规范.md#文本审查问题与交付)用[共用问题说明](../studio-creative-techniques/references/审查与返修方法.md#说明一个问题)给出审查意见，不擅自修改来源。用户另行授权修改时由对应业务技能接续。

## 按对象选择

| 对象或问题 | 方法与业务依据 |
| --- | --- |
| 原稿分析与改编 | [原稿审查](references/rubric-source-analysis.md)及[原稿边界](../nora-serial-drama/references/原稿接续规范.md) |
| 故事与单集剧本 | [故事剧本审查](references/rubric-story-script.md)，对应开发／写作规则、人物及采用原稿 |
| 人物、场景、道具资料卡 | [资产与提示词审查](references/rubric-assets-prompts.md)及[D04资料设计](../nora-drama-assets/SKILL.md)对应卡片规则 |
| 图片提示词及输入资格 | 同一审查方法结合[D06图片业务](../nora-drama-images/SKILL.md)对应图种及工具引用 |
| 分镜、首帧与视频提示词文本 | [视觉运动审查](references/rubric-visual-motion.md)、[文本方法适配](references/文本审查与返修规范.md#文本审查的方法补充)，核对当前镜头、P段和实际输入 |
| 表情表达检查或生成后的具体表情反馈 | [表情拆解](../studio-creative-techniques/SKILL.md#表情表达)；分镜允许抽象表情，模型正文检查具体面部变化。文本检查不构成生成验证；真实反馈按该技能更新参考表的验证情况，不因此取得修改项目来源或查看媒体的授权 |
| 镜头表达检查或针对实际镜头效果的反馈 | [镜头语言与表达](../studio-creative-techniques/SKILL.md#镜头表达)，核对观看目的、可见过程及相容性；指南验证更新沿其反馈规则，文本检查不等于生成有效，也不扩大媒体查看或项目修订授权 |
| 转场、特效或动作等技法的实际效果反馈 | [共用反馈复核](../studio-creative-techniques/references/学习与反馈维护规范.md#实际反馈复核)，按主题归属更新原专业参考；文本检查与媒体查看边界沿原任务 |
| 如何说明问题与复核 | [审查方法](references/review-method.md)；返修归属以[共用规则](../nora-serial-drama/references/制作返修接续规范.md)为准 |
| 模板感及重复写法 | [反模板方法](references/anti-template-repair.md)，具体表达按[共用中文润色](../studio-creative-techniques/references/对白与场次表演方法.md#中文表达润色)处理 |
| 用户授权的媒体审查与生产观察 | [生产质量参考](references/production-quality-gates.md)、[项目校准方法](references/project-calibration.md)，仅在主控允许的查看范围内使用 |

## 完成与边界

具体标准由所属业务规则维护，本技能引用，不复制第二套阈值。剧本和分镜按[山音适配](../nora-serial-drama/references/山音方法适配规范.md)合并当前适用检查，提示词的内容核对仍由[提示词规则](../nora-video-prompts/references/视频提示词制作规范.md#模型正文的内容核对)负责。依据[交付核对](references/交付核对规范.md)完成本次范围。

文本通过、工具技术通过、媒体结果符合要求和用户批准分别记录。纯文本审查不授权看图、审片、自动重生成或另派Agent；媒体查看沿[主控边界](../nora-serial-drama/references/业务工作约定.md#看图能力调用边界)。问题和结论并入既有工作稿、审阅记录或当前交付，不新建外部JSON裁决和审批状态；真实未决项明确说明。

## 输入、记录与脚本

输入是本次实际文本、明确来源版本、必要业务规则和审查/修订权限。审查标准以负责阶段为真源；资料卡设计、图片制作和模型输入分别按其实际对象选读，工具技术限制不由审查另定。

输出为当前交付或既有工作稿中的位置、依据、影响、建议及未决项；继续复用[共用工作稿的审阅结构](../nora-serial-drama/templates/工作稿模板.md)，不新建一份正式审查报告或审批状态。原生finding/verdict样例及[脚本使用规范](references/脚本使用规范.md)只供方法或机械格式核对，不生成中文内容质量结论。Agent承担事实与语义判断，脚本不能批准；业务修订交回负责阶段，媒体查看仍按真实授权。
