---
name: nora-imagegen
description: 共用内置Imagegen生成与编辑工具，说明Agent实际调用、参考输入、原生结果保存和异常恢复；不规定业务图片类型、布局、正式规格或采用流程。
---

# 内置Imagegen工具

由Agent调用当前可用的内置imagegen工具，使用实际工具说明和imagegen技能。调用方提供完整内容、参考图顺序、目标比例及有效授权；本工具不规定角色视图或业务目录。本地生图指会话内置能力，不表示本机GPU生成。

实际调用、执行代理、原生结果和恢复要求见[工具调用](references/Imagegen工具调用规范.md)。scripts/imagegen_tool.py只生成已备调用正文及原字节保存结果，不通过CLI执行生图，不创建ComfyUI任务。提示词的内容及模型语义适配由Agent负责。

原生结果交回业务登记与审阅；原始像素、请求比例及正式目标分别保留。需要尺寸处理时由调用方提供允许的处理和目标，进入[图片处理工具](../nora-image-processing/SKILL.md)。不因尺寸差异自动重生、换能力或裁图，不伪造模型版本、种子和远端ID。
