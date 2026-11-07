# Chloe 账号概况演示资料

这里是页面专用夹具，不是业务工作区。`new`展示尚未填写账号定位的新账号；`working`展示虚构的女装方向、模拟连接及三条视频进度。品类、账号名、权限和事项均不代表实际决定。

资料从现行`chloe-positioning`账号模板及`chloe-creative`视频README模板填写，后端使用`chloe_documents.read_document`校验并读取；没有另外保存统计JSON或第二份采用状态。这里只保留本页需要读取的文档，不声称是完整初始化工作区，不包含实际媒体、凭据、资源引用或发布证据。

入口：`#/examples/chloe/overview`。只读接口：`GET /api/examples/chloe/overview?scenario=working`，另支持`new`。接口固定在本目录取材，不接受工作区路径；不注册到实际空间列表，不创建任务，不写入`workspaces/Chloe Workspace`。

页面复用`ChloeAccountOverview`，正式账号概况已读取所属空间的实际文档，使用同一个展示组件。当前只评审账号概况，其他栏目保持原状。

验证：在`工作区浏览服务`运行`.venv/bin/python -m unittest tests.test_chloe_overview -v`及`node tests/test_chloe_overview_ui.mjs`。前者检查模板读取、统计来源及只读接口边界；后者使用接口同源样例，检查两种状态、长内容、错误重试及三档桌面布局，不调用真实业务接口。
