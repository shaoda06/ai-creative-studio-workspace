---
name: studio-video-processing
description: 共用视频技术处理，按明确源文件、尺寸、帧率和裁切要求装配RIFE/RTX工作流并读取客观媒体信息；不决定业务来源采用、目标规格或下一阶段。
---

# Studio 视频处理

调用阶段提供实际输入、宽高、帧率、裁切位置、方法、输出及授权。Agent解释目标与实际限制；脚本装配确定参数、保留原声和播放时长，并读取客观媒体信息，不判断内容是否获批。

媒体核对调用[scripts/video_metadata.py](scripts/video_metadata.py)的`probe(path)`，只读ffprobe的轨道与容器信息，不抽帧、转写或审片。缺少依赖或格式异常如实失败；不将推荐规格填写为实测值。

RIFE/RTX基准及参数装配按[技术处理规范](references/视频技术处理规范.md)，脚本`scripts/video_workflow.py`的`assemble`只接收方法、源路径、前缀、尺寸与裁切位置，不选择已采用来源；通信与排队调用[ComfyUI](../studio-comfyui/SKILL.md)和[后台](../studio-workspace-browser/SKILL.md)。技术任务明确`video_plan.adapter:"technical"`；业务另行维护源版本、候选、采用与正式位置。
