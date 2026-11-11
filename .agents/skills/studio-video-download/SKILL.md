---
name: studio-video-download
description: 从用户指定的抖音、小红书等作品链接取得视频文件，解析分享短链，按需用 Computer Use 和 Chrome 扩展从播放器下载，并核对媒体与来源。
---

# Studio 视频下载

用于单独下载视频，也供需要视频原件的业务调用。交回实际作品页、已保存文件的绝对路径及实测媒体信息。字幕、转写与画面分析交给[视频读取与分析](../studio-video-study/SKILL.md)，正式入库、采用与裁剪由调用业务负责。

## 定位作品并选择下载路径

1. 从分享文字提取完整 URL，保留打开作品所需的参数，跟随短链跳转。用作品 ID、标题或作者核对目标，只处理用户指定的作品。记录实际可打开的作品页，媒体直链用于取文件。
2. 已有对应文件时直接核对。优先沿用用户指定或已验证可用的下载工具。使用 `yt-dlp` 时限定单条作品，读取实际输出路径。没有可用下载器、提取器无法解析、作品接口返回 403 或要求当前浏览器会话时，切到下节。同一失败条件下不反复提交。
3. 有明确保存位置就沿用。浏览器直接下载时核对工具返回的文件及实际下载位置；命令行下载使用本次任务的临时目录。若调用方只需要已有字幕，按其要求获取相应字幕即可。

```bash
taskUrl='https://实际作品页'
taskWork=$(mktemp -d "${TMPDIR:-/tmp}/studio-video-download.XXXXXX")
yt-dlp --ignore-config --no-playlist --no-overwrites --no-simulate \
  --socket-timeout 20 --retries 2 --fragment-retries 2 \
  -P "$taskWork" -o '%(extractor_key)s-%(id)s.%(ext)s' \
  --print after_move:filepath -- "$taskUrl"
```

按需下载作品已有字幕时使用 `--write-subs`、`--write-auto-subs` 和 `--sub-langs` 指定语言。仅取字幕可用 `--skip-download`，从实际输出确认字幕文件。命令为 Bash 示例，Windows 使用实际可执行文件与 PowerShell 的参数、路径写法。

## 用 Computer Use 和 Chrome 扩展下载

1. 用 Codex 的 **Computer Use 浏览器工具**操作本机 **Chrome**。**ChatGPT Chrome 扩展**负责连接已启用扩展的 Chrome profile，实际页面操作和下载由 Computer Use 发起。按当前工具文档选择 `@Chrome` 或创建 Chrome 标签页，确认目标 profile。若当前工具提供 `cua.createBrowserTab`，可调用 `cua.createBrowserTab("chrome", workUrl, { sessionName: "🎬 视频下载" })` 打开核实过的作品页。标签页与窗口收尾按[共用浏览器操作](../studio-browser-operations/SKILL.md)执行。
2. 打开核实过的作品页，等待对应视频播放器加载。用页面实际作者、标题或作品 ID 确认目标，再定位当前作品的播放器。当前工具文档支持 `downloadMedia()` 时，对该播放器的 `<video>` 元素调用，核对实际返回的下载文件和状态。也可以使用作品页实际提供的下载入口。
3. 浏览器取文件失败且页面确实提供了可访问的直接媒体 URL 时，按播放器实际加载的地址用 `curl --fail --location --output` 保存原文件，Windows 使用 `curl.exe`。只在真实请求需要时沿用已知 Referer 等请求条件。若播放器仅有 `blob:` 地址，从当前工具可见的页面媒体资源中确认与该播放器对应的真实 URL。直接地址失效时从作品页重新取得。域名解析失败时先确认网络和解析是否恢复，再重试一次。避免在报告中输出带访问参数的媒体地址。
4. 网站要求登录或验证码时，请用户在目标 profile 完成，再从原作品页继续。访问或下载权限被明确拒绝时，按实际权限处理。不导出浏览器 Cookie、读取账号凭据或猜测签名。

### Chrome 连接失败时先由用户自查

1. 区分连接失败、作品页访问失败、播放器未加载及文件下载失败。列浏览器或开标签页时收到 `Local browser use is disabled in Work settings` 或 `Local browser access is unavailable for this chat` 一类提示，先报告原始报错和所处步骤，按下面的顺序请用户自查。
2. 请用户在 ChatGPT 桌面端核对 **设置 → 电脑操控 → Google Chrome** 的连接状态。显示「安装」时按提示安装，显示「管理」时核对当前使用的 Chrome profile 内已安装并启用 **ChatGPT** 扩展。若客户端的 **设置 → 工作偏好** 提供「使用本地浏览器」，确认已开启。保持目标 Chrome 窗口打开，并在必要时重启桌面端或 Chrome。网站权限提示只处理当前作品需要的权限。具体界面按[官方 Chrome 扩展说明](https://learn.chatgpt.com/docs/chrome-extension#troubleshooting)核对。
3. 用户完成自查后，在当前对话用同一个 Chrome 入口重试。仍无法连接时，由用户新建本地对话，或按用户的授权在原工作区和指定分区新建。带上原作品页、目标 profile（如已核实）、已完成的自查及具体报错，在新对话选择或调用 Chrome 再试。新对话可用时沿用它继续本任务。
4. 新对话仍失败，或没有可用的取文件路径时，报告实际阻塞位置，并请用户提供可用的本地视频文件。只有网页、封面或播放器时长时，按已获得的证据报告。

## 核对并交回文件

先用 `ffprobe` 确认真正的视频流、音轨、时长、分辨率与画幅。排除封面流、HTML 响应、未完成下载和空文件。用 `ffmpeg` 完整解码视频及存在的音轨，结合作品页信息核对下载对象。

```bash
taskVideo='/absolute/path/video.mp4'
ffprobe -v error -show_entries format=duration,start_time:stream=index,codec_type,codec_name,width,height,avg_frame_rate,sample_aspect_ratio,display_aspect_ratio,start_time:stream_tags=language,title:stream_disposition=attached_pic -of json "$taskVideo"
ffmpeg -v error -xerror -nostdin -i "$taskVideo" -map 0:V:0 -map '0:a?' -f null -
```

按实际结果交回作品页、文件绝对路径、时长、分辨率和解码结果。无音轨可以是源文件的正常状态，按实测注明。文件临时存放时说明实际位置，供后续分析或登记复用。
