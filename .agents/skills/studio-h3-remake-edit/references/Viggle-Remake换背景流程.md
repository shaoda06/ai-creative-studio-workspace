# Viggle-Remake 换背景流程

使用 Edit 修改源视频的场景，并按任务要求保留表演者、构图、运镜、时间线和声音。源片可以是原始视频，也可以是前一轮已选定的换人结果。

- 使用已登记的 [Edit 画布](../../studio-h3-remake/references/workflows/Viggle-Remake-换背景-目标参考帧.workflow.json)和 [Edit API](../../studio-h3-remake/references/workflows/Viggle-Remake-换背景-目标参考帧.api.json)。基准使用 Edit INT8、Euler 六步、24 fps、短边 480，采样器 `#16` 的 Sigma 来自 `#33`。[Viggle 官方 ComfyUI 说明](https://huggingface.co/Viggle/Viggle-Remake/blob/main/COMFYUI.md)

## 1. 核对源动作和目标场景

- 按镜头对照源片与目标场景的机位高度、俯仰角、地面透视、人物在画面中的大小和可活动范围。人物走动时，检查进出画方向、行走通道、远近变化和落脚位置能否落在目标空间里。存在桌椅、台阶或墙面时，核对遮挡、接触和通行关系。
- 场景素材有合适内容但拍摄角度不同，可以以源片构图为基准制作该场景的目标视角。原动作与场景动线冲突时，先按调用方要求决定使用更匹配的背景构图，或使用适合该场景的源镜头。当前素材的兼容性以有代表性的连续动作样片核实。
- 按[原声是否参与生成](../../studio-h3-remake/SKILL.md#原声是否参与生成)确认本轮选择。

## 2. 准备参考帧和提示词

1. 将当前源片转换为恒定 24 fps，沿原片切点独立分段，并记录实际保留区间。单段按 `17N+5` 向上对齐，生成窗口为 90–345 帧。连续镜头超过 345 帧时，按动作阶段与机位选切点，为相邻段准备空间关系一致的目标参考帧，并检查接缝。段尾复制最后一帧补齐，合片裁回正文。
2. 从本轮源片选构图和动作有代表性的一帧，以该帧为基准制作新背景下的目标画面。保留人物站位、姿势、大小和原镜头画幅。需要核对落脚时，选鞋底和地面都入画的帧，表达实际承重脚、抬起脚、鞋底接触阴影和投影方向。镜头变化较大时，按必要的机位或动作变化补参考，并核对各参考中的空间关系。
3. 第一张目标帧接 `#42.ref_1`，正文使用 `<Picture 1>`。按[共用绑定规则](../../studio-h3-remake/references/Viggle-Remake提示词规范.md#目标帧绑定)设置外观参考或绑定到具体时点。Edit 各段独立生成，预卷为 0，绑定值就是段内正文帧号。确需多张参考时，在画布或任务 API 副本中手动接入后续参考口。按 [Viggle 共用提示词规范](../../studio-h3-remake/references/Viggle-Remake提示词规范.md)描述新场景、光线与接地关系，并写明本轮要保留的人物、动作和镜头。

## 3. 装配 Edit 请求

装配前按[生成分辨率询问](../../studio-h3-remake/SKILL.md#生成分辨率询问)确认本轮尺寸。

手动画布或直接填写 API 副本时，`#66` 填本段计划保留帧数除以 24 得到的秒数。短于 90 帧时填 3.75 秒。`#67` 向上对齐生成帧数，最多 345 帧。保留区间以实际帧数为准。

| 节点 | 填写内容或基准配置 |
| --- | --- |
| `#1.unet_name`、`#3` | Edit INT8 权重 `viggle_remake_edit_pruned_int8_convrot.safetensors`，直连 `#3`，`keyframe_until=0.9` |
| `#33.sigmas` | Edit 的 `1.0, 0.983607, 0.96, 0.923077, 0.857143, 0.705882, 0.0` |
| `#62.file`、`#9.image`、`#34.value` | 分别填本段 24 fps 源视频、目标参考帧的实际上传名和六段英文提示词 |
| `#42` | 按目标参考帧填 `pins`。源片画面来自 `#63` |
| `#72.switch` | 本轮确认的选项，`true` 为「参考」，`false` 为「不参考」 |
| `#54.value`、`#12.seed`、`#65.filename_prefix` | 本次短边、种子及逐段输出前缀 |

### 分段和 API 命令

从工作区根目录运行[分段工具](../../studio-h3-remake/scripts/long_swap.py)。需要 Python 3.10+、FFmpeg 和 ffprobe。相对本地路径以当前目录为准。以下示例的第 1 段在第 144 帧前结束，参考图绑定在该段第 23 帧。

```sh
tool=".agents/skills/studio-h3-remake/scripts/long_swap.py"
python3 "$tool" prepare source_24fps.mp4 run --mode edit --cut 144
python3 "$tool" edit-graph run 1 --source remote/segment-001.mp4 \
  --reference remote/target_background_frame.png --pin 23 --prompt prompt.txt \
  --audio-conditioning silent --short-edge 736 \
  --output-prefix viggle_remake/background_edit --output run/segment-001.api.json
python3 "$tool" join source_24fps.mp4 run raw_results final.mp4
```

- `prepare --mode edit` 按 `--cut` 的 24 fps 原片帧号独立分段，切点可重复传入。单段正文超过 345 帧时补充切点后重试。使用新的工作目录，输出 `run/segments.json` 和 `run/sources/segment-NNN.mp4`。计划中的 `start`、`end` 是原片左闭右开的正文帧区间，`generation` 是生成帧数，Edit 的 `head` 为 0。
- `edit-graph` 每段绑定一张目标参考帧，读取 UTF-8 正文，以计划帧数填写 `#42.frames`。段号从 1 开始。`--source` 和 `--reference` 使用实际服务器输入名。省略 `--pin` 时作为普通参考，`--pin 0` 绑定段内第一帧。
- 按[已确认的原声选择](../../studio-h3-remake/SKILL.md#原声是否参与生成)传 `--audio-conditioning`。命令行省略时沿用模板的 `source`。
- `--short-edge` 按[生成分辨率](../../studio-h3-remake/SKILL.md#生成分辨率询问)填写本轮短边像素，省略沿用模板 480。`--seed` 可填 0 到 2⁶⁴−1 的整数，省略沿用模板种子。`--output-prefix` 是服务器输出前缀，工具在后面添加 `/segment-NNN`。`--output` 是本地 API 文件路径。
- 经生成授权后，用[共用 ComfyUI 提交入口](../../studio-comfyui/references/ComfyUI工具调用规范.md)逐段提交并取回 `#65`，按段号保存为 `raw_results/segment-NNN.mp4`。核对各段实际生成帧数。`join` 裁回正文，按原顺序合片并封回本轮规范源片音轨。
- 三个命令均只操作本地文件，成功时写出指定产物，输入或帧数不合要求时退出报错。API JSON 和合片路径须使用尚未存在的文件名。

## 4. 样片核对与返修

- 有查看授权时，检查参考帧及其前后的连续动作。重点看落脚、承重、抬脚和站定时鞋底与地板的关系，人物尺度和遮挡是否随镜头连贯，脸、穿搭、场景和原切点是否符合任务要求。
- 出现漂浮感、透视不合或动作与场景脱节时，选同一镜头做对照。保持源视频、种子和采样设置一致。先在原参考帧下补足遗漏的提示词，再用相同的动作和场景描述换成更合适的参考帧，并同步其帧位和正文时码。若参考帧附近改善、连续动作仍脱节，重点检查机位、地面透视与行走路线，优先试匹配原动作的场景视角。
- 工作流测试按 Edit 实际输出审阅，技术合片只裁去补帧、按顺序拼接并封回原声。保存实际参考、提示词、请求、模型输出和对照结论。单镜头结果用于判断该素材条件，扩到全片时按不同构图和动作复核。
