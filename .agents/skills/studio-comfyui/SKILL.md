---
name: studio-comfyui
description: 共用ComfyUI通信与提交工具，提供工作区配置、实际参考上传、请求提交和结果通信，依托持久任务后台运行；不决定业务内容、图种或阶段。
---

# Studio ComfyUI通信与提交

使用scripts/comfyui_dispatch.py将明确任务交给[任务后台](../studio-workspace-browser/SKILL.md)，不另建轮询或监控器。配置读取工作区comfyui-config.json，不输出凭据。实际请求、上传、任务ID和取回证据保留在调用方指定范围。

任务参数、准备/提交、技术结果适配和命令见[提交接口](references/ComfyUI工具调用规范.md)。只准备使用--prepare-only，已有授权且输入齐备时才提交。超时或取回失败恢复原任务，不自动重新POST。

scripts/comfyui_client.py维护通信；scripts/project_paths.py维护路径边界；scripts/workflow_graph.py维护画布转换。普通提交不做远端库存盘点；明确诊断时按现有[库存](dependencies/comfyui-inventory/SKILL.md)或[故障诊断](dependencies/comfyui-troubleshooter/SKILL.md)进入。具体模型装配由对应工具负责。

执行凭据默认归并；旧独立文件及新档案的读取、按需导出见[固定记录接口](references/固定脚本接口规范.md#聚合执行凭据读取与导出)。
