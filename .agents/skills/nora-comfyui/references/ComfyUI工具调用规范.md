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
