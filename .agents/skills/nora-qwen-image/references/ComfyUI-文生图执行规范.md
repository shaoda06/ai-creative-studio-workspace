# ComfyUI-文生图执行规范

状态：现行执行规范。\
版本：v1.48。更新日期：2026-10-20。

适用于无参考图的Qwen Image 2.1任务。调用方提供完整实际正文、明确宽高、种子和输出位置；Agent按模型规则完成语义转写，工具不选择业务图种、模板或采用。带参考图进入[图生图](ComfyUI-图生图执行规范.md)。

## 1. 输入与工作流文件

| 文件 | 用途 |
| --- | --- |
| [原始画布](workflows/Qwen2.1-文生图-普通版.workflow.json) | 用户提供文件的原样副本，仅保存在规定的workflow目录，不修改内容，不生成修改过的任务画布 |
| [API执行版](workflows/Qwen2.1-文生图-普通版.api.json) | Agent执行用基准；每个任务复制后填写本节允许的参数，实际副本保存到项目执行附件 |

API基准含占位正文及输出前缀，不可直接提交。画布保留原有文字、布局、节点及控件；API独立维护，不要求与画布逐项相等，不执行配对、一致性或差异比较。用户更新画布时，由用户与Agent共同调整执行API和调用说明。

### 共用模型组合

文生图与图生图共用主模型`qwen_image_2.1_int8_convrot.safetensors`、编码器`qwen3vl_8b_bf16.safetensors`、VAE `qwen_image_2.1_vae_bf16.safetensors`。用户未明确调整时保持。普通任务不查询远端节点／模型库存；执行条件由远端实际响应确定，异常按[服务规范](../../nora-generation/references/ComfyUI-服务配置与任务提交规范.md#远端能力与错误返回)处理。

## 2. 提示词与参数映射

API有效链包含10个节点。文本节点672接编码器522；主模型523经TE加速653接采样器515；空latent 514提供输出画布；520解码后由508保存PNG。旁路增强器、文字显示和LoRA不进入API；界面按钮与装饰标签不进入请求。尺寸选择器512和随机种子节点524不进入API，宽高及种子直接使用明确数值。此转换不回写原始画布。

| 参数 | API位置 | 允许操作 |
| --- | --- | --- |
| 最终正向正文 | `672.inputs.value` | 每任务填`rewritten_prompt`，不把整个JSON送入模型 |
| 宽、高 | `514.inputs.width`、`height` | 调用方明确宽高；均为32倍数 |
| 种子 | `515.inputs.seed` | 调用方提供有效非负整数，不使用-1随机标记 |
| 输出前缀 | `508.inputs.filename_prefix` | 每任务按[远端输出目录](../../nora-generation/references/ComfyUI-服务配置与任务提交规范.md#远端输出目录与命名)填写，不加扩展名 |
| 反向提示词 | `522.inputs.negative_prompt` | 默认空；本次已明确需要时通过`parameters.negative_prompt`填写并记录 |
| 图片数量 | `514.inputs.batch_size` | 固定1；多候选使用独立任务，仍按种子规则执行 |
| 参考预处理 | `522.inputs.resolution` | 保留0；本工作流没有参考图输入 |
| 采样 | `515.inputs` | 固定`steps=40`、`cfg=1`、`sampler_name=euler`、`scheduler=simple`、`denoise=1` |
| TE加速 | `653.inputs` | 固定`attention=kitchen_int8`、`step_cache=te_predictor`、`reuse_threshold=0.06`、`start_percent=0`、`end_percent=0`、`predictor_error_limit=0.08`、`verbose=true` |
| 输出 | 节点508，`images`第0项 | 1张PNG；按真实返回的filename/subfolder/type取回 |

模型组合、连接、节点类型、采样和加速参数均为固定执行配置，日常任务不自行修改。需要改变时先取得具体配置变更授权，再维护API与说明；不借`parameters`覆盖固定值，不自动启用提示词增强器或4步LoRA。CFG为1时反向条件不发挥常规引导作用。

## 3. 分辨率设置

`wh_ratio`使用明确宽高的最简整数比；它是任务元数据，不直接添加到节点输入。画布原文件中的16:9和2.2 megapixels不决定API任务尺寸。

调用方确定本次目标。工具核对宽高为32倍数及比例一致，返回实际输出规格，不推导人物或场景尺寸。

## 4. 执行流程

使用[共用装配接口](Qwen工具调用规范.md)。装配只填写已备内容和明确参数，不重新优化提示词。远端提交、取回与恢复进入[任务后台](../../nora-workspace-browser/SKILL.md)。

## 5. 检查与验收

工具检查实际参数、输入绑定、PNG及请求/取回证据。技术结果交回调用方，由业务登记及用户采用。普通任务不比较原始画布与API；参数维护使用受影响的装配与API检查，不以离线结果声称远端执行成功。

## 本地配套基准

本工具references/workflows保存原画布和执行API，原画布不改写。连接及恢复按[共用通信](../../nora-comfyui/SKILL.md)，具体模式见[图生图](ComfyUI-图生图执行规范.md)。
