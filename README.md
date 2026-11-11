# AI Creative Studio Workspace

`ai-creative-studio-workspace` 是用于AI视频创作、资料与素材管理、制作及迭代的工作区模板。包含统一业务入口、Nora短剧、Iris商业视频、Chloe带货及共用运营阶段、共用生成工具、配套工作流，以及Krea2本地风格库。三个业务资料区及真实项目由使用者在本地初始化，不随公共仓库提供。

## 开始使用

在Codex中选择本总目录。Nora、Iris、Chloe是资料分区；总入口、一级业务、二级阶段和共用工具都在本目录.agents/skills中，不必切换子目录才能使用技能。

统一入口为[AI创作与制作](.agents/skills/studio-entry/SKILL.md)。[共用视频制作核心](.agents/skills/studio-video-production/SKILL.md)从已确认脚本接续到视频候选与技术结果，按环节调用共用规则和工具。[Nora 短剧](.agents/skills/nora-serial-drama/SKILL.md)、[Iris 商业视频](.agents/skills/iris-commercial-video/SKILL.md)与[Chloe 带货](.agents/skills/chloe-commerce-video/SKILL.md)分别负责业务准备、审阅、返修接续、采用及交付。[Studio 社媒运营](.agents/skills/studio-social-operations/SKILL.md)等附加能力按实际任务接入。

