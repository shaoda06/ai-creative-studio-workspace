# ComfyUI-图片超分执行规范

调用方提供具体源图、明确处理目标、输出路径和实际授权。工具只执行技术处理，不规定业务图种、批准步骤或正式采用。

## 配套工作流与参数

本地[画布基准](../../nora-image-processing/references/workflows/RTX-图片2倍超分.workflow.json)和[API基准](../../nora-image-processing/references/workflows/RTX-图片2倍超分.api.json)配套维护。每次复制API任务副本，替换输入路径及按[远端输出目录](../../nora-generation/references/ComfyUI-服务配置与任务提交规范.md#远端输出目录与命名)填写输出前缀，不改写基准或远端保存的工作流。

| 节点 | 类名与输入 | 固定要求 |
| --- | --- | --- |
| 2 | `LoadImage.inputs.image` | 调用方指定源图的真实上传路径 |
| 1 | `RTXVideoSuperResolution.inputs.images` | `["2", 0]` |
| 1 | `resize_type` | `scale by multiplier` |
| 1 | `resize_type.scale` | `2`，动态参数完整键名不可改为`scale` |
| 1 | `quality` | `ULTRA` |
| 1 | 共用必填输入 | 按[RTX节点共用必填输入](#rtx节点共用必填输入)显式填写，不能省略远端标为必填的默认参数 |
| 3 | `SaveImage.inputs.images` | `["1", 0]` |
| 3 | `filename_prefix` | 本任务唯一可辨认的超分前缀 |

正式输出节点为3，PNG数量1。倍数模式核对输入的2倍宽高，指定尺寸模式核对调用方明确目标。画布中的ImageCompare只用于人工操作时对照，不属于API正式输出或自动看图环节。没有提示词、种子、CFG或采样步数，记录为不适用，不伪造扩散模型参数。

### RTX节点共用必填输入

图片超分和视频后处理使用 `RTXVideoSuperResolution` 时，任务API明确填写 `strength=1.0`、`image_encoding="8-bit RGB"`；画布的命名控件与位置控件同步保存这两个值。前者为处理强度，后者为SDK像素编码；它们不能因远端提供默认值而从API省略。尺寸、缩放方式、质量和帧率仍按各自图片／视频执行规范填写。

现行图片与视频工作流的配对基准均保存这些字段。固定 `--prepare-only` 入口和离线API检查工具检查已知必填输入及取值；缺字段时在本地停止，不上传、不生成，也不由工具自动补值。准备报告复用与节点接口差异的处理见[服务配置与任务提交规范](../../nora-generation/references/ComfyUI-服务配置与任务提交规范.md#远端能力与错误返回)。已生成任务的原请求、参数和批准记录保留，不因维护基准而改写。


运行、尺寸分流与输入输出见[处理工具规范](图片处理工具规范.md)。业务记录和正式采用交回调用方。
