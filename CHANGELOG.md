# 更新日志

## 2026-08-13
- **fix** 修复 `skill/scripts/check_env.sh` 自检时通过 `echo "$0" | bash` 把整个脚本再执行一遍来统计对勾的 bug，消除每次环境检查耗时翻倍（原 1~2 分钟）的问题。
- **perf** 新增 `scripts/summarize.sh` 一键包装，自动跳过 `check_env` 与运行前清理；`prepare` 步骤由 1~2 分钟降至约 4 秒。
- **docs** 明确总结流程保持纯 agent 执行：`prepare` → agent 读取 `prompt.txt` 写出 `summary.json` → `render`，不外包外部 LLM API。
