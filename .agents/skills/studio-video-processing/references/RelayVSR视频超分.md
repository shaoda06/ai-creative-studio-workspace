# RelayVSR 视频超分

使用 [独立画布](workflows/RelayVSR-视频2倍超分.workflow.json) 或 [默认 API](workflows/RelayVSR-视频2倍超分.api.json)。模型与 Flash VAE 使用基准中的配对。104 节点 `detail` 固定为 0.5。

## 参数确认

倍率只显示「2 倍放大」，随方案展示实际输出宽高，按原片宽高分别乘 2。只选 RelayVSR 时沿用源帧率，与补帧组合时按 [RIFE 参数确认](RIFE视频插帧.md#参数确认)补齐目标帧率。

## 分段装配与拼接

恒定帧率源视频按每段 10 秒的帧数上限在本地截取。分数帧率向下取整到完整帧，最后一段保留实际剩余帧。截取复制视频编码数据，保存解码所需的参考帧，并按 MP4 播放区间核对可读帧数和时长。原音轨留待整条拼接时封回。

在总工作区使用 Python 3、FFmpeg 和 ffprobe。以下示例的源片、执行目录和输出文件都是项目相对路径。本地准备和拼接只读写指定项目，不连接生成服务。

```sh
python .agents/skills/studio-video-processing/scripts/relayvsr_batch.py prepare --project "/实际项目" --source "源片.mp4" --record-dir "执行记录/本次RelayVSR" --output "执行记录/本次RelayVSR/候选.mp4" --authorization "本次用户授权"
```

`prepare` 返回 `status=prepared` 和分段数量，写出各段输入、画布、任务清单和分段计划。指定 `--fps 60` 等与源片不同的目标帧率时，同步写出下一阶段的插帧清单，中间合片使用执行目录内的 `超分合片.mp4`。最终文件使用独立的 MP4 路径。省略目标帧率时沿用源帧率。仅执行超分时，单段与多段均使用同一套清单和拼接入口。

用[共用任务入口](../../studio-comfyui/references/ComfyUI工具调用规范.md#提交与准备)先准备，再把 `执行记录/本次RelayVSR/任务清单.json` 提交为一个组。同一节点按既有队列调度逐段执行。保留任务组各自的取回凭据。组内异常按原任务身份恢复，齐备后继续。

收到完整组的后台通知后，在来源会话使用原执行目录拼接。脚本读取每段的结果收尾报告，核对与实际取回文件一致，按源片顺序合并画面并封回源片音轨。成功返回 `status=joined` 与实际路径。已经拼接并完成规格核对时，从原合片继续交付或插帧。

```sh
python .agents/skills/studio-video-processing/scripts/relayvsr_batch.py join --project "/实际项目" --record-dir "执行记录/本次RelayVSR"
```

需要 RIFE 时，合片成功后按[整条插帧的实际资源](RIFE视频插帧.md)核对条件，再按原授权准备并提交 `插帧任务清单.json`。由调用方核对合片的分段接点，完成技术核对后按业务约定交回。

回归使用 `python -B -m unittest discover -s .agents/skills/studio-video-processing/scripts -p test_relayvsr_batch.py -v`。测试在临时目录验证分段、任务装配、取回合片和原声，不调用生成服务。
