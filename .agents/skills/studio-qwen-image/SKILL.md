---
name: studio-qwen-image
description: 在选用 Qwen Image 2.1 文生图或图生图，需要编写、核对提示词或装配请求时使用。按实际模式、规格、种子及参考图装配。
---

# Studio Qwen图片生成与编辑

调用方提供已授权的内容、模式、参考图、目标规格和输出位置。Agent按[qwen-image-2-1-prompter（外部依赖）](../studio-entry/维护规范.md#6-依赖获取与适配资料)的实际分支完成语义表达，脚本原样读取正文并装配参数。工具不读取人物卡、EP目录或业务采用表。

按[文生图](references/ComfyUI-文生图执行规范.md)或[图生图](references/ComfyUI-图生图执行规范.md)读取当前模式。共用可填正文见[文生图模板](references/模板/Qwen-Image-2.1-文生图提示词模板.md)与[编辑模板](references/模板/Qwen-Image-2.1-图像编辑提示词模板.md)；业务视图、布局、图种及来源资格由调用方提供。

独立装配接口为scripts/qwen_image_workflow.py的assemble；命令和输入输出见[装配接口](references/Qwen工具调用规范.md)。只准备不上传、不生成。实际远端任务交[任务后台](../studio-workspace-browser/SKILL.md)和[ComfyUI通信](../studio-comfyui/SKILL.md)，结果交回业务登记。

工作流原画布保持原样；固定模型、节点和参数按当前规范，不自动替换。维护工具时核对受影响调用和装配测试，技术通过不代表生成效果或业务采用。
