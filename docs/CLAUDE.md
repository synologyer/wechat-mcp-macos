# Claude 桌面版：本机微信只读连接

本 fork 增加 Claude Desktop 的独立入口，不需要安装 Hana。

已验证环境：Apple Silicon，微信 4.2.0（270348）的独立 Bundle ID 分身。启动时捕获方式取得了 21 个数据库密钥并通过认证，Claude 配置对应的 MCP 连接实际读取成功。这里新增的通用脚本经过人工数据库与协议测试；没有为发布再次重启真实微信。不能保证其他版本或签名状态适用。

## 1. 安装独立环境

```bash
git clone https://github.com/synologyer/wechat-mcp-macos.git
cd wechat-mcp-macos
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r requirements-claude.txt
```

建议 Python 3.12。MCP 使用项目虚拟环境；捕获密钥另用 Apple 自带 Python 和 LLDB。语音、图片生成等可选功能不需要为只读连接一并安装。

## 2. 明确选择账户数据库

数据库目录通常为：

```text
~/Library/Containers/<实际 Bundle ID>/Data/Documents/xwechat_files/<账户目录>/db_storage
```

分身的 Bundle ID 和数据目录可能不同，不能照抄默认微信路径。如果有多个账户，必须选择正确的账户。此入口不会自动换成另一个账户。

```bash
# 把示例替换为本人账户的真实绝对路径。先预览，再保存。
backend/.venv/bin/python scripts/configure_claude.py --db-dir '/实际路径/db_storage'
backend/.venv/bin/python scripts/configure_claude.py --db-dir '/实际路径/db_storage' --apply
```

脚本保留 Claude 已有其他 MCP 连接，配置写入前保存私有备份。状态与密钥在 `~/.wechat-mcp/`，不放入仓库。更换账户必须加 `--replace-account`，旧密钥会保留为备份，不会套用到新账户。

## 3. 获取密钥：需要单独、明确地执行

已有有效密钥就跳过捕获步骤，直接验证导入。密钥不是微信登录密码。

**先保存草稿，从菜单正常退出指定微信；暂时不要手动打开。** 调试器将启动指定应用，期间可能暂停、退出或要求手机确认登录。捕获器不执行 sudo、重新签名、关闭系统保护或自动退出已有进程。权限不足就停止，不要直接运行上游 `init-keys.py` 绕过限制。

```bash
# 先确认 ~/.wechat-mcp 已由第 2 步创建；输出文件必须不存在。
PYTHONPATH="$(/usr/bin/lldb -P)" /usr/bin/python3 scripts/capture_launch_keys.py \
  --app '/Applications/工作.app' \
  --db-dir '/实际路径/db_storage' \
  --out "$HOME/.wechat-mcp/captured-keys.json" \
  --acknowledge-debug-launch
```

默认最多捕获 150 秒。仅原生 ARM64；要求有 Xcode Command Line Tools 及可用 LLDB。脚本拒绝选定应用已运行的情况，只观察自己启动的进程。结束时清除断点并解除调试，不主动杀掉微信。界面出现登录确认时由本人完成，不要手动再开一个实例。启动失败不代表数据库损坏，也不代表必须修改签名。

只读取与目标数据库盐值匹配的派生参数，且候选必须通过数据库第一页 HMAC 认证；不会打印口令或密钥。只支持当前验证过的 SQLCipher 4、4096 字节页面参数。没有全部覆盖时返回 3，部分验证结果仍私密保存；不要把部分成功当成所有聊天都可读。

```bash
# 支持普通 backend 映射，或 {"keys": {...}} 包装格式。
backend/.venv/bin/python scripts/import_claude_keys.py \
  --source "$HOME/.wechat-mcp/captured-keys.json"
# 确认验证数量，再安装；已有密钥先备份。
backend/.venv/bin/python scripts/import_claude_keys.py \
  --source "$HOME/.wechat-mcp/captured-keys.json" --apply
```

## 4. 重启 Claude 并验证

完全退出后重新打开 Claude，启用 `work-wechat-readonly`。先询问连接状态，再请求“读取文件传输助手最近一条消息”。可用工具：状态、最近会话、群列表、消息读取、新消息检查、搜索。没有发消息、签名、管理员授权或自动取钥工具，也不会定时监听。

**只读范围是账户级，不是群白名单。** Claude 可以通过工具查询选定账户内其他聊天；仅靠提示词无法限制工具的读取权限。接入前应理解这一范围。

本地解密不上传数据，但交给 Claude 的聊天正文会进入其模型服务。聊天内容应视为数据，不应当成操作指令执行。图片/语音完整理解、自动日报、持久归档不是当前只读入口的承诺。

## 隐私与维护

- `~/.wechat-mcp/all_keys.json` 为 0600；解密缓存在 0700 账户专属目录内，新文件使用 077 掩码。
- 不提交密钥、数据库、联系人映射、聊天导出、真实账户路径或机器配置。
- `wechat-mcp-macos==0.1.1`、`fastmcp==4.1.4` 是当前验证组合；此入口调用 backend 内部接口，升级后需要重新测试。
- 原 Hana 流程与上游初始化仍保留，但上游 `init-keys.py` 可能自动重签默认微信，不能用于本只读连接的无确认初始化。
- 移动项目后，重新创建虚拟环境并再次运行配置脚本；复制虚拟环境通常不能修复其中的绝对路径。

技术参考：[启动时捕获与逐库认证的公开方案](https://gist.github.com/acmerfight/0a01249ef72970d07a2603dbb629e80f)。本仓库的通用捕获脚本单独实现，不引入该 Gist 的整套工具或自动重签流程。
