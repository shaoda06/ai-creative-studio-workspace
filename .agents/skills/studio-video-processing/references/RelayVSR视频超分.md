# RelayVSR 视频超分

使用 [独立画布](workflows/RelayVSR-视频2倍超分.workflow.json) 或 [默认 API](workflows/RelayVSR-视频2倍超分.api.json)。模型与 Flash VAE 使用基准中的配对。104 节点 `detail` 固定为 0.5。

## 参数确认

倍率只显示「2 倍放大」，随方案展示实际输出宽高，按原片宽高分别乘 2。RelayVSR 放大阶段沿用源帧率。

## 分段装配与拼接

恒定帧率源视频按每段 10 秒的帧数上限在本地截取。分数帧率向下取整到完整帧，最后一段保留实际剩余帧。截取复制视频编码数据，保存解码所需的参考帧，并按 MP4 播放区间核对可读帧数和时长。原音轨留待整条拼接时封回。

在总工作区使用 Python 3、FFmpeg 和 ffprobe。以下示例的源片、执行目录和输出文件都是项目相对路径。本地准备和拼接只读写指定项目，不连接生成服务。

```sh
python .agents/skills/studio-video-processing/scripts/relayvsr_batch.py prepare --project "/实际项目" --source "源片.mp4" --record-dir "执行记录/本次RelayVSR" --output "执行记录/本次RelayVSR/候选.mp4" --authorization "本次用户授权"
```

`prepare` 返回 `status=prepared`、当前 `stage` 和可提交的 `plan`。只做超分时写出各段输入、画布、任务清单和分段计划。指定 `--fps 30` 等与源片不同的目标帧率时，按[共用装配顺序](视频技术处理规范.md#实际装配)准备首阶段，返回 `stage=rife` 和 `插帧任务清单.json`。

用[共用任务入口](../../studio-comfyui/references/ComfyUI工具调用规范.md#提交与准备)准备并提交返回的 `plan`。插帧组取回完成后，在原执行目录按报告准备下一组。使用返回的 `stage=relayvsr` 清单提交超分。

```sh
python .agents/skills/studio-video-processing/scripts/relayvsr_batch.py after-rife --project "/实际项目" --record-dir "执行记录/本次RelayVSR"
```

超分段在同一节点按既有队列调度逐段执行。组内异常按原任务身份恢复，齐备后继续。

收到完整超分组的后台通知后，在来源会话使用分段计划所在目录拼接。联动任务的分段计划在本次执行目录的 `超分分段/` 下。脚本按每段的结果收尾报告核对文件，按源片顺序合并画面并封回原片音轨。成功返回 `status=joined` 与实际路径。

```sh
python .agents/skills/studio-video-processing/scripts/relayvsr_batch.py join --project "/实际项目" --record-dir "执行记录/本次RelayVSR"
```

联动任务使用 `--record-dir "执行记录/本次RelayVSR/超分分段"`。由调用方核对合片的分段接点，完成技术核对后按业务约定交回。

回归使用 `python -B -m unittest discover -s .agents/skills/studio-video-processing/scripts -p test_relayvsr_batch.py -v`。测试在临时目录验证分段、任务装配、取回合片和原声，不调用生成服务。
