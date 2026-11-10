---
name: studio-h3-aimixer
description: 装配和接续 AiMixer 导演台视频任务，维护选组、素材槽位、缓存一采二采、逐段取回和历史请求读取。
---

# AiMixer 导演台

按[使用规范](references/ComfyUI-AiMixer导演台节点使用规范.md)确认场次分批、运行组、缓存及逐段成果。标准版的确认与装配读[参数与基准](references/参数与基准规范.md)。正文格式和参考语义读[共用 H3](../studio-h3/SKILL.md)。

装配使用 `scripts/h3_workflow.py`。后台通过本技能解释原生分段报告和核对目标缓存。恢复时读取原任务的输入和产物，按原组序、阶段及缓存身份接续。目录、批准和采用由调用业务负责。
