# agent-memory v2.0.0 发布说明

| 项 | 内容 |
|----|------|
| 版本 | **2.0.0**（包版本；文件 schema 仍为 **1.0.0**） |
| 日期 | 2026-07-17 |
| 相对 | 1.0.1 |

## 为什么要有 v2

1. **接入必须自包含**：别人只安装记忆系统即可用，**不能**依赖我们去改业务仓 `AGENTS.md`。  
2. **数据必须单根**：所有持久记忆只在 `AGENT_MEMORY_ROOT`；换电脑 = 同步该目录 + 安装 CLI。  
3. **不当垃圾桶**：回合精华进 `meta/pending-turn/`，由 Stop hook 升为 Working；无精华则 no-op。

## 破坏性变更（接入层）

| 旧（1.x 联调路径） | 新（2.0） |
|--------------------|-----------|
| 业务仓 `.agent-memory/turn.json` | **`$AGENT_MEMORY_ROOT/meta/pending-turn/<project>.json`** |
| 靠改业务 `AGENTS.md` 写协议 | **SessionStart 注入 + `~/.codex` 用户规则**；业务 AGENTS **可选** |
| 仅全局 hooks | 全局 hooks + 可选 `--project` 项目 hooks 指针 |

**不破坏**：已有 semantic / working / episode 文件格式与 schema 1.0.0。

## 新能力

| 项 | 说明 |
|----|------|
| `agent-memory turn` | 写入数据根 pending turn（供 Stop 消费） |
| Stop hook | 只读数据根 pending-turn；不扫业务仓目录 |
| SessionStart | 注入 context + v2 协议短文 |
| `install_codex_hooks.sh` | 启用 `codex_hooks`、用户规则、可选 `--project` |

## 安装（任意机器）

```bash
git clone https://github.com/valiantyan/agent_memory.git
cd agent_memory
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

export AGENT_MEMORY_ROOT="$HOME/.agent-memory"   # 或你的同步目录
agent-memory init
bash scripts/install_codex_hooks.sh
# 可选：bash scripts/install_codex_hooks.sh --project /path/to/your-app
```

### 换电脑

1. 整夹复制 `AGENT_MEMORY_ROOT`  
2. 新机安装 CLI + `export AGENT_MEMORY_ROOT=...`  
3. `bash scripts/install_codex_hooks.sh`  
4. `agent-memory doctor` → `context`

**不要**指望业务 git 仓库带上记忆数据。

### 业务项目需要什么（可选）

| 文件 | 必须？ |
|------|--------|
| `.agent-memory-project`（一行 id） | 可选，利于 project-detect |
| 改 `AGENTS.md` | **不必** |
| 业务仓数据目录 | **不要**放正式记忆 |

## Agent 每轮（由注入规则提示）

```bash
agent-memory context --query "..."
# … 工作 …
agent-memory turn --goal "..." --next-steps "- ..." --cwd .
# Stop hook → checkpoint
```

## 从 1.x 迁移

1. 升级包到 2.0.0，重跑 `install_codex_hooks.sh`  
2. 停止依赖业务仓 `.agent-memory/turn.json`  
3. 改用 `agent-memory turn`  
4. 业务仓 AGENTS 记忆段可删可留（仅文档，非引擎依赖）

## 测试

```bash
pytest -q
bash scripts/demo_ac1.sh
```
