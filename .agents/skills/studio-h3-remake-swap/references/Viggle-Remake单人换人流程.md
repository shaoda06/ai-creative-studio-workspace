# Viggle Remake 单人换人流程

用于把已有视频中的一名表演者换成目标角色，按原片保留动作、镜头、背景和声音。每次 Remake 请求处理一个片段，多个片段由调用方负责切分、提交和合片。

基准、分段及合片见[Swap 共用流程](Viggle-Remake换人分段与合片.md)。

## 1. 确定换人目标和参考图

- 从原片及用户说明确定要换的表演者。同框有其他人时，在提示词写清原片里可辨认的目标，以及其他人物的保留要求。
- 调用业务提供同一角色的两张参考图及各自分工。按本次换人最需要匹配的属性排参考图。单人露脸换人默认把面部身份放在首位，两张图共同定义一个 `<Subject 1>`。
  - 面部三视图排第一，接 `ref_1`，正文使用 `<Picture 1>`。
  - 全身三视图排第二，接 `ref_2`，正文使用 `<Picture 2>`。
- 用户或业务明确指定其他顺序时，按指定顺序接线并同步正文标签。此顺序是默认编排约定，效果以实际样片为准。双三视图作普通参考时 `pins` 留空。
- 按[原声是否参与生成](../../studio-h3-remake/SKILL.md#原声是否参与生成)确认本轮选择。

### 提示词编写与核对

- 按 [Viggle 共用提示词规范](../../studio-h3-remake/references/Viggle-Remake提示词规范.md)读取两份指南，结合原片和调用方要求描述换人后的主体外观、服装、配饰以及要保留的动作、背景、运镜与声音。正文要求对应本次参考、原片或已明确的业务依据。
- 使用面部三视图和全身遮面图且要求露脸时，面部图是唯一的面部身份参考，提供可见五官、妆容及经确认的头部造型。全身图提供经确认的体型、头身比例、服装、鞋履和穿搭配饰，也可按业务分工补充发尾与穿搭的关系。遮面处理留在素材说明，模型正文描述各景别和角度下实际可见的脸。

## 2. 逐段装配和提交

装配前按[生成分辨率询问](../../studio-h3-remake/SKILL.md#生成分辨率询问)确认本轮尺寸。

从 API 模板为每段准备任务副本。用服务器实际上传名填文件字段，原始素材及其版本按调用业务记录。

| 节点 | API 输入字段 | 填写内容 |
| --- | --- | --- |
| `#62` | `file` | 当前段的 24 fps 源片 |
| `#9`、`#64` | `image` | 按实际顺序绑定 `<Picture 1>`、`<Picture 2>` |
| `#34` | `value` | 当前段的完整六段英文提示词 |
| `#66` | `value` | 按[源片准备规则](Viggle-Remake换人分段与合片.md#规范源片和确定分段)填写本段时长 |
| `#54` | `value` | 视频画布及普通参考图的短边设定 |
| `#72` | `switch` | 本轮确认的选项，`true` 为「参考」，`false` 为「不参考」 |
| `#12` | `seed` | 本段实际使用的种子，API 模板给出固定数值 |
| `#65` | `filename_prefix` | 本段的输出前缀，按实际段号区分 |

装配后按[Swap 共用流程](Viggle-Remake换人分段与合片.md#提交取回和合片)提交、取回和审阅。

从工作区根目录运行以下命令。需要 Python 3.10+、FFmpeg 和 ffprobe。相对本地路径以当前目录为准。Swap 是 `prepare` 的默认模式。以下示例有一个原片切点，演示第 2 段的装配。

```sh
tool=".agents/skills/studio-h3-remake/scripts/long_swap.py"
python3 "$tool" prepare source_24fps.mp4 run --cut 240
python3 "$tool" graph run 2 --source remote/segment-002.mp4 \
  --face remote/face.png --full-body remote/body.png --prompt prompt.txt \
  --audio-conditioning silent --short-edge 736 \
  --output-prefix viggle_remake/long_swap --output run/segment-002.api.json
python3 "$tool" join source_24fps.mp4 run raw_results final.mp4
```

- `prepare` 写出 `run/segments.json` 和 `run/sources/segment-NNN.mp4`。使用新的工作目录，段号从 1 开始。
- `graph` 读取 UTF-8 正文，以计划的生成帧数直接填 `#42.frames`。面部图默认第一。全身图需排第一时加 `--reference-order full-body-first`，并同步调整正文的 Picture 编号。续接段加 `--previous` 和上一段原始输出上传后返回的服务器输入名，工具装配 `RemakePrefix`。
- 按[已确认的原声选择](../../studio-h3-remake/SKILL.md#原声是否参与生成)传 `--audio-conditioning`。命令行省略时沿用模板的 `source`。
- `--short-edge` 按[生成分辨率](../../studio-h3-remake/SKILL.md#生成分辨率询问)填写本轮短边像素，省略沿用模板 480。`--seed` 可填 0 到 2⁶⁴−1 的整数，省略沿用模板种子。`--output-prefix` 是服务器输出前缀，工具在后面添加 `/segment-NNN`。`--output` 是本地 API 文件路径。
- 三个命令均只操作本地文件，成功时写出指定产物，输入或帧数不合要求时退出报错。API JSON 和合片路径须使用尚未存在的文件名。
