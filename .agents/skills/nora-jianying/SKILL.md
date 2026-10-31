---
name: nora-jianying
description: 共用剪映草稿与归档工具，按明确视频顺序、包内文件名和时间线选择输出ZIP或原生jypack；不决定业务采用、完集状态或剪辑内容。
---

# 剪映草稿与打包

Agent提供实际文件、播放顺序、包内名称和输出位置；脚本保留原媒体，生成一条不裁剪、速度1、音量1的原声视频轨道。可将其他版本仅放入素材箱。业务阶段决定哪些文件进入交付、哪些版本进入时间线。

使用现有Python环境中的`pyJianYingDraft==0.3.0`和`pymediainfo==7.0.1`；本工作区可复用浏览服务`.venv`，无需运行后台服务。调用[scripts/jianying_export.py](scripts/jianying_export.py)：

```json
{"name":"草稿名称","media":[{"file":"/绝对路径/视频.mp4","member":"视频.mp4","timeline":true}]}
```

```bash
python jianying_export.py manifest.json /输出路径/草稿.zip --format zip
python jianying_export.py manifest.json /输出路径/草稿.jypack --format jypack
```

输出位置须已存在，输出文件须不存在。文件按清单顺序排列；`timeline:false`只入素材箱。ZIP保存媒体原字节及三份草稿JSON，原生jypack只转换容器签名。包内路径必须相对且不越界。失败返回真实异常并清理本次CLI创建的残包；不覆盖已有输出。调用方直接使用`export_archive`时负责临时文件生命周期。

后台可调用同一工具并通过响应流提供下载；服务负责请求鉴权、文件访问边界、临时文件清理。工具不读取项目、EP编号、采用记录或网页状态，不自动添加字幕、音乐、转场、变速或最终成片。草稿结构检查和真实剪映导入验收分开报告，不将生成文件视为已在客户端导入。
