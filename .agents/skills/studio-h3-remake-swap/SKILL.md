---
name: studio-h3-remake-swap
description: 已选定 Viggle Remake Swap 为原片替换一名表演者时使用。处理双参考图、换人提示词、长镜头续接、逐段生成和合片。
---

# Viggle Remake Swap 单人换人

按[单人换人流程](references/Viggle-Remake单人换人流程.md)核对源片、替换目标、参考图、画布与 API。调用方提供实际造型与参考分工、保留项、执行范围和授权。

编写正文时读取[共用提示词规范](../studio-h3-remake/references/Viggle-Remake提示词规范.md)，再按换人流程落实脸、发型、穿搭及各图的职责。按实际帧数限制准备 24 fps 源片，经[共用 ComfyUI 工具](../studio-comfyui/SKILL.md)逐段执行、取回并合片。结果交调用业务或 [Remake 外层流程](../studio-h3-remake/SKILL.md#两轮之间的交接)接续。
