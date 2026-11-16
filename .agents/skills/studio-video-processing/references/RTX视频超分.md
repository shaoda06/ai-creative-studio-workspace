# RTX 视频超分

使用 [独立画布](workflows/RTX-视频超分.workflow.json) 或 [默认 API](workflows/RTX-视频超分.api.json)。输入实际源视频，按已选交付规格填写目标尺寸。原有的[分步询问、尺寸与画幅适配](视频技术处理规范.md#后处理分步询问)继续适用。

`RTXVideoSuperResolution` 使用 `target dimensions` 和 `quality=ULTRA`，沿用 [RTX 共用必填参数](../../studio-image-processing/references/ComfyUI-图片超分执行规范.md#rtx节点共用必填输入)。单独使用时沿用源帧率。需要插帧时按[共用装配](视频技术处理规范.md#实际装配)把 RTX 接在 RIFE 之后。输出技术核对也按共用装配执行。
