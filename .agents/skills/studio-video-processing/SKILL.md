---
name: studio-video-processing
description: 在已有视频需要核对规格、裁切、RTX 或 RelayVSR 超分、RIFE 插帧时使用。按源片、目标规格和实际选择装配并核对技术结果。
---

# Studio 视频处理

媒体原件、上传参考音视频及修改版本统一按[项目资源与版本](../studio-workspace-browser/references/项目资源与版本管理.md)保存。调用业务维护原记录及采用，输入、审核、采用及导出引用准确版本。

调用阶段提供实际输入、输出及授权。按已选工作流补齐需要的规格。按交付规格装配 RTX、RIFE 或通用尺寸处理时，使用[后处理分步询问](references/视频技术处理规范.md#后处理分步询问)。脚本装配确定参数、保留原声和播放时长，并读取客观媒体信息。

审阅文件保留源片音轨。删除音轨或把音量置零须有用户明确要求。

媒体核对调用[scripts/video_metadata.py](scripts/video_metadata.py)的`probe(path)`，只读ffprobe的轨道与容器信息，不抽帧、转写或审片。缺少依赖或格式异常如实失败；不将推荐规格填写为实测值。

视频后处理使用[共用装配](references/视频技术处理规范.md#实际装配)，按本次选择读取专项指南。

| 工作流 | 调用条件 |
| --- | --- |
| [RTX 视频超分](references/RTX视频超分.md) | 按交付尺寸放大，或接在 RIFE 后面 |
| [RelayVSR 视频超分](references/RelayVSR视频超分.md) | 用 RelayVSR 做 2 倍放大，按指南本地裁段、成组提交和拼接，可接 RIFE |
| [RIFE 自动切镜保护插帧](references/RIFE视频插帧.md) | 按目标帧率重采样并保护真实切镜 |

普通任务字段与原规格复用按[调用接口](references/视频技术处理规范.md#调用接口)，通信与排队调用[ComfyUI](../studio-comfyui/SKILL.md)和[后台](../studio-workspace-browser/SKILL.md)。技术任务填写 `video_plan.adapter:"technical"`。业务维护源版本、候选、采用与正式位置。
