# Nora｜连续短剧与社媒运营资料区

## 工作区定位与业务范围

本目录是AI Creative Studio内的Nora业务资料区，保存连续短剧、独立篇章、角色资产项目及所属社媒运营资料。日常在AI Creative Studio Workspace总目录新建Codex对话，不另建技能库或浏览服务。

## 一级业务入口

- [Nora连续短剧](../../.agents/skills/nora-serial-drama/SKILL.md)
- [Studio社媒运营](../../.agents/skills/studio-social-operations/SKILL.md)

按实际项目类型和当前阶段进入业务；已有角色资产等项目继续遵循各自README的专用约定。

## 目录结构与资料存放

- `projects/`保存独立项目；各项目的阶段目录按所属业务及项目约定维护。
- `综合资料/`用于Nora跨项目资料，按实际需要建立。
- `comfyui-config.json`属于Nora资料空间；任务库及连接配置集中于总后台的`runtime/workspaces/nora/`，按[运行资料维护规范](../../.agents/skills/studio-workspace-browser/references/任务运行资料维护规范.md)管理，资料区不另建服务目录。
- 技能、规则、模板和共用工具统一位于总目录`.agents/skills/`，公共浏览服务在总层运行。

## 项目索引入口

- [项目总索引](projects/项目总索引.md)
- [项目目录说明](projects/README.md)

索引负责项目定位和排序，各项目进度只在对应状态文件维护。

## 工作区专用约定

- 共用行为、授权和规则优先级按[总工作区约定](../../AGENTS.md#项目规则读取与适用)执行。处理具体项目先读其README和当前进度，再按本次任务定位资料；项目已确认约定优先，不把例外扩到其他项目。
- 共用规则及工具维护在总层，不在业务项目复制执行实现。任务提交明确实际project，查询和恢复明确本资料根作为workspace，不以总技能库位置判断业务归属。
- 新项目按所属一级/二级规则建档；真实项目、候选、采用、历史及任务记录不随工具维护改写。隔离技术测试不混入真实项目，按总工作区技术测试规范安排。

## 项目接续与相关资料

先明确Nora和实际项目根目录，读取本文件、项目README及其指定的唯一进度文件，再按当前阶段接续；已经读过且未变化的资料不重复读取。README由Agent按任务主动读取，不宣称Codex默认自动加载。

- 新建或整理一级子工作区：[工作区结构与README规范](../../.agents/skills/studio-entry/references/一级子工作区结构与README规范.md)
- 新建连续短剧项目：[项目README规范](../../.agents/skills/nora-drama-positioning/references/项目README规范.md)
- 运营项目入口：[运营项目README规范](../../.agents/skills/nora-operations-setup/references/运营项目README规范.md)

历史旧路径不作为另建项目实体、技能库或后台的入口。已归档项目按其归档说明只读追溯，不恢复旧制作流程。
