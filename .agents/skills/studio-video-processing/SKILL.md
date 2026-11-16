---
name: studio-video-processing
description: 在已有视频需要核对规格、裁切、RTX 或 RelayVSR 超分、RIFE 插帧时使用。按源片、目标规格和实际选择装配并核对技术结果。
---

# Studio 视频处理

媒体原件、上传参考音视频及修改版本统一按[项目资源与版本](../studio-workspace-browser/references/项目资源与版本管理.md)保存。调用业务维护原记录及采用，输入、审核、采用及导出引用准确版本。

调用阶段提供实际输入、处理目标及授权。脚本按所选工作流装配，保留原声和播放时长，并读取客观媒体信息。

审阅文件保留源片音轨。删除音轨或把音量置零须有用户明确要求。

媒体核对调用[scripts/video_metadata.py](scripts/video_metadata.py)的`probe(path)`，只读ffprobe的轨道与容器信息，不抽帧、转写或审片。缺少依赖或格式异常如实失败；不将推荐规格填写为实测值。

## 后处理工作流选择

接到新的视频后处理或超分请求时，先询问用户本次使用哪个工作流。结合源片和处理目标，列出适用的工作流或组合，说明实际差别和推荐依据。只有一个适用方案时也请用户确认。本次已明确选定的工作流或组合直接沿用。项目偏好和上一轮的选择可以作为推荐依据。

| 工作流 | 调用条件 |
| --- | --- |
| [RTX 视频超分](references/RTX视频超分.md) | 按交付尺寸放大，或接在 RIFE 后面 |
| [RelayVSR 视频超分](references/RelayVSR视频超分.md) | 用 RelayVSR 做 2 倍放大，按指南本地裁段、成组提交和拼接，可接 RIFE |
| [RIFE 自动切镜保护插帧](references/RIFE视频插帧.md) | 按目标帧率重采样并保护真实切镜 |

用户选定后读取相应指南，只补齐该工作流需要的规格，再按[共用装配](references/视频技术处理规范.md#实际装配)准备。按交付规格装配 RTX、RIFE 或通用尺寸处理时，使用[后处理分步询问](references/视频技术处理规范.md#后处理分步询问)。选型与执行授权分别核对，同一次确认已覆盖的批次沿用其选择。查询、取回及恢复原任务使用原执行记录的工作流。

普通任务字段与原规格复用按[调用接口](references/视频技术处理规范.md#调用接口)，通信与排队调用[ComfyUI](../studio-comfyui/SKILL.md)和[后台](../studio-workspace-browser/SKILL.md)。技术任务填写 `video_plan.adapter:"technical"`。业务维护源版本、候选、采用与正式位置。
