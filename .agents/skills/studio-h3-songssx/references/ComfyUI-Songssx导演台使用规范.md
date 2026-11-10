# ComfyUI-Songssx导演台使用规范

适用于 [SelfLift 备用画布](../../studio-h3/references/workflows/非正式工作流/MiniMax-H3-Songssx导演台-Selflift-标准版.workflow.json)及[离线 API 基准](../../studio-h3/references/workflows/非正式工作流/MiniMax-H3-Songssx导演台-Selflift-标准版.api.json)。参考[上游 Agent 指南](https://github.com/Songssx/ComfyUI-MiniMaxH3-TimelineDirector/blob/main/docs/AGENT_LONG_VIDEO_GUIDE_CN.md)及[低内存工作流](https://github.com/Songssx/ComfyUI-MiniMaxH3-TimelineDirector#2-all-in-one-low-memory-video-output)。桌面标准版的定制参数以实际 fork 分支 `material-planner-options` 与目标节点为准。API 基准根据原画布、节点定义和本机已有节点规格离线转换，目标服务的兼容性另行核对。

## 场次装配

一次提交一个场次。每个 P 对应一个 GEN。按[共用制作层级](../../studio-storyboard/references/分镜写作规范.md#制作对象场次与分段)提供分段身份、时长、提示词、准确素材版本和接续意图。不同机位的直接切镜使用零帧重叠。同机位连续时按分镜指定前段尾部、重叠帧与后段开头的声音和动作。固定帧数按目标插件对齐，后段提示词先交代接续部分，内容时码与实际采样窗口一起核对。

标准低内存采样器在一次任务中完成 SelfLift、原生段间接续和合并。插件负责移除重叠画面并接续音频。执行产物为 `SaveVideo` 的整场 MP4。保留每个 P 对应的 GEN、采样窗口、重叠帧及成片计划帧区间。SelfLift 技术参数中的一采倍率与高分辨率步数属于同一次场次生成。后处理、采用和正式资料归调用业务。局部返修待生成链路验证后按上游支持另定。

## 试点任务接口

通过[共用准备与入队入口](../../studio-comfyui/references/固定脚本接口规范.md#准备检查与提交复用)调用。清单的任务项使用 `task_type: "video-scene-generation"`，提供 `title`、`record_dir`、`output` 和 `songssx`。准备检查通过并具备本次执行授权后才入队。

- `songssx` 提供对齐 32 的 `width`、`height`，明确的 `reference_image_center_crop`、`lowres_scale`、`seed` 及 `remote_prefix`。
- `segments` 按播放顺序，每项提供 `p`、内容 `duration`（秒）、入段 `overlap_frames`、完整英文 `prompt` 与对应 `images` 文件路径数组。图片顺序与段内 Picture 标签一致。试点支持 Ref2VA 独立参考图及原生场内音画接续。
- `scripts/songssx_workflow.py` 装配任务画布、API、图片上传绑定、单一取回目标及帧区间。后台保存原准备结果和实际上传路径。返回后沿共用任务的成功状态和取回凭据做基础登记，出现媒体异常或时码疑问时按需检查。
