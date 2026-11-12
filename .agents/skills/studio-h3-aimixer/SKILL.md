---
name: studio-h3-aimixer
description: 在已选择 AiMixer 导演台，需要配置、装配、核对或接续原任务时使用。处理运行组、素材槽位、缓存一采二采与逐段取回。
---

# AiMixer 导演台

按[使用规范](references/ComfyUI-AiMixer导演台节点使用规范.md)确认场次分批、运行组、缓存及逐段成果。标准版的确认与装配读[参数与基准](references/参数与基准规范.md)。正文格式和参考语义读[共用 H3](../studio-h3/SKILL.md)。

装配使用 `scripts/h3_workflow.py`。后台通过本技能解释原生分段报告和核对目标缓存。恢复时读取原任务的输入和产物，按原组序、阶段及缓存身份接续。目录、批准和采用由调用业务负责。
