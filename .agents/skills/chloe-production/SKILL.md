---
name: chloe-production
description: Chloe 带货视频整片制作阶段，组织生成候选审阅、后处理、局部返修、准确版本采用及公共制作工作台接入。
---

# Chloe 视频制作

接续本条生成、返修或资产补缺时，先核对[项目专用约定](../chloe-commerce-video/references/会话组织与接续规范.md#项目专用约定的记录与执行)，再按[会话组织与接续](../chloe-commerce-video/references/会话组织与接续规范.md)确定视频会话及相关资产入口。

随后读取本视频 README、脚本及制作记录。固定写法按[资料规范](../chloe-positioning/references/固定资料写法规范.md)，分段、轮次、审阅、恢复、采用及网页映射按[视频制作流程与记录](references/视频制作流程与记录.md)。

按共用视频制作核心的[工作流选择](../studio-video-production/SKILL.md#工作流选择)确定本次工作流，再接续[生成资产与提示词](../studio-video-production/SKILL.md#生成资产与提示词)及[请求核对与生成](../studio-video-production/SKILL.md#请求核对与生成)。按[候选交回](../studio-video-production/SKILL.md#候选与技术结果交回)接收候选和技术结果，本阶段组织整片审阅、返修、后续执行与采用。

开始或继续提示词准备、生成及返修任务时，按[复盘建议接续](../chloe-review/SKILL.md#建议接续与验证回填)读取适用建议及已有T记录；执行中的T关联、分段和准确输出及原用户审阅依据的交回按[阶段记录落点的视频制作项](../chloe-review/SKILL.md#阶段记录落点)执行。

视频生成提示词按[固定文件规范](references/视频制作流程与记录.md#视频提示词文件)及[模板](templates/视频提示词模板.md)保存模型正文与中文参考，制作记录只链接原件。

确认本条视频的画幅、分段和声音；画幅不设默认。镜头参考按[共用用途与绑定](../studio-storyboard/references/分镜写作规范.md#镜头参考图与首帧)判断。需制作镜头图时，由本视频会话调用[镜头参考图流程](../chloe-assets/references/镜头参考图制作流程.md)，完成用户批准、2倍超分、尺寸核对及正式登记后绑定准确版本。

按[整片制作与审批](references/视频制作流程与记录.md#配置与整片推进)接续所选工作流的候选审阅、返修与后处理，用户负责视频内容审阅。

整片满足接续条件后，按[核心执行入口](../studio-video-production/SKILL.md#按业务决定调用执行工具)提供获批源片、目标与授权，制作记录引用原请求和结果报告。

按[采用与直接沿用](references/视频制作流程与记录.md#无需后处理时直接沿用)核对已批准源片和技术规格。采用组合交[剪映交接](../chloe-handoff/SKILL.md)，人工后期前仍为制作中。

资料更新后运行固定资料检查和本阶段 `scripts/chloe_production.py check --project <视频项目绝对路径>`。网页使用完整公共制作工作台，本技能只维护资料映射，不维护另一套播放器、审阅控件或任务监控。

收到后台通知后先区分任务类型：镜头图片超分按[镜头图接续](../chloe-assets/references/镜头参考图制作流程.md#5-批准后2倍超分与自动采用)完成图片尺寸核对、正式登记及汇报，不推进视频轮次；视频任务才按[视频结果接续](references/视频制作流程与记录.md#后台结果接续)回写原执行并进入对应整片审阅或后处理采用。

任务的自动登记按[共用任务接入](../studio-workspace-browser/references/业务接入规范.md#chloe-视频结果登记接入)关联原执行和轮次。通知接续整片审阅、异常或已有授权的下一阶段。
