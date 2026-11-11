---
name: studio-comfyui
description: 在准备、装配交接或提交明确的 ComfyUI 请求时使用。按所属工作区配置、素材和输出映射交给统一后台，查询和恢复从原任务接续。
---

# Studio ComfyUI通信与提交

使用scripts/comfyui_dispatch.py将明确任务交给[任务后台](../studio-workspace-browser/SKILL.md)，不另建轮询或监控器。配置读取工作区comfyui-config.json，不输出凭据。实际请求、上传、任务ID和取回证据保留在调用方指定范围。

任务参数、准备/提交、技术结果适配和命令见[提交接口](references/ComfyUI工具调用规范.md)。只准备使用--prepare-only，已有授权且输入齐备时才提交。超时或取回失败恢复原任务，不自动重新POST。

scripts/comfyui_client.py维护通信；scripts/project_paths.py维护路径边界；scripts/workflow_graph.py维护画布转换。具体模型装配由对应工具负责。

| 当前任务 | 入口 |
| --- | --- |
| 共用队列查询、原任务恢复或结果取回 | [任务后台](../studio-workspace-browser/SKILL.md) |
| 需要核对 REST 协议、获授权的直接接口诊断或独立离线导出 | [ComfyUI API](dependencies/comfyui-api/SKILL.md)，工作区请求沿用实际所属空间的配置和认证 |
| 明确盘点可用节点、模型或诊断特定依赖缺项 | [ComfyUI 库存](dependencies/comfyui-inventory/SKILL.md) |
| 出现连接、提交、执行或取回异常，需要据原记录排查 | [ComfyUI 故障诊断](dependencies/comfyui-troubleshooter/SKILL.md) |

执行凭据默认归并；旧独立文件及新档案的读取、按需导出见[固定记录接口](references/固定脚本接口规范.md#聚合执行凭据读取与导出)。
