---
name: studio-h3
description: 在规划 MiniMax H3 生成或原片编辑，或编写、修订与核对 H3 提示词时使用。维护正文格式、参考语义和时长规则，按实际工作流进入专项。
---

# Studio H3 共用规则

调用方提供实际生成模式、完整正文、参考文件和顺序、时长与授权。编写、修订或核对 H3 原生模式提示词时，按[依赖登记](../studio-entry/维护规范.md#独立第三方技能登记)定位实际安装的 `h3-prompt-writing`，选读对应模式及[参考与接续表达规范](references/参考与接续表达规范.md)。脚本 `scripts/h3_prompt_format.py` 负责通用正文检查。

- [AiMixer 导演台](../studio-h3-aimixer/SKILL.md)负责运行组和缓存一采、二采。
- [Songssx 导演台](../studio-h3-songssx/SKILL.md)负责 GEN 时间线和 SelfLift。
- 已有原片并使用 Viggle Remake 换人、换背景或连续完成两项时，进入 [Viggle Remake 视频编辑](../studio-h3-remake/SKILL.md)。

已登记任务以原请求和画布为准。提交和恢复使用[共用 ComfyUI 工具](../studio-comfyui/SKILL.md)。技术完成与内容采用分别记录。

## 生成段时长

MiniMax H3 官方输出规格为 24 fps、单次 4–15 秒。分镜规划采用本次选定的工作流与模式限制，入队前核对实际参数。模型规格、执行窗口和剪辑采用时长分别记录。[MiniMax H3 官方输出规格](https://github.com/MiniMax-AI/MiniMax-H3#system-overview)

- [Songssx 标准版 Ref2VA](../studio-h3-songssx/references/ComfyUI-Songssx导演台使用规范.md#单段时长与帧数校验)按 GEN 核对计划新增时长，以及包含入段重叠和帧格对齐的采样窗口。
- [AiMixer](../studio-h3-aimixer/references/ComfyUI-AiMixer导演台节点使用规范.md#5-时长帧数与编辑状态同步)按本次实际画布逐组核对请求时长及帧数。

## 动作速度询问

两套导演台的新任务均使用以下第 5 步。

**第 5 步｜是否要自定义动作速度？自定义时，请直接输入 −10～10 的数值。**

上一步选文戏或关闭打戏 LoRA 组时，只显示：

- 保持默认（文戏默认关闭速度 LoRA）

上一步选打戏或开启打戏 LoRA 组时，只显示：

- 保持默认（打戏默认 4.0）

文戏选择保持默认时，清单传 `speed: null`，装配脚本旁路 H3 Speed Slider。打戏选择保持默认时，传 `speed: 4.0` 并启用该节点。两种戏型都可直接输入 −10～10 内的数值，装配时启用节点并使用该数值。
