# Viggle-Remake 提示词规范

Swap 和 Edit 在编写、修订或核对正文时共用以下写法。

1. **按 H3 六段格式。** 读取 [h3-prompt-writing](../../h3-prompt-writing/SKILL.md) 的 Full-Reference Mode 和 [Ref2VA 指南](../../h3-prompt-writing/references/ref-en.txt)，沿用其字段名、顺序、参考标签、保留关系和时码。正文用英文，台词、歌词及画面文字按任务要求保留原语。
2. **结合 Viggle 的编辑写法。** 读取 [Viggle 本地提示词指南](upstream/PROMPTING.md)，本地缺失时读取[官方原文](https://huggingface.co/Viggle/Viggle-Remake/raw/7e5be143702dd53b9154482de673b8519ed2d4d6/PROMPTING.md)。直接描述目标成片，`retention_analysis` 写清本轮修改项、参考图提供的属性和源片保留项。按实际素材和任务目标写细节。
3. **核对实际请求。** `<Video 1>` 对应当前轮送入的源片，`<Picture N>` 对应当前请求的参考图顺序。对照 `#34` 正文和 `#42` 的实际参考端口。时码按本次输入片段计算，核对预卷、切点、绑定帧和生成帧数。保持各段的身份、造型或场景定义一致，按镜头的实际构图与动作填写逐镜描述。