1. 获取整个工作区，使用支持本地文件与技能的agent打开根目录。推荐Codex Desktop；其他平台需自行提供相应的会话和监控能力。
2. agent先读取根目录 [AGENTS.md](AGENTS.md)，再按任务使用 [统一入口](.agents/skills/studio-entry/SKILL.md) 或 [Krea2技能](.agents/skills/studio-krea2-style-library/SKILL.md)。处理具体业务项目时，继续读取所属业务工作区README、项目README及唯一进度或状态文件；后两层使用README，不另设AGENTS.md。
3. 告知业务类型、项目名称、素材和目标，由对应业务按阶段建档；已有项目直接接续。三个ComfyUI适配技能随仓库提供，不重复安装。其他能力先按名称发现可用入口，缺失时按[公共依赖登记与获取](.agents/skills/studio-entry/维护规范.md#6-依赖获取与适配资料)补齐本次所需项。
4. 新增外部技能默认安装到本工作区 `.agents/skills/{技能名}/`，已有可用安装复用。该工作区是本README所在目录，不是某部短剧的项目目录。当前独立安装的外部技能按 `.gitignore` 排除；新增技能默认可被Git发现，提交前核对来源、许可及是否需要随模板提供。
5. 初始化项目工作区时，按下方[FFmpeg初始化与运行](#ffmpeg初始化与运行)落实媒体处理依赖；服务地址询问及配置按[主技能的工作区ComfyUI配置](.agents/skills/studio-comfyui/references/ComfyUI-服务配置与任务提交规范.md#工作区-comfyui-配置)执行。

不需要ComfyUI即可进行策划、剧本和资料整理。执行生成时，使用者须自行准备能够运行配套工作流的ComfyUI服务；本工作区不附带模型权重、不自动安装服务端节点，也不保证任意后端都兼容。随包节点资源的存放、获授权安装及验证按[节点与安装包](.agents/skills/studio-entry/维护规范.md#comfyui节点与安装包)执行；任务核对遵循执行规范。

## 初始化业务工作区

各业务分别维护初始化流程，按需要启用；已有资料区直接接续。命令从本README所在的Studio总目录运行，Python 3.10及以上即可创建骨架，无需启动网页或连接生成服务：

```sh
python3 .agents/skills/nora-drama-positioning/scripts/workspace_init.py --workspace 'workspaces/Nora Workspace' --register
python3 .agents/skills/iris-commercial-brief/scripts/workspace_init.py --workspace 'workspaces/Iris Workspace' --register
python3 .agents/skills/chloe-positioning/scripts/chloe_init.py --workspace 'workspaces/Chloe Workspace' workspace --register
```

三个入口分别见[Nora初始化](.agents/skills/nora-drama-positioning/references/工作区与初始化规范.md)、[Iris初始化](.agents/skills/iris-commercial-brief/references/工作区与初始化规范.md)、[Chloe初始化](.agents/skills/chloe-positioning/references/工作区与初始化规范.md)。脚本只补缺，不覆盖已有README、业务资料、配置或独立Git。Chloe还需使用project命令建档；项目名称必须由用户提供或明确选定，没有名称时先讨论，不能用待命名跳过。未确定的账号方向保持待确定，不创建示例订单、剧集、视频或媒体。

`--register`接入同一个浏览服务：Nora使用默认目录，Iris与Chloe写入本地空间登记；省略时只建资料区。完成初始化后按服务README安装依赖、构建并启动；初始化本身不启动、重启服务，不提交生成。

旧版使用者先保留自己的项目、提示词、配置和任务库，再按所属业务迁移到实际资料区。Git更新及初始化都不会自动搬迁旧`projects/`或旧提示词库，也不覆盖现有业务决定。

## 会话组织

会话职责、命名和接续按所属业务维护：Nora读取[会话与进度管理规范](.agents/skills/nora-serial-drama/references/会话与进度管理规范.md)，Iris读取[流程与交接](.agents/skills/iris-commercial-video/references/流程与交接.md)，Chloe读取[会话组织与接续规范](.agents/skills/chloe-commerce-video/references/会话组织与接续规范.md)，独立社媒运营从[运营入口](.agents/skills/studio-social-operations/SKILL.md)接续。实际会话入口留在所属项目，不统一套用某项业务的编号。

## 目录

| 位置 | 用途 |
| --- | --- |
| `AGENTS.md` | 工作区约定、默认依赖安装位置及本地Git提交规则 |
| `.agents/skills/studio-entry/` | 统一业务路由与共用能力登记；H3工作流由studio-h3维护，视频处理工作流由studio-video-processing维护，统一按studio-comfyui中的登记定位 |
| 一级业务及其二级阶段 | Nora短剧、Iris商业视频、Chloe带货与Studio运营的业务入口和阶段；阶段内维护规则、模板及脚本，不再嵌套业务子技能 |
| `.agents/skills/studio-social-operations/` | 工作区通用运营一级路由及六个共享二级业务阶段，管理账号、个人页、封面、发布包、复盘和制作反馈 |
| `studio-combat-methods/`、`studio-fantasy-combat/`、`studio-realistic-combat/` | 位于 `.agents/skills/`，由业务技能按戏型选择通用、玄幻、写实打戏方法 |
| `.agents/skills/studio-comfyui/dependencies/` | 三个ComfyUI适配技能的真源；节点源码目录或ZIP安装包统一放在其 `ComfyUI节点资源/` 子目录，保留来源、版本与许可证 |
| `.agents/skills/studio-krea2-style-library/` | 风格库使用与维护指引 |
| `.agents/skills/studio-prompt-library/` | [提示词管理子技能](.agents/skills/studio-prompt-library/SKILL.md)，由各业务按需调用或独立使用，管理统一提示词库中的公开与隐私内容 |
| `提示词库/` | 统一提示词资料目录；`公开/` 随公共仓库保存和分发，`隐私/` 仅本地保存且不入Git；网页统一管理，一份提示词对应一个MD文件 |
| `.agents/skills/studio-archive/` | 整个项目的归档标记、浏览分类与关联 Codex 对话归档／恢复，资料保留原位 |
| `工作区浏览服务/` | React＋FastAPI浏览服务、双击启动、共用解析器与开发历史 |
| `工作区浏览服务/Krea2风格库/` | 本地浏览页、当前风格资源、更新程序和启动入口 |
| `workspaces/Nora Workspace/projects/` | Nora真实短剧及角色项目 |
| `workspaces/Iris Workspace/projects/` | Iris商业订单，本地保存 |
| `workspaces/Chloe Workspace/` | Chloe具名项目，各项目独立维护综合资料与共用资产，项目内projects保存单条视频 |
| `综合资料/` | 跨项目资料、未分类资料和本机过程资料，模板仅保留目录说明 |

技能历史版本、真实服务库存、项目、个人配置和工具缓存仍可留在本机，但由 `.gitignore` 排除。不要把它们的本地存在误认为已被Git备份。

## 依赖与来源

### 能力组成与依赖登记

本项目的[独立第三方技能登记](.agents/skills/studio-entry/维护规范.md#独立第三方技能登记)维护直接使用的14项技能的来源、版本、许可与获取入口；这些技能不随模板重复分发。其自带子技能、脚本、运行依赖和安装步骤以该技能自身说明为准，不在本项目重复维护。

已经融入仓库的第三方资源另见[本地适配来源与更新](.agents/skills/studio-entry/维护规范.md#本地适配来源与更新)。保留原始来源与版本，后续按需比较、选择合并并验证，不用上游整包覆盖本地规则。全局技能及平台插件不列入项目安装清单；有实际调用需求时，由调用处说明所需能力并按平台发现。

检查或更新第三方技能时，两类均纳入范围，处理方式见[第三方技能更新规则](.agents/skills/studio-entry/维护规范.md#第三方技能更新范围与处理方式)。依赖变化与分发前按[依赖专项审计](.agents/skills/studio-entry/维护规范.md#依赖登记同步与专项审计)核对。浏览服务、媒体工具和风格资源继续由各自说明、锁文件和资源版本记录维护。第三方许可不由本仓库MIT许可证重新授权。

### 本工作区技能与风格资源

[统一入口](.agents/skills/studio-entry/SKILL.md)登记核心流程、各业务入口和共用附加能力。[视频读取与分析](.agents/skills/studio-video-study/SKILL.md)和[Krea2风格库](.agents/skills/studio-krea2-style-library/SKILL.md)按项目需要选用。第三方适配资源的来源与许可见[公共登记](.agents/skills/studio-entry/维护规范.md#6-依赖获取与适配资料)。

| 资源 | 来源与作者 |
| --- | --- |
| Clio风格库与预览 | [lumenastrum/clio-style-preview](https://github.com/lumenastrum/clio-style-preview)；风格文本主要来自 [u/Dear-Spend-2865原始分享](https://www.reddit.com/r/StableDiffusion/comments/1uzdj7o/krea_2_styles_wildcards_txt/) |
| Ray Moodboard资源包 | [Ray3780 / Ray Style Switching Extension](https://civitai.com/models/2856809/ray-style-switching-extension)；[发布元数据API](https://civitai.com/api/v1/models/2856809) |
| Moodboard原始来源 | [Krea官方Moodboard介绍](https://www.krea.ai/blog/moodboards-krea-2)、[服务条款](https://www.krea.ai/terms) |

现行资源随仓库保留，实际应用版本及来源下载地址见 [versions.json](工作区浏览服务/Krea2风格库/Krea2_风格资源/versions.json)。第三方授权事项由工作区维护者负责处理；这项分发安排不表示agent已经核实取得全部授权，也不改变原始许可。

### 运行环境与后端来源

- [Python](https://www.python.org/downloads/)：独立脚本按其调用说明使用；浏览服务的版本要求、虚拟环境及依赖安装见[服务安装说明](工作区浏览服务/README.md#安装与构建)。
- [FFmpeg](https://ffmpeg.org/download.html)：本地音视频裁剪、解码及合成依赖；安装与调用统一按[FFmpeg初始化与运行](#ffmpeg初始化与运行)。
- [Node.js](https://nodejs.org/)：浏览服务构建使用22及以上。
- [ComfyUI](https://github.com/Comfy-Org/ComfyUI)：由使用者独立部署的图片／视频生成后端。本仓库携带工作流及[已登记的节点源码或安装包](.agents/skills/studio-entry/维护规范.md#comfyui节点与安装包)，不携带模型权重，不自动部署服务端节点或依赖。服务地址与认证按[工作区共用配置](.agents/skills/studio-comfyui/references/ComfyUI-服务配置与任务提交规范.md#工作区-comfyui-配置)执行；节点、模型与兼容性问题按执行规范处理，这里的技能依赖清单不是后端安装清单。

## 环境

| 用途 | 要求 |
| --- | --- |
| 阅读规则与创作 | 可读写工作区文件的agent；对应阶段按需读取技能 |
| ComfyUI客户端、库存脚本、Krea2更新工具 | Python 3.9及以上，运行脚本仅使用标准库 |
| 本地音视频处理 | FFmpeg；按[初始化与运行规则](#ffmpeg初始化与运行)落实 |
| 本地版本维护 | Git；完成任务后按AGENTS规则提交，推送另需用户要求 |
| GitHub发布 | GitHub账号及仓库权限，可通过插件或已授权的GitHub CLI操作 |
| 浏览风格库和项目页 | 现代浏览器及工作区浏览服务；资源更新另需联网 |
| 浏览服务的Node测试 | 使用下方浏览服务开发环境中的Node.js 22＋运行 `node --test` |
| 工作区浏览服务 | Python、Node.js、pnpm及各平台通知条件统一见[服务安装说明](工作区浏览服务/README.md#安装与构建) |
| 技能格式校验 | 使用平台提供的 `skill-creator` 及其校验工具；按工具本身要求准备依赖 |

Python命令示例使用 `python3`；Windows按实际安装可改为 `py -3`。新浏览服务的Windows入口为批处理文件，其他平台按服务README启动。

### FFmpeg初始化与运行

FFmpeg是工作区的本地音视频处理依赖。只在初始化项目工作区时，由agent告知其用途并安装适合当前系统的可执行版本，安装来源使用[FFmpeg官方下载入口](https://ffmpeg.org/download.html)所列的系统安装包或构建。已有明确安装／成功调用记录时复用，不重复安装；多部短剧共用本机安装，不在每个项目内复制程序。

初始化完成后，将实际调用命令或可执行文件的绝对路径记入工作区 `综合资料/工作区本机运行环境.md`；这里只保存本机事实，不复制本节规则，程序和本机路径不随公共模板分发。

日常运行默认依赖已经具备，直接使用已记录的调用方式，不先检查程序是否存在、搜索命令或查询版本。实际调用因环境问题报错时，才向用户说明真实错误及受影响的操作；不在运行中自动安装、下载或升级依赖。此项免查指运行环境，不取消素材时长、格式、解码及输出文件的核对。

## 工作区浏览服务

Windows双击 [启动（Windows）.bat](工作区浏览服务/启动（Windows）.bat)，Mac双击 [启动（Mac）.command](工作区浏览服务/启动（Mac）.command)，由系统托管启动后自动打开 `http://127.0.0.1:8782/`。首页按登记空间发现业务项目：Nora、Iris项目位于各自资料区的`projects/`；Chloe具名项目直接位于资料区下，项目内部的`projects/`保存单条视频。Chloe项目页提供账号概况、选品与商品、共用资产、视频制作、成片与发布、运营复盘和资源库；完整制作页复用公共组件。服务同时提供Krea2风格库及开发记录。页面打开期间自动检测文件变化，局部更新列表；正在阅读的文档由用户选择切换新版本，不自动整页刷新。局域网使用本机局域网IP加8782端口，风格库管理开放本机及局域网IP地址，保留同源请求和操作凭证校验。双击对应系统的停止脚本结束本工作区服务；关闭Codex或网页不停止服务，不设开机或登录自启。Agent发布重启也走同一托管入口，详见[日常启动](工作区浏览服务/README.md#日常启动)。

首次安装、构建、开发及测试说明见[服务README](工作区浏览服务/README.md)。运行、构建及会话通知按服务README的环境要求准备；普通浏览与后台通知的条件分别列明。项目页面由浏览服务读取源资料展示，不再生成或维护项目静态HTML。

## Krea2风格库

从[工作区浏览服务](工作区浏览服务/README.md)的“风格库”进入，提供搜索、分类、预览、提示词复制及资源更新管理。服务的启动、停止与访问方式统一见服务README。

当前资源随工作区提供；检查、准备、审阅差异、应用和恢复均由使用者手动触发，不会自动升级。风格操作与文件结构见[使用说明](工作区浏览服务/Krea2风格库/使用说明.md)，agent检索与维护见[studio-krea2-style-library](.agents/skills/studio-krea2-style-library/SKILL.md)。

## 维护与检查

修改工作区技能前读取[维护规范](.agents/skills/studio-entry/维护规范.md)，使用 `skill-creator`。三个ComfyUI技能只在随包真源中维护，不从远端自动覆盖；吸收上游更新时检查适配差异并保留来源版本和许可证。Krea2的使用与维护规则集中在对应技能，不另设局部AGENTS。

按影响范围选择已有测试，不因普通文档修改运行全部测试。下列命令均在工作区根目录执行：

```sh
# ComfyUI通信客户端：本地测试，不访问生产服务。
python3 -B -m unittest discover -s .agents/skills/studio-comfyui/scripts -p 'test_*.py'
# 工作流脚本。
python3 -B -m unittest discover -s .agents/skills/nora-drama-production/scripts -p 'test_*.py'
# 项目浏览服务：在该目录执行资料解析、API与同步测试。
(cd 工作区浏览服务 && python3 -X utf8 -B -m unittest discover -s tests -v)
# 离线检查API结构及执行参数；不读取画布，不访问远端。
python3 -B .agents/skills/studio-comfyui/scripts/workflow_baselines.py
# Krea2：临时目录与本机临时端口测试，不联网更新资源。
python3 -B -m unittest discover -s 工作区浏览服务/Krea2风格库/Krea2_更新工具 -p 'test_*.py'
```

退出码0表示相应检查通过；脚本测试不等于用户批准素材，也不替代涉及交互修改时的浏览器检查。只维护说明且不影响项目数据结构时，不重新生成项目浏览页。

## Git边界

采用 `.gitignore` 排除清单：通用规则、技能、脚本、模板、源码和获准分发的资源可被Git发现；实际 `workspaces/`、总层综合资料内容、本机配置、运行库、缓存、历史归档及按需安装的外部技能不入库。Nora、Iris、Chloe通过各自初始化流程创建本地README和资料目录。公开提示词的新增、修改和删除按[提交规则](AGENTS.md#git-提交与推送)一并归入，隐私、回收站和临时文件继续排除。

开发记录与测试只分发通用实现、检查结果及独立示例。真实项目、客户订单、台词、账号决定、素材标识、任务和会话ID、个人路径及业务验收明细保存在本地资料中。原始画布及Krea2资源的分发范围沿各自来源与许可说明维护。

每次完成获授权维护并通过检查后，agent按上述规则，将本次任务与公开提示词变更归入同次本地提交；纯讨论和只读检查不提交，推送须另有明确要求。提交前查看差异和暂存清单，不混入并发修改。Git只保存被跟踪且已提交的文件；真实项目需另行安排私有版本管理或备份。

作为GitHub模板使用时，新建工作区获得当前目录和文件，但不会自动接收模板后续更新。同步更新前检查本地修改，不要覆盖使用者自己的内容。单独分享Nora技能时同时携带适用的许可证及三个随包依赖的许可证。

## 授权

本工作区原创技能、脚本及文档采用根目录 [MIT许可证](LICENSE)，允许修改、再分发和商用，保留版权及许可声明。

第三方内容不因放入本仓库自动改为MIT：三个ComfyUI适配技能保留各自许可证；Krea2风格文本、预览图及来源限制以对应上游来源的许可声明为准。


## 分层README规范

一级子工作区按[工作区结构与README规范](.agents/skills/studio-entry/references/一级子工作区结构与README规范.md)及其模板建立；业务项目分别按[Nora项目规范](.agents/skills/nora-drama-positioning/references/项目README规范.md)、[Iris项目建档规范](.agents/skills/iris-commercial-brief/references/项目建档与README规范.md)等所属业务入口维护；Chloe先按[具名项目结构](.agents/skills/chloe-positioning/references/工作区与初始化规范.md)维护项目README，再按[单条视频建档规范](.agents/skills/chloe-creative/references/视频项目与脚本规范.md)维护其内部视频README；公共运营只规定[接入信息要求](.agents/skills/studio-operations-setup/references/运营项目README规范.md)，不另定项目结构。它们的结构规则与模板各归所属维护入口，不复制到资料区形成另一套现行规范。
