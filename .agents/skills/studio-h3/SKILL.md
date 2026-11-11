---
name: studio-h3
description: MiniMax H3 共用提示词模式、正文格式、参考素材语义和导演台选择入口。
---

# Studio H3 共用规则

调用方提供实际生成模式、完整正文、参考文件和顺序、时长与授权。按实际模式阅读[官方提示词技能](../h3-prompt-writing/SKILL.md)。编写、修订和核对使用[参考与接续表达规范](references/参考与接续表达规范.md)，脚本 `scripts/h3_prompt_format.py` 负责通用正文检查。

按当前任务选择 [AiMixer 导演台](../studio-h3-aimixer/SKILL.md) 或 [Songssx 导演台](../studio-h3-songssx/SKILL.md)。已登记任务以原请求和画布为准。提交和恢复使用[共用 ComfyUI 工具](../studio-comfyui/SKILL.md)。技术完成与内容采用分别记录。

## 动作速度询问

两套导演台的新任务均使用以下第 5 步。

**第 5 步｜是否要自定义动作速度？自定义时，请直接输入 −10～10 的数值。**

上一步选文戏或关闭打戏 LoRA 组时，只显示：

- 保持默认（文戏默认关闭速度 LoRA）

上一步选打戏或开启打戏 LoRA 组时，只显示：

- 保持默认（打戏默认 4.0）

文戏选择保持默认时，清单传 `speed: null`，装配脚本旁路 H3 Speed Slider。打戏选择保持默认时，传 `speed: 4.0` 并启用该节点。两种戏型都可直接输入 −10～10 内的数值，装配时启用节点并使用该数值。
