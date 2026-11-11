---
name: studio-h3-remake
description: 使用 Viggle Remake Swap 为已有视频替换一名表演者，维护双参考图画布与 API，准备分段、参考绑定、提示词、逐段生成及合片。
---

# Viggle Remake 单人换人

使用[单人换人流程](references/Viggle-Remake单人换人流程.md)核对画布、API 和当前试行步骤。调用方提供源视频、要换的表演者、两张参考图及各自分工、需要保留的画面和声音、执行范围与授权。具体造型选用、候选审阅和采用按调用业务执行。

按 Remake 的实际帧数限制准备 24 fps 源片，按绑定顺序写 Viggle 六段提示词。每个请求对应一个源片分段。已有生成授权时经[共用 ComfyUI 工具](../studio-comfyui/SKILL.md)提交、恢复和取回，按记录的保留帧数裁去补齐帧，再按原片顺序合片。只准备时交付本次分段、提示词及实际输入映射。
