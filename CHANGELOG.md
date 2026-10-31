# 更新日志

## 2026-11-01（synologyer fork）
- 新增 Claude Desktop 只读 MCP 入口，不开放发送、签名或自动取钥功能。
- 新增明确账户目录配置、保留其他 MCP 的安装器，以及逐库认证的密钥导入。
- 新增 ARM64 启动时密钥捕获工具，不自动修改签名；账户分身可显式指定。
- 新增私有分账户缓存、测试和 Claude/分身安装指南。

## 2026-08-13
- **fix** 修复 `skill/scripts/check_env.sh` 自检时通过 `echo "$0" | bash` 把整个脚本再执行一遍来统计对勾的 bug，消除每次环境检查耗时翻倍（原 1~2 分钟）的问题。
- **perf** 新增 `scripts/summarize.sh` 一键包装，自动跳过 `check_env` 与运行前清理；`prepare` 步骤由 1~2 分钟降至约 4 秒。
- **docs** 明确总结流程保持纯 agent 执行：`prepare` → agent 读取 `prompt.txt` 写出 `summary.json` → `render`，不外包外部 LLM API。
