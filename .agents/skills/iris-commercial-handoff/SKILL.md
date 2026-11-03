---
name: iris-commercial-handoff
description: Iris 商业视频返修与交接二级业务阶段，评估局部修复或重做、维护采用组合，按明确要求调用共用工具打包。
---

# Iris 返修与交接

按[阶段规则](references/流程规则.md)处理本次范围。业务阶段负责内容、业务条件和记录，不在内部嵌套更深业务技能。

- 输入：具体问题、原采用、允许修改范围、交接要求。
- 内部生产：[模板](templates/返修与剪辑交接.md)。
- 交付整理：[模板](templates/素材与剪辑交接说明.md)，来源于当前生产资料与实际成果。

Agent与脚本按[业务与工具分工](../iris-commercial-video/references/流程与交接.md#业务与工具分工)协作；工具接续查[能力状态](../iris-commercial-video/references/工具适配.md)，实际整理对外材料时读取[跨阶段交付规则](../iris-commercial-video/references/对外交付.md)。

先评估局部修复，合适才修，不合适回相关段重做。剪映包默认jypack、ZIP按需；Agent只有用户明确要求时才调用脚本生成并提供包，不手工打包或逐包打开剪映。日常网页下载由用户点击触发后台脚本及自动检查，详细分工归阶段规则。
