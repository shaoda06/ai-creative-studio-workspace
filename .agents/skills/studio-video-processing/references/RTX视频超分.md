# RTX 视频超分

使用 [独立画布](workflows/RTX-视频超分.workflow.json) 或 [默认 API](workflows/RTX-视频超分.api.json)。输入实际源视频，按已选交付规格填写目标尺寸。

## 参数确认

问题用「目标分辨率是多少？」按源尺寸及交付目标给出适用的推荐尺寸和自定义宽高。横屏 1920×1080、竖屏 1080×1920 可在满足本次目标时作为选项。目标宽高使用正偶数。

目标比例和原片不同时，在同一问题链提供「保留完整画面」和「裁切到目标画幅」。通过[共用尺寸计算](视频技术处理规范.md#画面尺寸与适配)展示实际输出尺寸及各边裁切量。目标比例一致时沿用完整画面。

`RTXVideoSuperResolution` 使用 `target dimensions` 和 `quality=ULTRA`，沿用 [RTX 共用必填参数](../../studio-image-processing/references/ComfyUI-图片超分执行规范.md#rtx节点共用必填输入)。单独使用时沿用源帧率。装配及结果核对见[共用装配](视频技术处理规范.md#实际装配)。
