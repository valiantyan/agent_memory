# agent-memory v2.0.1 发布说明

| 项 | 内容 |
|----|------|
| 版本 | **2.0.1**（schema 仍为 **1.0.0**） |
| 日期 | 2026-07-17 |
| 相对 | 2.0.0 |

## 解决什么（kmp-music / Codex 验收缺口）

2.0.0 读路径（SessionStart）可用，但：

1. 用户发出任务（如 BUG）后若 Agent 未 `turn`，**零痕迹**  
2. 默认未按**当前用户输入**检索  
3. Stop 无 pending 时完全静默，中断与「从未发生」不可区分  

## 2.0.1 行为

| 层 | 行为 |
|----|------|
| **L0 事件** | `meta/events.jsonl`；`agent-memory event`；UserPrompt **总是**记一条（截断/密钥脱敏） |
| **Intent draft** | 任务类用户输入 → `meta/intent-draft/<project>.json`（**不是** Working/Semantic） |
| **检索** | UserPrompt 启发式：任务词/长度 ≥48 → `context --query <用户输入>` 注入 |
| **Stop 无 turn** | 记 `stop_no_turn` + **interrupt** intent；**仍不 invent Working** |
| **Stop 有 turn** | 原 claim→checkpoint；清 intent；记 `stop_ok` |
| **context** | 增加 `## Open intent` + `## Recent events` |
| **安装默认** | UserPrompt hook **默认开启** |

## 非目标（刻意不做）

- 用户原文直写 `working/current.md` 或 semantic  
- Stop 从 transcript invent goal  
- 强制人工审核每条记忆  

## 升级

```bash
cd agent_memory
pip install -e ".[dev]"
export AGENT_MEMORY_ROOT=...
bash scripts/install_codex_hooks.sh --project /path/to/kmp-music
agent-memory doctor
```

## 验收建议

1. Codex 发 BUG 句 → `meta/events.jsonl` 有记录 + intent-draft open  
2. 不 turn 就 Stop → intent **interrupted**，Working **不变**  
3. `agent-memory turn` + Stop → Working 更新，intent 清除  
4. 新会话 context 能看到 Open intent 或更新后的 Working  
