# Viggle-Remake 提示词规范

Swap 和 Edit 在编写、修订或核对正文时共用以下写法。

1. **按 H3 六段格式。** 读取 [h3-prompt-writing](../../h3-prompt-writing/SKILL.md) 的 Full-Reference Mode 和 [Ref2VA 指南](../../h3-prompt-writing/references/ref-en.txt)，沿用其字段名、顺序、参考标签、保留关系和时码。正文用英文，台词、歌词及画面文字按任务要求保留原语。
2. **结合 Viggle 的编辑写法。** 读取 [Viggle 本地提示词指南](upstream/PROMPTING.md)，本地缺失时读取[官方原文](https://huggingface.co/Viggle/Viggle-Remake/raw/7e5be143702dd53b9154482de673b8519ed2d4d6/PROMPTING.md)。直接描述目标成片，`retention_analysis` 写清本轮修改项、参考图提供的属性和源片保留项。按实际素材和任务目标写细节。
3. **核对实际请求。** `<Video 1>` 对应当前轮送入的源片，`<Picture N>` 对应当前请求的参考图顺序。对照 `#34` 正文和 `#42` 的实际参考端口。时码按本次输入片段计算，核对预卷、切点、绑定帧和生成帧数。保持各段的身份、造型或场景定义一致，按镜头的实际构图与动作填写逐镜描述。

## 目标帧绑定

绑定的目标帧来自本段正文，按生成画幅制作。每张图依次对应 `#42.ref_1` 至 `ref_4`、正文 `<Picture N>` 和一个 `pins` 值。帧号按 24 fps 生成窗口从 0 起算，等于「规范源片帧号 − 本段正文起点 + 预卷帧数」。提示词的绑定时码也按该窗口计算。只作外观参考时留空 `pins`，启用绑定时每个已接入的参考口都须有对应帧号。
