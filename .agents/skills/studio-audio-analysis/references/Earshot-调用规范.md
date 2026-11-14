# Earshot-调用规范

按当前问题查对应工具。分析已给素材前核对实际文件、版本、区间和用途；需要调整或输出文件时，沿用调用方给定的剪辑范围和保存位置。

## 音频比较与判读

读[官方 Earshot 技能](../dependencies/earshot/SKILL.md)的 Loop 1、Loop 3 和 Reading the numbers。比较两条音效或两个版本用 `ab`，长录音应先限定各自真正要用的片段。对照一组已采用的参考音效用 `compare`，结合音色、起音、衰减和参考素材本身的差异。判断声音是否有明显合成感用 `realness`，以拟采用片段为准，结合声音类型与报告证据；音频来源及许可按素材页面核对。

查询描述可以写声源、材质、动作和听感。分数接近时用两三种贴合实际声音的措辞，返回匹配等级和 z 值；原始相似度和备选间的相对得分按官方口径解释。短事件用 `find --kind event`，连续环境声或背景质感可用 `--kind texture`。检查可剪片段的头尾提示，试听时按实际使用的音量和画面复核。

## 音轨与整片审阅

读[官方 Earshot 技能](../dependencies/earshot/SKILL.md)的 Loop 2 和[能力边界](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/LIMITS.md)。

| 要核对的问题 | 工具与读法 |
| --- | --- |
| 电平、峰值、动态、静音、频谱、起音，或稳态音乐的节拍和调性 | `measure`。根据问题取整轨或具体区间；稳态音乐的节拍和调性用 `--music` |
| 整条音轨或成片里有哪些声音事件、段落变化、节拍和音画对应 | `timeline`。要核对动作帧时传 `cues`；已有独立音轨可配同版画面 `--video`。密集混音结合偶然匹配基线和明显起音看结果 |
| 想查看波形、频谱、声音事件和画面标记的关系 | `sheet` 导出带时码的 PNG，可用 `--from` 和 `--to` 限定区间。查看其中的画面时遵循工作区图片查看范围 |
| 需要按同类参考成片检查响度、混音、声音密度和音画匹配 | `critique`，先确认所用参考范围。默认参考面向产品发布片。需与自己的参考片比较时，用 `profile` 建立参考配置，再传给 `critique --profile` |
| 修改前后哪里有变化 | `ab` 比较同一段，涉及同步时结合各版 `timeline` 和对应分轨；回报具体变化和需要试听的区间 |

[验证说明](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/VALIDATION.md)提供测试场景和数据适用范围。整片混音里的声音标签、音乐类型和氛围是线索；需要确认指定声音时，用分轨或放回画面试听。

## 音效制作与试听交付

