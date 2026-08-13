#!/usr/bin/env bash
# 一键群聊总结包装（纯 agent 执行）：跳过耗时的 check_env 与运行前清理，只跑必要步骤。
#
# 设计：分析(写 summary.json)由 agent 完成，本脚本只负责把其余冗余步骤去掉。
#   summarize.sh prepare --chat <群名/联系人/wxid> [日期参数]
#       -> 仅做 查库+压缩+填模板（约 2~4s），输出 prompt.txt
#       -> agent 读取 prompt.txt 写出 summary.json
#   summarize.sh render <summary.json> [output.png]
#       -> 校验并渲染长图
#
# 日期参数同 chat-summary-workflow.sh：
#   --today | --yesterday | --date YYYY-MM-DD | --last 7d | --hours 24
#   --start ... --end ... | --day-start HH:MM

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WF="$ROOT_DIR/scripts/chat-summary-workflow.sh"

[[ -x "$WF" ]] || { echo "找不到工作流脚本：$WF" >&2; exit 1; }

cmd="${1:-prepare}"
shift || true

case "$cmd" in
  prepare)
    # 关键加速：--skip-cleanup 避免每次清理扫描；不调用 check_env
    exec "$WF" prepare --skip-cleanup "$@"
    ;;

  render)
    [[ $# -ge 1 ]] || { echo "缺少 summary.json 路径" >&2; exit 1; }
    exec "$WF" render "$@"
    ;;

  *)
    echo "未知子命令：$cmd（支持 prepare / render）" >&2
    exit 1
    ;;
esac
