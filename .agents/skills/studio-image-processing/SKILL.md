---
name: studio-image-processing
description: 在已有源图，需要保留原图、本地等比适配、遮罩填充或 RTX 放大时使用。按目标规格处理，并核对 PNG 与执行凭据。
---

# Studio 图片处理

媒体原件、上传参考音视频及修改版本统一按[项目资源与版本](../studio-workspace-browser/references/项目资源与版本管理.md)保存。调用业务维护原记录及采用，输入、审核、采用及导出引用准确版本。

调用方提供具体源图、处理授权、目标宽高和输出路径。按[输入与分流](references/图片处理工具规范.md#输入与分流)确定直接保存、本地处理或RTX装配，方式未明确时由用户选择。需要改变构图的裁切必须处于实际授权范围，不按图种猜尺寸。

scripts/image_processing.py提供resize和assemble_rtx；scripts/image_files.py提供PNG和远端实际输入/输出凭据核对。固定配置及节点要求见[RTX执行规范](references/ComfyUI-图片超分执行规范.md)。Agent决定实际任务与内容取舍，脚本执行明确处理，不做画面质量判断。

明确要求本地遮罩填充时，按[本地遮罩填充](references/图片处理工具规范.md#本地遮罩填充)使用Pillow处理与核对像素；业务调用方提供范围，工具不推断遮蔽部位。

本地处理不入远端队列；RTX任务交[任务后台](../studio-workspace-browser/SKILL.md)。保留原图，返回真实规格、处理方式和凭据。正式保存、归档及采用关系交业务阶段；无需业务记录的技术任务使用明确的technical结果适配，不创建人物卡或EP目录。
