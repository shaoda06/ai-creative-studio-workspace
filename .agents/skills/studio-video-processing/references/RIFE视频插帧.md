# RIFE 自动切镜保护插帧

使用 [独立画布](workflows/RIFE-自动切镜保护插帧.workflow.json) 或 [默认 API](workflows/RIFE-自动切镜保护插帧.api.json)。输入视频及其实际帧率，按目标帧率重采样，输出接本节点的实际帧率。装配及结果核对见[共用装配](视频技术处理规范.md#实际装配)。

## 参数确认

问题用「目标帧率是多少？」显示原片实际帧率，按本次目标列出适用的 30 fps、60 fps 或自定义帧率。补帧时只列高于原片帧率的值。自定义目标为 1～240 fps。单独使用 RIFE 时沿用源尺寸。

`NoraRIFEInterpolationCutTest` 复用已安装的 `RIFEInterpolation` 和 `flownet.pkl`。节点包与安装验证见[节点与安装包](../../studio-entry/维护规范.md#comfyui节点与安装包)。默认 `scale=1.0`、`scene_cut_threshold=0.15`、`batch_size=1`、`use_fp16=true`。切镜检测依据 64×64 RGB 相邻帧差异。跨切点保持源帧，其余位置调用 RIFE。阈值 0 会关闭保护，须有明确选择。闪光、快速运动和相近构图可能影响检测。

## 运行资源

此画布会一次读取本次输入的整条视频帧序列。按实际输入的宽高、帧数和目标帧率核对节点的运行资源。
