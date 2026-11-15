# Herk-Edit-Kit-安装与调用

Studio 从本工作区的 `.agents/skills/herk-edit-kit/SKILL.md` 进入 Herk Edit Kit，再读取该工具目录里的上游 `.agents/skills/short-form-edit/SKILL.md`。已有可用安装时直接读取入口。执行时按 [Studio 的按需剪辑与动效工具](../SKILL.md#按需剪辑与动效工具)确定调用范围。

## 首次安装

准备 Git、Node.js 22 及以上版本、npm、FFmpeg（含 ffprobe）和 Chrome 或 Chromium。以下命令从 Studio 总工作区根目录执行，Windows 可使用 Git Bash。已有工具目录且只缺 Studio 入口时，确认已装版本和运行依赖后直接执行第 2 步。

1. 获取[依赖登记](../维护规范.md#独立第三方技能登记)指定的完整仓库，并按锁文件安装依赖。上游的配套技能、脚本和许可证都保留在工具目录中。

   ```bash
   git clone --no-checkout https://github.com/nateherkai/herk-edit-kit.git .agents/skills/herk-edit-kit &&
     git -C .agents/skills/herk-edit-kit checkout --detach 10511e5af86fc47756ea89803b397422e2d89284 &&
     npm --prefix .agents/skills/herk-edit-kit ci &&
     npm --prefix .agents/skills/herk-edit-kit run setup
   ```

   克隆及检出成功后，如依赖安装中断，可从 `npm ci` 接着执行。

2. 在工具根目录生成 Studio 的技能入口。已有可用的根目录 `SKILL.md` 时直接复用。

   ```bash
   cat > .agents/skills/herk-edit-kit/SKILL.md <<'EOF'
   ---
   name: herk-edit-kit
   description: 用于已有口播底片且视觉方向明确的复杂动效字幕、字卡或图形包装。需要 HyperFrames 预览或渲染时，按 Studio 的共用调用条件选择。
   ---

   # Herk Edit Kit

   先按[Studio 的按需剪辑与动效工具](../studio-entry/SKILL.md#按需剪辑与动效工具)确认本次范围，再读上游 [short-form-edit](.agents/skills/short-form-edit/SKILL.md) 中与本次工作相关的段落。配套 HyperFrames 和方法资料按该入口引用读取，路径以本目录为工具根。

   复用实际底片的字级时间轴，按项目确认的样式做字幕或图形层。项目目录、素材、音画改动和交付范围沿用工作区实际授权。根目录示例用作技术验证；AIS 品牌素材遵守[许可证](LICENSE)中的单独条款。
   EOF
   ```

3. 检查测试和 HyperFrames 环境。打开以 Studio 总目录为工作区的新 Codex 会话，可按 `herk-edit-kit` 发现技能，或从 Studio 入口按上方路径读取。

   ```bash
   (
     cd .agents/skills/herk-edit-kit &&
       npm test &&
       npx --no-install hyperframes doctor
   )
   ```

本地预览与渲染关注 `doctor` 的 Node.js、FFmpeg、ffprobe 和浏览器检查。首次渲染可能下载 HyperFrames 所用的无头浏览器。测试与示例渲染无需 API 密钥。外部服务按所选功能配置，详情见 [上游环境与故障说明](https://github.com/nateherkai/herk-edit-kit/blob/10511e5af86fc47756ea89803b397422e2d89284/docs/SETUP.md)。
