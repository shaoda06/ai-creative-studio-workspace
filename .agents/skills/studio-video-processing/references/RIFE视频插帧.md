# RIFE 自动切镜保护插帧

使用 [独立画布](workflows/RIFE-自动切镜保护插帧.workflow.json) 或 [默认 API](workflows/RIFE-自动切镜保护插帧.api.json)。输入视频及其实际帧率，按目标帧率重采样，输出接本节点的实际帧率。目标帧率与源帧率一致时按[共用装配](视频技术处理规范.md#实际装配)直接沿用源画面。

`NoraRIFEInterpolationCutTest` 复用已安装的 `RIFEInterpolation` 和 `flownet.pkl`。节点包与安装验证见[节点与安装包](../../studio-entry/维护规范.md#comfyui节点与安装包)。默认 `scale=1.0`、`scene_cut_threshold=0.15`、`batch_size=1`、`use_fp16=true`。切镜检测依据 64×64 RGB 相邻帧差异。跨切点保持源帧，其余位置调用 RIFE。阈值 0 会关闭保护，须有明确选择。闪光、快速运动和相近构图可能影响检测。

RIFE 的装配按实际视频时间线处理。与 RTX 或 RelayVSR 组合时按[共用装配](视频技术处理规范.md#实际装配)确定顺序。接在 RelayVSR 后时，此画布会读取拼好后整条视频的帧序列。根据整条合片的实际宽高、帧数和目标帧率，核对该节点的运行资源。现有节点无法承载整条时，先保留已核对的超分合片，插帧按实际可用条件接续。
