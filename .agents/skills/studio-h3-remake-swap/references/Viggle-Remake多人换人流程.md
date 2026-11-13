# Viggle Remake 多人换人流程

同一段源片需要替换多位表演者时，使用 Swap 模型和 Swap 采样设置。按 [Viggle 官方目标帧指南](https://huggingface.co/Viggle/Viggle-Remake/blob/main/PROMPTING.md#painted-frames-and-pins)在源片帧上制作换人后的画面，再绑回对应帧号。可对照[官方双人换人提示词](https://huggingface.co/Viggle/Viggle-Remake/blob/main/examples/prompts/swap-card-royals.txt)核对主体定义和目标帧写法。

## 选段与人物对应

- 根据任务目标选原片区间。做短样时，优先看每位目标人物在这段里是否有足够清楚、便于对照的露脸画面，兼顾光线、脸部大小、运动模糊、遮挡和画面边缘。镜头可先后拍清各人，同一帧不必拍全。预先定位谁在什么时点出入画、转头或被挡住。
- 从原片给每位表演者确定稳定识别依据，如衣着、配饰、发型和动作。左右位置只用于描述指定时点。逐一核对原片表演者、目标身份和实际参考版本，明确要换的面部、发型或穿搭，以及保留的动作、构图、配饰、背景和声音。
- 参考身份使用业务已确认且足以辨认的原照或造型图。三视图、四视图可按需用于制作目标帧。照片和多视图拼图作为制图素材，绑定到视频时间轴的是编辑后的原片帧。

## 制作与绑定目标帧

1. 按[Swap 共用流程](Viggle-Remake换人分段与合片.md#规范源片和确定分段)规范源片并确定分段，再从规范源片取帧。优先用一张能覆盖目标人物和主要角度的画面。因出入画或转头无法覆盖时，再补对应时点，让共同出现的人在不同目标帧里保持同一身份。目标帧按源帧构图编辑，仅替换用户指定的属性，保留站位、视线、遮挡、光线及画面内原有物件；只处理该时点实际可见的人。送入模型前核对脸与身份、画面比例及准确源帧号。
2. 每段使用 1–4 张目标帧，按[共用绑定规则](../../studio-h3-remake/references/Viggle-Remake提示词规范.md#目标帧绑定)对齐端口、帧号及正文。例如规范源片第 132 帧，窗口正文从第 112 帧开始且有 17 帧预卷，则 `pins` 对应 37，提示词内的窗口时码为 00:01.542。
3. 按[共用六段提示词规范](../../studio-h3-remake/references/Viggle-Remake提示词规范.md)编写正文。每位目标人物单独定义一个 `<Subject N>`，写清源片表演者、目标外观及对应的画面；同一人物跨多个 `<Picture N>` 沿用同一主体编号。逐镜写实际入画、转头和动作，说明哪些属性替换、哪些由原片保留。

## 装配、取回与审阅

使用[既有 Swap 画布和 API 基准](Viggle-Remake换人分段与合片.md)的模型与采样链。手动用画布时，`#62` 加载补帧后的源片，`#9`、`#64` 分别加载第一、第二张目标帧。需要第三、第四张时追加图像加载节点接入对应参考口，未用的参考口断开，并按接线顺序填写 `#42.pins`。程序装配用现有 `long_swap.py` 的 `swap-keyframes` 命令。按 Remake 共用规则设置[生成分辨率](../../studio-h3-remake/SKILL.md#生成分辨率询问)及[原声条件](../../studio-h3-remake/SKILL.md#原声是否参与生成)。

从工作区根目录运行，依赖 Python 3.10+、FFmpeg 和 ffprobe。以下为 24 fps 单段示例，两张目标图分别取自规范源片第 8、46 帧：

```sh
tool=".agents/skills/studio-h3-remake/scripts/long_swap.py"
python3 "$tool" prepare source_24fps.mp4 run
python3 "$tool" swap-keyframes run 1 --source remote/segment-001.mp4 \
  --keyframe 8 remote/target-008.png --keyframe 46 remote/target-046.png \
  --prompt prompt.txt --short-edge 544 --audio-conditioning source \
  --output-prefix viggle_remake/multi_swap --output run/segment-001.api.json
python3 "$tool" join source_24fps.mp4 run raw_results final.mp4
```

- `--keyframe` 每次传一组「24 fps 规范源片的 0 起算正文帧号、该图实际上传名」，按 Picture 顺序提供。脚本读取分段计划，换算到生成窗口并写入 `pins`。续接段用 `--previous` 传上段原始结果的上传名，保持同一人物身份和生成尺寸，各段目标帧按其实际画面准备。
- 路径相对当前命令目录，`--source`、`--keyframe` 的图名和 `--previous` 是服务器输入名。命令只在本地切片、写计划、装配 API 或合片，不联网。API 与成片输出用新路径，输入和绑定不符合计划时报错。
- 按[Swap 共用流程](Viggle-Remake换人分段与合片.md#提交取回和合片)提交、取回和审阅。
