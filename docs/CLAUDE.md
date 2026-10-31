# Claude 桌面版：本机微信只读连接

本项目只面向 Claude Desktop，提供独立的本机微信只读入口。

已验证环境：Apple Silicon，微信 4.2.0（270348）的独立 Bundle ID 分身。启动时捕获方式取得了 21 个数据库密钥并通过认证，Claude 配置对应的 MCP 连接实际读取成功。这里新增的通用脚本经过人工数据库与协议测试；没有为发布再次重启真实微信。不能保证其他版本或签名状态适用。

## 1. 安装独立环境

```bash
git clone https://github.com/synologyer/wechat-mcp-macos.git
cd wechat-mcp-macos
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r requirements.txt
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

**先保存草稿，从菜单正常退出指定微信；暂时不要手动打开。** 调试器将启动指定应用，期间可能暂停、退出或要求手机确认登录。捕获器不执行 sudo、重新签名、关闭系统保护或自动退出已有进程。权限不足就停止排查。

```bash
# 先确认 ~/.wechat-mcp 已由第 2 步创建；输出文件必须不存在。
PYTHONPATH="$(/usr/bin/lldb -P)" /usr/bin/python3 scripts/capture_launch_keys.py \
  --app '/Applications/工作.app' \
  --db-dir '/实际路径/db_storage' \
  --out "$HOME/.wechat-mcp/captured-keys.json" \
  --acknowledge-debug-launch
```

默认最多捕获 150 秒。仅原生 ARM64；要求有 Xcode Command Line Tools 及可用 LLDB。脚本拒绝选定应用已运行的情况，只观察自己启动的进程。正常结束时清除断点并尝试解除调试，不主动调用终止操作；异常仍可能导致微信退出。界面出现登录确认时由本人完成，不要手动再开一个实例。启动失败不代表数据库损坏，也不代表必须修改签名。

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
- 移动项目后，重新创建虚拟环境并再次运行配置脚本；复制虚拟环境通常不能修复其中的绝对路径。

技术参考：[启动时捕获与逐库认证的公开方案](https://gist.github.com/acmerfight/0a01249ef72970d07a2603dbb629e80f)。本仓库的通用捕获脚本单独实现，不引入该 Gist 的整套工具或自动重签流程。

## 日常使用与常见问题

### 已经配置完成，下次还要提取密钥吗？

通常不需要。先在 Claude 询问连接状态，再读取已知测试会话。微信普通重启不代表密钥失效。只有验证失败、账户迁移或出现新分库缺钥时才重新排查，不要每次重启微信都执行捕获。

### Claude 看不到连接

确认使用的是 Claude 桌面 App；完全退出后重新打开，而不是只关闭窗口。检查桌面配置中的 `command` 指向当前项目 `backend/.venv/bin/python`，`args` 指向当前项目 `claude_wechat_readonly.py`。检查环境是否安装了 `requirements.txt`，连接状态是否报配置路径缺失。

### 状态显示 0 个密钥

第 2 步只配置目录，不获取密钥。完成第 3 步捕获、验证、导入后重启 Claude。密钥文件是本机文件，不要发给 AI 或上传 GitHub。

### 提示所选微信已运行

从微信菜单正常退出，等主进程结束后重试。捕获期间不要手动再次打开同一个 App，避免新实例因重复运行而退出。

### 捕获返回 3，或者只覆盖部分数据库

检查输出中的 `verified` 与 `total`；部分密钥已保存不代表全部聊天可读。先完成手机登录确认、检查账户路径和版本，不要删除认证检查或通过重新签名强行重试。失败时没有经过验证的库就无法读取。

### 群名重名、找不到会话或无消息

先列出群聊/最近会话，使用精确会话 ID 查询。只能读取本机已有记录，不会从手机或服务器补齐全部历史。图片和语音可能只显示类型占位，不等于附件已解析。

### 按群名整理后，文件在哪里？

这个连接只把查询结果返回给 Claude，不自动建立归档文件。需要写入文件时，要另行提供 Claude 的文件访问能力和保存位置，或手动保存输出。也没有默认定时任务。

### 更换账户

用新账户的准确 `db_storage` 路径运行配置脚本，显式添加 `--replace-account --apply`。旧密钥会私密备份，不套用到新账户；新账户需单独验证并导入密钥。然后重启 Claude。

### 移动项目

在新位置重建 `backend/.venv`、安装 `requirements.txt`，用同一账户路径重新运行配置脚本并重启 Claude。无需移动微信数据库；已有有效密钥仍留在 `~/.wechat-mcp/`。复制虚拟环境可能留下旧绝对路径，不应假设可直接使用。
