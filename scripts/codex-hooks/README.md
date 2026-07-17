# Codex Hooks（随 agent-memory 交付）

使用者安装记忆系统后，**一键安装 hooks**：

| 时机 | 行为 |
|------|------|
| **SessionStart** | 跑 `context`，**stdout 注入**会话；并写私有缓存 |
| **Stop** | **仅当**项目有完整 `.agent-memory/turn.json`（含非空 `goal` + `next_steps`）时 `checkpoint`；否则 **no-op**，**不**发明 Working |
| **UserPromptSubmit**（可选） | 用户话含「上次/之前/怎么做」等 → 再 `context` 并尝试注入 |

**不会**把对话全文写入 semantic；**不会**在无精华文件时用占位文案覆盖任务态。

---

## 一键安装

```bash
export AGENT_MEMORY_ROOT="${AGENT_MEMORY_ROOT:-$HOME/.agent-memory}"

# SessionStart + Stop（默认）
bash scripts/install_codex_hooks.sh

# 业务仓（推荐：写入 DIR/.codex/hooks.json，工作区更易触发）
bash scripts/install_codex_hooks.sh --project /path/to/repo

# 启用条件检索
bash scripts/install_codex_hooks.sh --with-prompt-search --project /path/to/repo

# 关闭条件检索（重装时）
bash scripts/install_codex_hooks.sh --no-prompt-search
```

默认重装策略：若已装过 `--with-prompt-search`，再次安装（不带 flag）**会保留**条件检索。  
安装器会尽量设置 `codex_hooks = true`；**无此开关时 hooks 可能完全不跑**。

卸载：

```bash
bash scripts/uninstall_codex_hooks.sh
bash scripts/uninstall_codex_hooks.sh --purge-cache   # 同时删 ~/.codex/memory-cache
```

安装器会：复制脚本、写入 CLI/记忆根指针、**合并** `hooks.json`（按**命令级**剥离旧 agent-memory hook，保留 Muxy 等）、备份并只保留最近 3 个 bak。

---

## 行为契约（与对抗审查对齐）

### SessionStart（读）

1. 从 **stdin JSON** 读 `cwd` / `source` 等  
2. `agent-memory context`  
3. **stdout**：JSON `hookSpecificOutput.additionalContext`（失败则退回纯文本）→ Codex 注入  
4. 缓存：`~/.codex/memory-cache/last-context.md`（目录 `700`，文件 `600`）

### Stop（写）

1. 从 stdin JSON 取 `cwd`  
2. 查找 `$cwd/.agent-memory/turn.json`  
3. **缺少或 goal/next_steps 为空 → 直接退出，不写记忆**  
4. 完整则先将 `turn.json` **claim** 为 `turn.processing-*.json`，再 `checkpoint`，成功 → `turn.done-*.json`（失败尽量还原 `turn.json`）；只保留最近 5 个 done

示例 `turn.json`：

```json
{
  "project_id": "my-app",
  "goal": "修复播放卡顿",
  "next_steps": "- 补测试\n- 验证复现",
  "decisions": "- 先查会话恢复"
}
```

### 双写说明

- Hook 只在有完整 `turn.json` 时写 Working。  
- Agent 也可自行 `checkpoint`；若两边都写，**后写覆盖**——建议项目协议约定：**优先写 turn.json 交给 Stop hook**，或仅 Agent 写、不装 Stop 写路径。  
- 业务仓 `AGENTS.md` 建议走**版本更新**加入 turn.json 约定，而非临时强改。

---

## 启用 Codex hooks

```toml
# ~/.codex/config.toml（配置名以本机文档为准）
[features]
codex_hooks = true
```

---

## 手动验收

```bash
# 注入冒烟（应在 stdout 看到 T0/Working 等）
echo '{}' | bash ~/.codex/hooks/agent-memory/session_start.sh | head -c 400; echo

# 无 turn.json → no-op
echo '{"cwd":"'"$PWD"'"}' | bash ~/.codex/hooks/agent-memory/stop_turn.sh
# stderr 应含 no-op: missing ...

# 有完整 turn → checkpoint
mkdir -p .agent-memory
printf '%s\n' '{"goal":"试钩子","next_steps":"- 验收","project_id":"demo"}' > .agent-memory/turn.json
echo '{"cwd":"'"$PWD"'"}' | bash ~/.codex/hooks/agent-memory/stop_turn.sh
agent-memory recent --n 3
```

---

## 安全

- 脚本最终 **exit 0**  
- 不写 semantic 全文  
- 缓存目录权限收敛  
- 无开发者机器硬编码路径（仅用 PATH / 安装器写入的 `*.path`）
