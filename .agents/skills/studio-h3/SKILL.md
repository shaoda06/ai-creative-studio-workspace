---
name: studio-h3
description: MiniMax H3 共用提示词模式、正文格式、参考素材语义和导演台选择入口。
---

# Studio H3 共用规则

调用方提供实际生成模式、完整正文、参考文件和顺序、时长与授权。按实际模式阅读[官方提示词技能](../h3-prompt-writing/SKILL.md)。编写、修订和核对使用[参考与接续表达规范](references/参考与接续表达规范.md)，脚本 `scripts/h3_prompt_format.py` 负责通用正文检查。

按当前任务选择 [AiMixer 导演台](../studio-h3-aimixer/SKILL.md) 或 [Songssx 导演台](../studio-h3-songssx/SKILL.md)。已登记任务以原请求和画布为准。提交和恢复使用[共用 ComfyUI 工具](../studio-comfyui/SKILL.md)。技术完成与内容采用分别记录。
