# ComfyUI工具调用规范

## 提交与准备

使用工作区已有Python环境，从工作区根调用：

~~~sh
python3 .agents/skills/nora-comfyui/scripts/comfyui_dispatch.py --project /实际项目目录 --plan 相对项目的任务清单.json --prepare-only
~~~

任务清单是调用方业务接入的准备入口，业务阶段负责解释其模板、类型和来源。--prepare-only只准备、不上传、不提交；已有有效生成授权且准备通过时移除此参数入队。返回prepared或enqueued分别表示对应步骤完成。参数完整说明使用--help，历史命令入口继续转调同一实现。

无业务工作稿的图片技术任务可用旧式明确参数入口：--project、--task-type image、--workflow实际API文件、--record-dir项目内执行目录、--task-title、--output-plan、--image-plan。所有JSON文件路径按当前命令目录解析，记录和输出路径按项目边界核对。image-plan例如：

~~~json
{"adapter":"technical","images":[{"path":"生成结果/图片.png","width":1024,"height":1024}]}
~~~

output-plan仍显式提供输出节点、images索引、项目内目标和取回凭据名。technical只保存实际结果和技术报告，不填写人物卡或业务采用；未指定adapter的既有业务计划仍使用原业务登记及安全要求。新任务与恢复均保留真实会话上下文、原服务和请求，不能用技术适配伪称业务已采用。

## 配置与通信

scripts/comfyui_config.py读取实际工作区comfyui-config.json，按既有格式和认证执行；不输出密码或复制凭据到请求。通信实现为scripts/comfyui_client.py，所有文件访问保留项目边界。日常任务不自动查询库存或安装节点。

## 状态和恢复

查询与报告由[后台客户端](../../nora-workspace-browser/SKILL.md)完成。超时先查原任务；已取回成果的登记失败只修复登记；取回失败只请求原任务取回重试。真实错误保留，不自动换节点、重提或改配置。业务采用和网页同步按对应接入分别处理。

## 无短剧资料的视频技术任务

明确API入口在上述逐项参数基础上提供`--task-type video-first-pass`、`video-second-pass`或`video-postprocess`及`--video-plan`，其JSON为：

~~~json
{"adapter":"technical","metadata":"ffprobe"}
~~~

原生H3分段输出使用`--output-plan`空数组及`--segment-plan`，逐一填写实际运行组序、导演台/报告节点、远端output根和本机成果位置。其他视频使用明确`outputs`映射。任务组清单也支持`video_plan`同一适配，提供`canvas`、`output_nodes`、明确`outputs`或`segment_plan`、`record_dir`和本次授权；不填短剧mapping、人物卡或EP。

工具只装配实际模式与参考槽位，后台保存取回凭据和ffprobe报告，不创建短剧候选审阅、修改轮次或采用。未知adapter报错；省略adapter的现行/历史短剧请求继续遵循其原业务检查。技术任务不得用来冒充短剧已完成或已采用。

## 工作流资源登记与下载

工作流仍保持唯一物理位置，scripts/workflow_paths.py同时登记逻辑分类与工具实际目录。浏览服务使用原分类URL列出并下载明确工作流/API文件，不假设资源都在旧主技能根内；只允许登记目录中的直接文件，并保留所属目录边界和越界拒绝。目录归属变化不修改模型参数或项目任务副本。
