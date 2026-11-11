---
name: studio-video-processing
description: 共用视频技术处理，按明确源文件、尺寸、帧率和裁切要求装配RIFE/RTX工作流并读取客观媒体信息；不决定业务来源采用、目标规格或下一阶段。
---

# Studio 视频处理

媒体原件、上传参考音视频及修改版本统一按[项目资源与版本](../studio-workspace-browser/references/项目资源与版本管理.md)保存。调用业务维护原记录及采用，输入、审核、采用及导出引用准确版本。

调用阶段提供实际输入、输出及授权；Agent按[后处理分步询问](references/视频技术处理规范.md#后处理分步询问)补齐输出分辨率、帧率及必要的画面适配选择。Agent解释目标与实际限制；脚本装配确定参数、保留原声和播放时长，并读取客观媒体信息，不判断内容是否获批。

媒体核对调用[scripts/video_metadata.py](scripts/video_metadata.py)的`probe(path)`，只读ffprobe的轨道与容器信息，不抽帧、转写或审片。缺少依赖或格式异常如实失败；不将推荐规格填写为实测值。

视频后处理使用[统一基准与实际装配](references/视频技术处理规范.md#实际装配)，按源片与目标规格选择插帧、尺寸处理和裁切。任务字段与原规格复用按[调用接口](references/视频技术处理规范.md#调用接口)，通信与排队调用[ComfyUI](../studio-comfyui/SKILL.md)和[后台](../studio-workspace-browser/SKILL.md)。技术任务填写 `video_plan.adapter:"technical"`。业务维护源版本、候选、采用与正式位置。
