# Qwen工具调用规范

## Agent与脚本

调用方给出实际内容和目标。Agent按qwen-image-2-1-prompter的T2I或Edit方法编写并核对正文；脚本原样装配，不生成或改写创意，不选择角色视图、布局或业务采用。

## 装配接口

从工作区根执行：

~~~sh
python3 .agents/skills/nora-qwen-image/scripts/qwen_image_workflow.py --request /实际请求.json --output /新装配结果.json
~~~

Python 3.9以上。request/output为本地路径，相对路径按当前目录解析；输出独占新建。请求示意：

~~~json
{"mode":"t2i","prompt":{"rewritten_prompt":"本次由Agent写好的完整实际正文","wh_ratio":"1:1"},"size":[1024,1024],"seed":123,"prefix":"request-001","references":[],"parameters":{}}
~~~

mode为t2i或edit；size为明确宽高像素且为32倍数；seed为0至2的64次方减1之间的整数。edit的references按实际输入顺序提供1至10个文件路径，t2i不带图。parameters只接受negative_prompt，其他固定技术配置按模式规范。remote_output可显式提供最终输出前缀，省略时使用prefix；上传目录仍为prefix。图片内容及目标规格均由调用方决定。

输出包含workflow、uploads、output_node及canvas；Qwen的canvas为空，不改原画布或生成修改过的任务画布。uploads指明每张实际素材与节点输入，上传后由后台写入真实远端路径。进程退出0且结果文件写成表示装配成功，不代表提交或生成成功；错误保留具体原因，不自动重发。

Python调用为assemble(prompt=..., size=..., seed=..., mode=..., references=..., parameters=..., prefix=..., remote_output=...)。没有项目卡片、短剧编号或业务目录参数。

## 执行及结果

调用方将明确的工作流、输出映射和执行授权交给[ComfyUI工具](../../nora-comfyui/SKILL.md)。业务结果接入由调用方指定；只要技术结果时可使用technical图片计划，不要求业务工作稿。脚本保留正文原样、参考顺序、实际上传、请求和取回证据。结果返回后，由业务处理候选和采用。
