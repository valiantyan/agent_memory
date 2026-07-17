# agent-memory · 个人 Agent 外挂记忆系统

[![CI](https://github.com/valiantyan/agent_memory/actions/workflows/ci.yml/badge.svg)](https://github.com/valiantyan/agent_memory/actions/workflows/ci.yml)

**纯文件、本机、跨 Agent 共享**的个人记忆库。通过统一 CLI `agent-memory` 读写，让 Cursor / Codex / Claude Code / Grok 等工具在**同一数据根**上接续任务、记住偏好与项目约定，而不绑定任何厂商私有 Memory API。

| 项 | 内容 |
|----|------|
| 当前包版本 | **2.0.4** |
| 数据 schema | **1.0.0**（文件格式兼容 1.x） |
| 最新发布说明 | [`docs/RELEASE_v2.0.4.md`](docs/RELEASE_v2.0.4.md) |
| 2.0.0 基线说明 | [`docs/RELEASE_v2.0.md`](docs/RELEASE_v2.0.md) |
| 需求 | [`REQUIREMENTS.md`](REQUIREMENTS.md) v1.2 Frozen |
| 设计 | [`DESIGN.md`](DESIGN.md) v0.3 Frozen |
| 协议（Agent 行为契约） | [`PROTOCOL.md`](PROTOCOL.md) |
| **使用手册（中文）** | [`docs/使用手册.md`](docs/使用手册.md) |
| **接入指南（中文）** | [`docs/接入指南.md`](docs/接入指南.md) |
| 仓库 | https://github.com/valiantyan/agent_memory |

---

## 目录

1. [要解决什么问题](#1-要解决什么问题)
2. [设计总览（第一性原理）](#2-设计总览第一性原理)
3. [核心概念](#3-核心概念)
4. [数据布局](#4-数据布局)
5. [实现架构](#5-实现架构)
6. [命令一览（FA-2）](#6-命令一览fa-2)
7. [安装与快速开始](#7-安装与快速开始)
8. [符合性三等级](#8-符合性三等级)
9. [测试与验收](#9-测试与验收)
10. [版本与路线图](#10-版本与路线图)
11. [文档索引](#11-文档索引)
12. [许可证与贡献](#12-许可证与贡献)

---

## 1. 要解决什么问题

| 痛点 | 本系统做法 |
|------|------------|
| 换窗口 / 换 Agent 就失忆 | `working` + `handoff` + `context` 接续任务态 |
| 偏好与约定每会话重讲 | `remember`（slot 唯一 current）+ T0 硬约束 |
| 项目 A 约定污染项目 B | `scope=project:<id>` + `project-detect` 写门禁 |
| 记忆变成垃圾场 | INDEX 分层检索、预算截断、staging 候选、forget/reject |
| 绑定某一家内置 memory | **纯文件 + 通用 CLI**，任意能跑 shell 的 Agent 都可接 |

**一句话目标：** 在本机构建一套**人可读、可拷贝、可审计**的记忆根目录；多个 Agent 按同一协议读写。

**明确非目标（v1）：** Git 同步产品化、跨机器自动续上、向量库作真相源、MCP、多租户 ACL、常驻 daemon、全文聊天归档、强制所有 Agent 开箱遵守。

---

## 2. 设计总览（第一性原理）

记忆只保证四件事：

| 原理 | 含义 | 本系统落点 |
|------|------|------------|
| **P1 状态连续** | 任务还在哪 | Working / work-items / handoff / `turn`→checkpoint |
| **P2 规则稳定** | 偏好与约定可复用 | T0、`remember`、global/project semantic |
| **P3 边界正确** | 不串项目、不把猜测当真理 | scope 隔离、**cwd 项目作用域 context（2.0.4）**、写门禁 |
| **P4 可控体积** | 省 token、可清洗 | INDEX L0、top_k、预算、staging、gc |

### 2.1 时间尺度分层

```text
短 ──────────────────────────────────────────────────► 长
 Working          Episode           Semantic(项目)      Semantic(全局)/T0
 当前任务态         会话情节摘要        项目约定             跨项目偏好/硬约束
 checkpoint 覆盖    session-end 追加    project scope       global / me.T0.md
```

### 2.2 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 真相源 | **仅文件系统** | 可移植、可人工改、无 DB 绑定 |
| 接口 | **CLI 子命令**（v1 FA-2 + v2 `turn`/`event`/`work`） | 核心可测；v2 扩展写入路径 |
| 检索 | **INDEX 表 L0 → 再读正文** | 省长度；非向量依赖 |
| 偏好唯一 | **同 scope + 同 slot 仅一份 active** | 新写 supersede 旧写 → `history/` |
| 候选 | **staging 默认不进 search** | 防止噪声当真理 |
| 程序记忆 | **禁止 extract 自动升 active** | 高影响流程须确认 |
| 并发 | INDEX **原子写**；多任务用 **work-items**；focus **按项目** | 同项目 dual session 靠 session_id；跨项目靠 cwd |
| 到期 | **惰性**（挂在常用命令上），无 daemon | 适配「用户直接关窗」习惯 |
| 责任 | **L-Core / L-Protocol / L-Ref 三等级** | 模型漏调 checkpoint ≠ CLI bug |

### 2.3 读路径 vs 写路径

```text
开聊读（hooks SessionStart / UserPrompt）：
  context --cwd <workspace>
    → T0
    → 本项目 Working(focus) + work items + open intents + events
    → Semantic(INDEX 命中再读详情)

会话中写：
  event（L0 审计，hooks 自动）/ intent-draft（按 session）
  turn → meta/pending-turn/ → Stop → checkpoint + work item
  remember（正式语义）/ handoff（换窗）

收工写：
  session-end → episode
  extract → staging → promote / reject
  forget / gc
```

完整 Agent 义务见 [`PROTOCOL.md`](PROTOCOL.md) 与 [`docs/接入指南.md`](docs/接入指南.md)。

---

## 3. 核心概念

| 术语 | 说明 |
|------|------|
| **记忆根** | `AGENT_MEMORY_ROOT` 指向的目录；默认 `~/.agent-memory` |
| **schema_version** | 根目录版本文件；不兼容则写失败 |
| **T0** | `profile/me.T0.md`：硬约束与极短协作风格，**每次 context 注入** |
| **Working / focus** | 任务态：全局镜像 `working/current.md` + **per-project** `working/focus/<project>.json`（2.0.4） |
| **Work item** | 可并行任务条 `working/items/wi_*.md`；不互抹 |
| **Handoff** | 交接快照，便于换 Agent / 换窗 |
| **Episode** | 情节摘要（**不是**全文聊天） |
| **Semantic active** | 默认可检索的正式语义记忆 |
| **Intent-draft** | 用户任务意图暂存（**按 session 分文件**，2.0.3+） |
| **Event (L0)** | `meta/events.jsonl` 审计日志（含 session/project） |
| **Staging** | 候选；默认不进 search/context 主结果 |
| **Slot** | 偏好/事实槽位键；同 scope 下 active 唯一 |
| **INDEX** | `INDEX.semantic.md` / `INDEX.episodic.md` 分表 L0 → 再读正文 |
| **Checkpoint / turn** | `turn` 写 pending；Stop→checkpoint 晋升 Working/item |
| **项目识别** | `project-detect` / `.agent-memory-project`；context 优先 **cwd**（2.0.4） |

---

## 4. 数据布局

`agent-memory init` 后记忆根大致为：

```text
$AGENT_MEMORY_ROOT/
  schema_version
  PROTOCOL.md
  profile/me.T0.md
  working/
    current.md                 # 全局 last focus 镜像（兼容）
    focus.json                 # 全局 last-active 指针
    focus/<project_id>.json    # 2.0.4 每项目 focus
    items/wi_*.md              # 2.0.2+ 并行任务条
    handoff-*.md
  scopes/global|projects/<id>/semantic/
  staging/candidates/
  history/semantic/
  episodes/
  INDEX.semantic.md / INDEX.episodic.md
  meta/
    recent.jsonl
    events.jsonl               # 2.0.1+ L0 审计
    intent-draft/              # 2.0.3+ <project>__sess_<id>.json
    pending-turn/              # 2.0.0+ turn → Stop 消费
    quotas.md / rejected.jsonl
```

**一条记忆一个 Markdown 文件**（含 YAML front matter）。人可以直接打开编辑；改完建议 `reindex` + `doctor`。

语义 front matter 字段概要：`id`、`type`、`content_kind`、`status`、`scope`、`slot`、`one_liner`、`importance`、`source` 等。详见 [`DESIGN.md`](DESIGN.md)。

---

## 5. 实现架构

### 5.1 仓库结构

```text
agent_memory/                 # 安装包（下划线名）
  cli.py                      # argparse 入口；全局 --root 可置于子命令前后
  config.py / errors.py / util.py
  frontmatter.py / io_atomic.py
  index.py                    # INDEX 读写、doctor、reindex
  working.py / recent.py / expiry.py
  project_detect.py / write_gate.py / security.py
  extract_rules.py / templates.py
  commands/                   # 各 FA-2 子命令实现
tests/                        # pytest（无 LLM）
docs/                         # 中文使用/接入 + 签字与参考
scripts/demo_ac1.sh           # AC-1 L-Core 交接演示
REQUIREMENTS.md / DESIGN.md / PROTOCOL.md
pyproject.toml                # 入口：agent-memory = agent_memory.cli:main
```

### 5.2 模块职责

| 模块 | 职责 |
|------|------|
| `cli.py` | 解析参数、`hoist_global_options`（兼容 `context --root PATH`）、分发命令 |
| `index.py` | 解析/原子写 INDEX；doctor 一致性检查 |
| `io_atomic.py` | 临时文件 + rename，避免 INDEX 写残 |
| `write_gate.py` | 项目写门禁（low confidence 禁 project semantic） |
| `security.py` | 密钥/PEM 等启发式拦截；T0 预算 |
| `expiry.py` | 惰性观察期转正/丢弃（FM-4 挂点） |
| `commands/*` | 单命令：init / context / remember / … |

### 5.3 关键写入顺序（多文件变更）

对 `remember`、`forget`、`session-end` 等：

1. 写/改正文  
2. 原子更新 INDEX  
3. 尽力追加 `meta/recent.jsonl`（失败不推翻主结果）

同 slot supersede：**新 id 正文 → 旧文件移 history → INDEX 替换 → recent**。

### 5.4 CLI 行为要点（1.0.1）

- **`--root` / `-q` / `--json`**：可写在子命令**前或后**（方便 Agent 乱序传参）。  
- **`recent`：只读**；磁盘裁剪由 `gc` 负责（沙箱 Agent 可审计）。  
- **默认根**：`$AGENT_MEMORY_ROOT` 或 `~/.agent-memory`。  
- **演示脚本** `demo_ac1.sh` 使用独立临时根，**不会**误写你环境里的生产记忆库。

### 5.5 技术栈

- Python **≥ 3.10**  
- 运行依赖：`PyYAML`  
- 开发依赖：`pytest`  
- 无数据库、无网络服务、无向量库

---

## 6. 命令一览

| 命令 | 用途 |
|------|------|
| `init` / `doctor` / `reindex` | 建库、健康检查、重建 INDEX |
| `context` | 开聊打包：T0 + **本项目** Working/items/intents + Semantic（`--cwd` / `--project`） |
| `search` / `get` | INDEX 检索 / 按 id 取正文 |
| `turn` | **v2** 写 `meta/pending-turn/`（供 Codex Stop→checkpoint） |
| `checkpoint` | 更新 Working + upsert work-item + per-project focus |
| `event` | **v2.0.1+** L0 审计；任务句可 intent-draft + auto item |
| `work` | **v2.0.2+** `list` / `focus` / `upsert` 并行任务条 |
| `handoff` / `session-end` | 交接快照 / 情节摘要 |
| `remember` / `forget` / `extract` / `promote` / `reject` | 正式语义与候选生命周期 |
| `recent` / `gc` | 最近写入（只读）/ 清理 |
| `project-detect` | 项目 id + confidence |

参数与示例见 **[使用手册](docs/使用手册.md)**。

---

## 7. 安装与快速开始

### 7.1 安装

```bash
git clone https://github.com/valiantyan/agent_memory.git
cd agent_memory
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
agent-memory --version      # 期望：agent-memory 2.0.4 (schema 1.0.0)
```

### 7.2 初始化记忆库

```bash
export AGENT_MEMORY_ROOT="$HOME/.agent-memory"   # 可改成任意目录
agent-memory init
agent-memory doctor
```

建议写入 shell 配置（如 `~/.zshrc`）：

```bash
export AGENT_MEMORY_ROOT="$HOME/.agent-memory"
export PATH="/path/to/agent_memory/.venv/bin:$PATH"
```

### 7.3 最小闭环

```bash
# 开聊（按仓库目录作用域，2.0.4）
agent-memory context --cwd /path/to/app --query "当前任务关键词"

# 固定偏好
agent-memory remember --slot coding --content "只改任务相关文件；禁止顺手重构"

# 回合精华（Codex 推荐；Stop 再晋升）
agent-memory turn --goal "修复播放卡顿" --next-steps $'- 复现\n- 定位' --cwd /path/to/app

# 或直接任务态
agent-memory checkpoint --goal "修复播放卡顿" --next-steps $'- 复现\n- 定位' --project-id my-app

# 并行任务
agent-memory work list --project-id my-app
agent-memory work focus --id wi_...

# 换工具 / 上下文将满
agent-memory handoff --goal "修复播放卡顿" --next-steps "- 继续排查"
```

### 7.4 Codex Hooks（推荐：项目触发，不改业务 AGENTS）

```bash
export AGENT_MEMORY_ROOT="${AGENT_MEMORY_ROOT:-$HOME/.agent-memory}"
# 推荐：只挂业务仓 hooks，并剥离全局 agent-memory 触发（防双写）
bash scripts/install_codex_hooks.sh --project /path/to/app
# 仅本机全局触发（无 --project）：bash scripts/install_codex_hooks.sh
# 强制保留全局触发：加 --global-hooks（不推荐与 --project 同开）
```

| 效果 | 说明 |
|------|------|
| SessionStart | `context --cwd` + **v2.0.4 协议**（**本项目** Working/items） |
| UserPrompt | L0 `event` + session intent + 启发式 context |
| Stop | 消费 `meta/pending-turn/` → checkpoint；无则 no-op / interrupt intent |
| 脚本位置 | `~/.codex/hooks/agent-memory/`（实现）；触发在**项目** `.codex/hooks.json` |
| 数据边界 | 只写 `AGENT_MEMORY_ROOT`；业务仓最多 `.agent-memory-project` + hooks 指针 |
| 换电脑 | 整夹同步记忆根 + 重装 CLI/hooks |

说明：[`docs/RELEASE_v2.0.4.md`](docs/RELEASE_v2.0.4.md) · [`scripts/codex-hooks/README.md`](scripts/codex-hooks/README.md)。

更完整的日常流程与命令表：**[使用手册](docs/使用手册.md)**。  
接到 Cursor/Codex 等：**[接入指南](docs/接入指南.md)**。

---

## 8. 符合性三等级

| 等级 | 含义 | 保证方 | 失败怎么算 |
|------|------|--------|------------|
| **L-Core** | CLI 与文件规则的确定行为 | 本仓库 pytest / 脚本 | 实现未完成 |
| **L-Protocol** | Agent 何时读写、不编造 | 接入规则 + 模型 | **不算** CLI bug |
| **L-Ref** | 参考粘贴块 + 演示剧本 | `docs/接入指南.md` 等 | 先修文档/接入 |

**承诺边界：** 已执行 `turn`→Stop/`checkpoint` / `handoff` / `session-end` 的状态保证可恢复；仅 event/intent 有审计痕迹但未必晋升 Working；杀进程且未写盘的进度允许丢失。

---

## 9. 测试与验收

```bash
pip install -e ".[dev]"
pytest -q
bash scripts/demo_ac1.sh
```

- 聚合验收：`tests/test_ac_signoff.py`  
- 安全 / INDEX 原子性等专项测试见 `tests/`  
- 签字清单：`docs/SIGNOFF.md`  
- CI：`.github/workflows/ci.yml`（pytest + demo）

---

## 10. 版本与路线图

| 版本 | 说明 |
|------|------|
| 1.0.0 | FA-2 齐全、AC 主路径、PROTOCOL / 参考集成 |
| **1.0.1** | `recent` 只读；`--root` 子命令前后均可；demo 不误用生产 `AGENT_MEMORY_ROOT` |
| **2.0.0** | 自包含接入；`turn` + `meta/pending-turn/`；数据单根；不依赖业务 AGENTS |
| **2.0.1** | L0 `event` + intent-draft；UserPrompt 默认启发式检索；Stop 无 turn 时 interrupt intent |
| **2.0.2** | 项目 hooks 默认剥离全局触发；multi work-item + focus；当前任务优先级 |
| **2.0.3** | 按 session 的 intent；event/item/turn 带 session_id；UserPrompt 自动 draft item |
| **2.0.4** | context/hooks 按 cwd 项目作用域；per-project focus；禁止跨项目 Working 串味 |

**可能的后续（非承诺）：** 查询句不建 auto-item、MCP、Git 托管说明、更强 INDEX/向量、时间点 rollback。

---

## 11. 文档索引

| 文档 | 语言 | 内容 |
|------|------|------|
| [README.md](README.md) | 中文 | 本页：问题、设计、实现、安装 |
| [docs/使用手册.md](docs/使用手册.md) | 中文 | 安装配置、命令详解、日常配方、排错 |
| [docs/接入指南.md](docs/接入指南.md) | 中文 | 接入 Codex/Cursor 等、粘贴块、沙箱、项目标记 |
| [PROTOCOL.md](PROTOCOL.md) | 英文 | Agent 行为契约（init 会拷入记忆根） |
| [REQUIREMENTS.md](REQUIREMENTS.md) | 中文为主 | 需求 Frozen v1.2 |
| [DESIGN.md](DESIGN.md) | 英文 | 详细设计 Frozen v0.3（v2 演进见 RELEASE + 文末附录） |
| [docs/RELEASE_v2.0.4.md](docs/RELEASE_v2.0.4.md) | 中文 | **当前** 2.0.4 发布说明 |
| [docs/demo/AC1_script.md](docs/demo/AC1_script.md) | 英文 | 换 Agent 接续演示剧本 |
| [docs/SIGNOFF.md](docs/SIGNOFF.md) | 英文 | 签字检查表 |

---

## 12. 许可证与贡献

- 个人 / 学习 / 二次修改请自担数据安全责任：**勿把密钥写入记忆库**。  
- 改需求请先升 `REQUIREMENTS.md` 版本，勿在 Frozen 文档上静默扩 scope。  
- Issue / PR 欢迎围绕：文档、测试、L-Core 缺陷、接入体验。

---

**维护提示：** 记忆**数据**与**本仓库代码**分离。数据在你本机的 `AGENT_MEMORY_ROOT`；请勿把含隐私的记忆目录提交到 Git。