| 当前需要 | 工具与官方指南 |
| --- | --- |
| 从内置音效库取一条音效，例如 UI 点击、转场呼啸或短撞击 | `sfx list` 选 ID，`sfx render` 输出 WAV，`sfx check` 检查音效。按需要读时长、峰值时刻、音高和起音。[音效库与参数](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/SFX.md) |
| 同一条片需要成套音效，或按配乐和画面时点安排音效 | `kit init/render/check/audition`。用套件的实测起音、峰值、结束和音量安排落点。需要音乐相对电平、错位或重复间距时，读[套件与混音说明](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/SFX.md)及[Cinetic 接入示例](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/INTEGRATION.md) |
| 按具体听感制作一种合成音效并出多个变体 | `forge`。从配方出发，以频谱、包络、尾音、跨种子表现和实际试听核对；相似度或 `realness` 分数只作为证据之一。[官方 Earshot Loop 4](../dependencies/earshot/SKILL.md) · [Forge v2](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/FORGE_V2.md) |
| 根据一条已有录音拟合可编辑的声音配方，做重渲染、变体或两种音色之间的过渡 | `fit`。按需用 `--takes` 或 `--morph`，比较配方输出与实际参考的差异；拟合素材沿用该录音的使用条件。[录音拟合](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/FIT.md) · [内置拟合素材来源](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/CREDITS_FIT.md) |
| 交付可播放的试听页、对比多个版本 | `gallery`。按需做相对路径或嵌入式输出；交付含参考音频的页面前核对相应素材的分享范围。[试听页说明](https://github.com/Leonxlnx/earshot/blob/v0.4.1/README.md#gallery) |

内置库会按配方渲染声音，也包含从录音拟合的配方。需要真实录音素材时走 `real-sound` 的查找与许可步骤。

## 真实录音的声音设计

从[官方 real-sound 技能](../dependencies/real-sound/SKILL.md)选实际步骤。单独找音效、验许可、排配乐或复核混音时可以直接进入对应一行。整片流程按本次要求及所属业务的交付规格执行。

| 任务 | 上游步骤与文件 |
| --- | --- |
| 标动作时点、明确声音需求和素材范围 | 0–1，Cue list 与 Brief。[画面标记模板](../dependencies/real-sound/templates/cues.json) · [声音需求模板](../dependencies/real-sound/templates/SOUND_BRIEF.md) |
| 找拟音、环境声、配乐，核对许可、登记来源与署名 | 2–3，Sourcing 与 Licence audit。[许可说明](../dependencies/real-sound/references/licences.md) · [素材登记模板](../dependencies/real-sound/templates/manifest_entry.json) |
| 按段落、节拍、小节剪配乐，或为具体镜头安排拟音、环境声和效果 | 4–5，`arrange.py` 草拟配乐结构，确认首拍后落小节与动作。按[声音设计规则](../dependencies/real-sound/references/sound-design.md)和[设计格式](../dependencies/real-sound/references/design-format.md)准备可用素材、裁剪、摆放和分轨 |
| 混音、分轨、质检及逐处修订 | 6–9，`mix.py` 渲染、`qa.py` 检查遮蔽、边缘、频谱、音量和同步；用 `variant.py` 试修并比较。按[制作与审阅流程](../dependencies/real-sound/references/process.md)的相应审查视角复核 |
| 母带、署名、换入成片音轨并回查 | 10，`master.py`、`credits.py` 和 `mux.mjs`；保留采用音轨、署名及最终文件，检查新成片的同步。按项目的交付目标设响度和峰值 |

执行上游脚本用能导入 Earshot 和其音频依赖的 Python，按官方说明使用 `-I`。合片脚本使用 Node.js 和 FFmpeg。产物位置按当前项目约定；命令、输入缺失和导出问题查[上游故障说明](../dependencies/real-sound/references/troubleshooting.md)。需要参考上游的发布片风格时，读[发布片声音指南](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/launch-video-sound.md)，将其参考范围对应到当前片型。

## 运行与能力边界

- `doctor` 查 FFmpeg、依赖、缓存和 CPU 设置，`doctor --load` 核对本机实际加载。分析前查看当前会话可用的 MCP 工具，已安装命令的参数以 `earshot <command> --help` 为准。[官方安装与 Python 接口](https://github.com/Leonxlnx/earshot/blob/v0.4.1/README.md#install)
- 上游 MCP 的 `sfx_list`、`sfx_render`、`kit_render` 分别对应命令行的 `sfx list`、`sfx render`、`kit render`。按当前会话可用的工具选择入口。
- `measure`、`sfx` 和 `kit` 可在无模型时运行。基于模型的结果按[能力边界](https://github.com/Leonxlnx/earshot/blob/v0.4.1/docs/LIMITS.md)判读，尤其是很短的音效、被盖住的声音、较慢的转场和自动识别的切点。
- 可选的 `llm` / `llm_critique` 是把音频发给 Google Gemini 做复核。只有用户明确同意上传指定音频，且运行环境已具备相应依赖和用户提供的 API Key 时，按[官方 Earshot 技能](../dependencies/earshot/SKILL.md)的 Optional 段调用。再用本地测量和试听核对其时码及判断。
