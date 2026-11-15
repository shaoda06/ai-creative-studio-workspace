# W685：补齐Herk-Edit-Kit分发接入

日期：2026-11-15
状态：已完成
关联版本：不涉及发布（仅文档整理）

## 修改原因

Herk Edit Kit 的来源和版本随 Studio 分发。接收方按上游说明可以装好工具，但 Studio 使用的根目录技能入口只在本机安装目录里。需要让接收方能按分发版说明生成该入口。

## 具体改动

- [Herk Edit Kit 安装与调用](../../../.agents/skills/studio-entry/references/Herk-Edit-Kit-安装与调用.md)补齐上游固定提交的安装步骤、Studio 入口正文和环境检查。统一入口和依赖表均链接到该说明。

## 验证结果

### 依赖专项审计

- 从暂存内容导出隔离工作区，逐条运行说明里的命令。检出 `10511e5`，安装锁定依赖并通过上游 11 项测试。核实上游入口、原许可证和 Studio 入口可用，外部安装目录仍由 Git 忽略。
- Studio 统一入口和生成的 `herk-edit-kit` 均通过格式校验。Codex `skills/list` 返回隔离目录中的 `herk-edit-kit/SKILL.md`，该文件能定位上游 `short-form-edit`。
- HyperFrames 的本地渲染环境检查通过。上游示例 lint 为零错误、零警告，实际渲染出 8 秒、1920×1080 的 MP4，并通过 FFmpeg 完整解码。实装与渲染在 macOS 核验。
- `npm ci` 报告锁定依赖有 8 项漏洞（6 高、2 中）。本次沿用登记的固定提交和锁文件。

公共组件复用检查覆盖本次 Markdown 差异。改动为技能安装说明、引用与记录，未涉及 UI 组件或页面行为。
