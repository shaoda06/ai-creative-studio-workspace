---
name: nora-image-processing
description: 共用图片技术处理工具，按明确输入和尺寸执行原图保存、本地等比适配或RTX放大，并核对PNG和执行凭据；不管理业务批准和正式资产采用。
---

# 图片处理工具

调用方提供具体源图、处理授权、目标宽高和输出路径。按[处理规范](references/图片处理工具规范.md)选择直接保存、本地处理或RTX装配。需要改变构图的裁切必须处于实际授权范围，不按图种猜尺寸。

scripts/image_processing.py提供resize和assemble_rtx；scripts/image_files.py提供PNG和远端实际输入/输出凭据核对。固定配置及节点要求见[RTX执行规范](references/ComfyUI-图片超分执行规范.md)。Agent决定实际任务与内容取舍，脚本执行明确处理，不做画面质量判断。

本地处理不入远端队列；RTX任务交[任务后台](../nora-workspace-browser/SKILL.md)。保留原图，返回真实规格、处理方式和凭据。正式保存、归档及采用关系交业务阶段；无需业务记录的技术任务使用明确的technical结果适配，不创建人物卡或EP目录。
