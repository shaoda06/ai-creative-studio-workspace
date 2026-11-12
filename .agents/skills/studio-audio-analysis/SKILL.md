---
name: studio-audio-analysis
description: 从素材网站查找拟音、环境声、短音效和配乐并核对许可。用 Earshot 筛选、定位和对比已有音频，检查音画同步、响度与混音，或渲染、合成和拟合音效。真实录音的整片声音设计走 real-sound。
---

# Studio 音频分析

## 按任务读取官方技能

| 当前任务 | 读取入口 |
| --- | --- |
| 缺少一条音效、环境声或配乐，要找素材、试听或核对许可 | [从素材网站找音效](#从素材网站找音效)，走 `real-sound` 的素材与许可步骤 |
| 手上已有音频，要筛选、找可剪片段、比较两个版本或评估合成感 | [筛选或定位音效](#筛选或定位音效)和[音频比较与判读](references/Earshot-调用规范.md#音频比较与判读) |
| 核对指定动作的音效落点、音轨响度，或审阅成片混音 | [核对音效落点](#核对音效落点)和[音轨与整片审阅](references/Earshot-调用规范.md#音轨与整片审阅) |
| 要渲染内置音效或套件、自定义合成、用录音拟合音效或交试听页 | [音效制作与试听交付](references/Earshot-调用规范.md#音效制作与试听交付) |
| 用真实录音做整片声音，或只做画面标记、配乐剪辑、混音、质检、母带、署名和合片中的某一步 | [真实录音的声音设计](references/Earshot-调用规范.md#真实录音的声音设计)，按任务进入 `real-sound` 对应步骤 |

## 从素材网站找音效

一条音效也可以单独查找。读[官方 real-sound 技能](dependencies/real-sound/SKILL.md)第 2 步 Sourcing 和[许可说明](dependencies/real-sound/references/licences.md)。按实际声音搜索，例如「皮鞋踩木地板，单步，无背景声」。在 Freesound 找具体拟音或环境录音，在 Mixkit 找短撞击、破风或界面提示音。找配乐时也可查作曲家的曲库。核对素材原页面或站点列出该素材的页面、对应许可和署名要求，按任务交回试听链接或素材文件，并附上名称、来源和许可。需要筛选已取得的候选时，再用下方的本地筛选方法。

## 核对音效落点

核对本地文件的准确版本、目标声音和片段时码。有对白或音乐的成片优先用对应音效分轨核对起音，再回到混音版判断该处是否听得清。分轨与画面需要对齐到同一时间原点。

- 用 `timeline`，把动作接触、界面弹出等目标时刻作为 `cues` 传入。时刻可以用秒数数组或画面标记 JSON。明确区分剪辑者给出的动作帧和 Earshot 自动识别的画面切点。只查响度、峰值或静音时，用 `measure`。
- 查时间先用 `detail=low`。逐点读 `sync.cues.items` 的 `event_t`、`offset_ms` 和 `status`。偏差是声音起点减画面时刻，负数为早、正数为晚。返回文件版本、画面时刻、检测到的起音、偏差毫秒和判断依据。
- `OK` 和 `near` 表示标记附近有起音。混音里匹配的起音可能来自对白、音乐或另一条音效，声音标签也只是候选判断。目标声音归属不明时，报告检测到的事件和待试听时码，拿到分轨后再确认偏差。渐强或呼啸要根据设计核对峰值或经过画面动作的时刻，`peak`、`swell` 或 `no sound` 均需结合分轨或试听判断。

## 筛选或定位音效

- 用 `rank` 给多条候选排序，描述实际声音，例如「一次短促低沉的木块敲击」。用 `find` 在长录音中找匹配片段，点击、敲击、脚步选 `kind=event`。`find` 的起点包含起音前的裁剪余量，核对同步时读 `timeline` 的起音字段。用 `describe` 描述单条样本，或用 `match` 检查特定描述。返回文件、匹配等级或 z 值、适用区间和可能截断的头尾。
- 把匹配结果交回调用方试听和选择。需要按确认的区间输出文件时，用[音频处理](../studio-audio-processing/SKILL.md)。需要读对白内容时用[视频读取](../studio-video-study/SKILL.md)的转写路径。

## 调用与更新

分析本地文件时，优先用本项目已提供的 `earshot` MCP 工具，文件参数用绝对路径，需要逐点数据时传 `full=true`。当前会话没有 MCP 工具或工具列表缺少所需操作时，使用同一安装的命令行；批量分析也可在一个 Python 进程里用 `earshot.api`。例如：

```bash
earshot timeline "/path/to/film.mp4" --cues "2,4,6,8" --detail low --json
```

安装使用 `uv tool install 'earshot[mcp] @ git+https://github.com/Leonxlnx/earshot'`，更新使用 `uv tool upgrade earshot`。首次取模型或更新后缺少模型时，用 `earshot doctor --fetch` 准备缓存，再用 `EARSHOT_OFFLINE=1 earshot doctor --load` 核对实际加载。公开模型下载如遇本机缓存凭据过期，可以仅对取模型命令设置 `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`，按匿名方式下载。

MCP 使用本地标准输入输出，入口为 `earshot mcp`。配置工作区的 `.codex/config.toml` 时，`command` 指向 `uv tool dir --bin` 下的实际 Earshot 可执行文件，进程须能找到 FFmpeg 和 FFprobe。模型缓存就绪后用 `EARSHOT_OFFLINE=1` 运行。

模型与测量边界、调用诊断及可选云端复核见[运行与能力边界](references/Earshot-调用规范.md#运行与能力边界)。
