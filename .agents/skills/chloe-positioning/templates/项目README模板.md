# {{title}}｜Chloe视频项目

## 项目定位与业务范围

本项目用于自营视频内容与带货业务。当前账号的发布平台、目标人群和内容风格，统一见[账号定位](综合资料/账号定位.md)。

## 一级业务入口

由[Chloe AI视频带货]({{skills}}/chloe-commerce-video/SKILL.md)组织业务。进入成片发布准备、用户提供发布结果或明确提出发布协助时读取[Chloe运营接入]({{skills}}/chloe-positioning/references/社媒运营接入规范.md)，再调用公共运营。

## 目录结构与资料存放

- `projects/`：每条视频一个V编号项目，包含脚本、制作记录、专属资源、剪辑交接与人工成片。
- `综合资料/`：账号定位、选品记录、运营复盘、商品资料、共用素材说明与共用资源。
- `综合资料/商品资料/`、`综合资料/共用素材/`：商品、模特、服装、造型、场景、声音的说明及资源引用。
- `综合资料/资源/`：共用图片、视频、音频的唯一正式存储及版本记录；资产说明和视频项目只引用准确版本。

目录由[初始化规范]({{skills}}/chloe-positioning/references/工作区与初始化规范.md)与脚本维护，技能统一归总目录，不复制到本资料区。

## 项目索引入口

从[视频项目入口](projects/README.md)及projects实际子目录查找；当前进度只维护在各视频README，不另做重复进度表。

## 项目专用约定

无。仅记录用户确认的项目专用约定或例外。

## 项目接续与相关资料

会话入口按[会话入口登记]({{skills}}/chloe-commerce-video/references/会话组织与接续规范.md#会话入口登记)维护：

| 会话名称 | 职责 | 真实会话入口 |
| --- | --- | --- |

处理具体视频时主动读取本README、视频README、脚本和与当前任务有关的制作记录。账号方向只在账号定位维护。初始化阶段不预设已选商品或已采用资产，不建立账号连接与权限配置。

按当前任务读取[资产制作规范]({{skills}}/chloe-assets/references/资产制作规范.md)、[声音资产流程]({{skills}}/chloe-assets/references/声音资产制作流程.md)、[资源保存与引用]({{skills}}/chloe-assets/references/资源存储与引用规范.md)、[视频制作与页面接入]({{skills}}/chloe-production/references/视频制作流程与记录.md)、[剪映交接]({{skills}}/chloe-handoff/SKILL.md)或[运营与展示接入]({{skills}}/chloe-positioning/references/社媒运营接入规范.md)。通用约定见[总工作区AGENTS]({{studio}}/AGENTS.md)。

固定资料的章节、字段、表格和更新方式按[固定资料写法规范]({{skills}}/chloe-positioning/references/固定资料写法规范.md)，写入后运行该规范的检查命令。
