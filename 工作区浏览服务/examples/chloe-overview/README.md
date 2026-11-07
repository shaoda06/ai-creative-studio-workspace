# Chloe 账号概况演示资料

这里保存账号定位与视频进度的隔离样例：`new`是未填写的方向，`working`是虚构的女装方向，不代表实际决定。使用现行账号定位模板和`chloe_documents.read_document`读取，不包含账号配置。working包含三个虚构视频，覆盖待用户决定、人工后期及未开始；new没有视频，仍展示统计和进度空状态。

入口：`#/examples/chloe/overview`。只读接口：`GET /api/examples/chloe/overview?scenario=working`，另支持`new`。页面与正式账号概况复用`ChloeAccountOverview`；示例不注册为工作区、不写业务资料、不创建任务。

验证：在`工作区浏览服务`运行`.venv/bin/python -m unittest tests.test_chloe_overview -v`及`node tests/test_chloe_overview_ui.mjs`，覆盖真实模板投影、文档更新、缺失与格式错误、两种状态、长内容、错误重试及三档桌面，测试不调用真实业务接口。
