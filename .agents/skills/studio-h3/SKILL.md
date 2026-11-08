---
name: studio-h3
description: 共用MiniMax H3模型工具，维护配置选择与装配前询问、实际模式提示词格式、时间线与参考槽位、参数装配、缓存技术条件及原生导演包；不规定短剧流程、资产采用或EP编号。
---

# Studio H3视频生成工具

调用方提供明确模式、完整正文、参考文件和顺序、时长、参数、运行组序、缓存身份及输出目标。图片的业务制作规格、批准和采用沿调用业务，不从其他业务的示例或链接继承；本工具核对实际模式与输入作用，r2v普通Picture不等于硬首帧。Agent依据实际模式读取[h3-prompt-writing（外部依赖）](../studio-entry/维护规范.md#6-依赖获取与适配资料)对应指南，编写和适配语义；脚本做格式检查、帧数换算、槽位绑定、API装配和技术结果解释，不替Agent创作。

- 提示词完成后按[提示词自检与执行接续](references/参数与基准规范.md#提示词自检与执行接续)核对并推进；标准版装配前按[配置选择与询问](references/参数与基准规范.md#标准版配置选择与装配前询问)确定配置及方向；业务方提供项目默认来源及执行授权。
- 参数与API结构：[参数与基准](references/参数与基准规范.md#标准版配置参数)。脚本按明确配置装配，不因剧情标签自动改配置。
- 参考特征、保留说明和切镜／段间引导：[参考与接续表达](references/参考与接续表达规范.md)；逐组字符上限与计数见[长度规则](references/参数与基准规范.md#模型提示词长度)。
- 素材、时间线、缓存和输出：[导演台节点](references/ComfyUI-MiniMaxH3导演台节点使用规范.md)，只读取本次模式及操作章节。
- 按用户明确要求进行的原生包格式、导出和导入：[导演包](references/ComfyUI-MiniMaxH3导演包制作规范.md)。导入、导出与实际生成分别授权和记录。
- 已提交请求的只读制作页投影：scripts/h3_browser_context.py，读取实际镜头描述及参考槽位，不提交任务、不推断采用或用当前稿替代历史快照。
- 机械格式检查：scripts/h3_prompt_format.py；明确无缓存新输入的帧数装配：scripts/h3_timing.py。
- 六步答案装配、画布转换与明确素材绑定：scripts/h3_workflow.py；新一采通过任务清单h3_first_pass字段落实，字段与命令见[一采装配接口](references/参数与基准规范.md#任务清单字段与调用)；二采通过h3_second_pass只设置目标尺寸，见[二采装配接口](references/参数与基准规范.md#二采装配接口)；原生报告解释：scripts/h3_results.py；素材容量检查：scripts/h3_inputs.py；包内容技术核对：scripts/h3_pack.py；按重建清单临时原生导出：scripts/director_export.py。

准备与执行交[ComfyUI通信](../studio-comfyui/SKILL.md)和[持久后台](../studio-workspace-browser/SKILL.md)。通用技术任务使用`video_plan.adapter:"technical"`及明确输出，不要求人物卡、剧本、分镜、EP或短剧采用记录。短剧任务由D09/D10提供业务适配；省略adapter的旧任务保留原短剧语义，不追溯改写。

技术报告只能证明相应格式、提交、取回或缓存事实。模型生成、客户端导入、内容审核各自按实际执行结果报告。失败恢复原任务，不自动重新生成，不改变已批准参数及来源。
