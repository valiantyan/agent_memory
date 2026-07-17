# agent-memory · 个人 Agent 外挂记忆系统

[![CI](https://github.com/valiantyan/agent_memory/actions/workflows/ci.yml/badge.svg)](https://github.com/valiantyan/agent_memory/actions/workflows/ci.yml)

**纯文件、本机、跨 Agent 共享**的个人记忆库。通过统一 CLI `agent-memory` 读写，让 Cursor / Codex / Claude Code / Grok 等工具在**同一数据根**上接续任务、记住偏好与项目约定，而不绑定任何厂商私有 Memory API。

| 项 | 内容 |
|----|------|
| 当前包版本 | **1.0.1** |
| 数据 schema | **1.0.0** |
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
| **P1 状态连续** | 任务还在哪 | `working/current.md`、`handoff-*`、`checkpoint` |
| **P2 规则稳定** | 偏好与约定可复用 | T0、`remember`、global/project semantic |
| **P3 边界正确** | 不串项目、不把猜测当真理 | scope 隔离、写门禁、禁 `user_explicit` 推断 |
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
| 接口 | **CLI 穷尽列表 FA-2（17 条）** | 不擅自加 P0 命令；Agent 行为可测边界清晰 |
| 检索 | **INDEX 表 L0 → 再读正文** | 省长度；非向量依赖 |
| 偏好唯一 | **同 scope + 同 slot 仅一份 active** | 新写 supersede 旧写 → `history/` |
| 候选 | **staging 默认不进 search** | 防止噪声当真理 |
| 程序记忆 | **禁止 extract 自动升 active** | 高影响流程须确认 |
| 并发 | INDEX **原子写**；**仅一份活跃 working** | 双 Agent 同改 working 可能互盖（已文档声明） |
| 到期 | **惰性**（挂在常用命令上），无 daemon | 适配「用户直接关窗」习惯 |
| 责任 | **L-Core / L-Protocol / L-Ref 三等级** | 模型漏调 checkpoint ≠ CLI bug |

### 2.3 读路径 vs 写路径

```text
开聊读：
  context → T0 + Working + Semantic(命中详情)
         或 search / get

会话中写：
  checkpoint（任务态） / remember（正式语义）
  里程碑 → handoff

收工写：
  session-end → episode
  extract → staging 候选
  promote / reject / forget / gc
```

完整 Agent 义务见 [`PROTOCOL.md`](PROTOCOL.md) 与 [`docs/接入指南.md`](docs/接入指南.md)。

---

## 3. 核心概念

| 术语 | 说明 |
|------|------|
| **记忆根** | `AGENT_MEMORY_ROOT` 指向的目录；默认 `~/.agent-memory` |
| **schema_version** | 根目录版本文件；不兼容则写失败 |
| **T0** | `profile/me.T0.md`：硬约束与极短协作风格，**每次 context 注入** |
| **Working** | 唯一活跃任务态 `working/current.md` |
| **Handoff** | 交接快照，便于换 Agent 接续 |
| **Episode** | 情节摘要（**不是**全文聊天） |
| **Semantic active** | 默认可检索的正式语义记忆 |
| **Staging** | 候选；默认不进 search/context 主结果 |
| **Slot** | 偏好/事实槽位键；同 scope 下 active 唯一 |
| **INDEX** | `INDEX.semantic.md` / `INDEX.episodic.md` 分表 L0 |
| **Checkpoint** | 把 working 落到磁盘 |
| **项目识别** | `project-detect`；confidence=`high` 才允许写 project 语义 |

---

## 4. 数据布局

`agent-memory init` 后记忆根大致为：

```text
$AGENT_MEMORY_ROOT/
  schema_version
  PROTOCOL.md                 # init 时拷贝的协议
  README.md
  profile/
    me.T0.md                  # T0：请按需改成你的硬约束
  working/
    current.md
    handoff-YYYYMMDD-HHMMSS.md
  scopes/
    global/semantic/          # 全局正式语义
    projects/<id>/semantic/   # 项目正式语义
  staging/candidates/         # 候选（默认不检索）
  history/semantic/           # 被 supersede / 软删的正文
  episodes/YYYY/MM/           # 情节
  procedural/
    candidates/
    active/                   # 仅 promote 门禁后
  archive/episodes/
  INDEX.semantic.md
  INDEX.episodic.md
  meta/
    recent.jsonl
    quotas.md
    rejected.jsonl
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

## 6. 命令一览（FA-2）

v1 **穷尽** 17 条（不得擅自加 P0 命令）：

| 命令 | 用途 |
|------|------|
| `init` | 创建合法空库 |
| `doctor` | 健康检查（INDEX/schema/孤儿/高危串） |
| `reindex` | 从正文重建 INDEX |
| `context` | 打包 T0 + Working + 语义命中（开聊首选） |
| `search` | L0 分层检索 |
| `get` | 按 id 取一条 |
| `checkpoint` | 更新 working |
| `handoff` | 写交接快照 |
| `session-end` | 写一条 episode |
| `extract` | 从 episode 抽候选 |
| `remember` | 立刻正式语义（需 `--slot`） |
| `forget` | 软删 / `--hard` |
| `reject` | 候选永不再自动转正 |
| `promote` | 候选 → active |
| `recent` | 最近写入列表（只读） |
| `gc` | 到期处理 + 归档 + 裁剪 recent |
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
agent-memory --version      # 期望：agent-memory 1.0.1 (schema 1.0.0)
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
# 开聊注入
agent-memory context --query "当前任务关键词"

# 固定偏好
agent-memory remember --slot coding --content "只改任务相关文件；禁止顺手重构"

# 任务态
agent-memory checkpoint --goal "修复播放卡顿" --next-steps "- 复现"$'\n'"- 定位"

# 换工具前
agent-memory handoff --goal "修复播放卡顿" --next-steps "- 继续 Media3 排查"

# 收工
agent-memory session-end --title "播放卡顿排查" --body "意图… / 动作… / 结果… / 教训…"
```

### 7.4 Codex Hooks（推荐一键安装）

记忆 **CLI 本身不改**也能用；要让 Codex **开聊自动读、回合结束自动写任务态**，安装随仓库交付的 hooks：

```bash
export AGENT_MEMORY_ROOT="${AGENT_MEMORY_ROOT:-$HOME/.agent-memory}"
bash scripts/install_codex_hooks.sh
# 可选：用户消息含「上次/之前」等再检索
# bash scripts/install_codex_hooks.sh --with-prompt-search
```

| 效果 | 说明 |
|------|------|
| SessionStart | `context` → **stdout 注入会话** + 私有缓存 |
| Stop | **仅**完整 `.agent-memory/turn.json` 时 `checkpoint`；否则 **no-op**（不冲 Working） |
| 合并策略 | **保留**你已有的其它 hooks（如 Muxy） |
| 卸载 | `bash scripts/uninstall_codex_hooks.sh` |

说明：[`scripts/codex-hooks/README.md`](scripts/codex-hooks/README.md) · 整体路径：[`docs/四问题解决路径.md`](docs/四问题解决路径.md)。

更完整的日常流程与命令表：**[使用手册](docs/使用手册.md)**。  
接到 Cursor/Codex 等：**[接入指南](docs/接入指南.md)**。

---

## 8. 符合性三等级

| 等级 | 含义 | 保证方 | 失败怎么算 |
|------|------|--------|------------|
| **L-Core** | CLI 与文件规则的确定行为 | 本仓库 pytest / 脚本 | 实现未完成 |
| **L-Protocol** | Agent 何时读写、不编造 | 接入规则 + 模型 | **不算** CLI bug |
| **L-Ref** | 参考粘贴块 + 演示剧本 | `docs/接入指南.md` 等 | 先修文档/接入 |

**承诺边界：** 只有已执行 `checkpoint` / `handoff` / `session-end` 的状态保证可恢复；用户直接杀进程且未写盘的进度允许丢失。

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

**可能的后续（非承诺）：** MCP 封装、多活跃 working、Git 托管说明、时间点 rollback、更强 extract。

---

## 11. 文档索引

| 文档 | 语言 | 内容 |
|------|------|------|
| [README.md](README.md) | 中文 | 本页：问题、设计、实现、安装 |
| [docs/使用手册.md](docs/使用手册.md) | 中文 | 安装配置、命令详解、日常配方、排错 |
| [docs/接入指南.md](docs/接入指南.md) | 中文 | 接入 Codex/Cursor 等、粘贴块、沙箱、项目标记 |
| [PROTOCOL.md](PROTOCOL.md) | 英文 | Agent 行为契约（init 会拷入记忆根） |
| [REQUIREMENTS.md](REQUIREMENTS.md) | 中文为主 | 需求 Frozen v1.2 |
| [DESIGN.md](DESIGN.md) | 英文 | 详细设计 Frozen v0.3 |
| [docs/demo/AC1_script.md](docs/demo/AC1_script.md) | 英文 | 换 Agent 接续演示剧本 |
| [docs/SIGNOFF.md](docs/SIGNOFF.md) | 英文 | 签字检查表 |

---

## 12. 许可证与贡献

- 个人 / 学习 / 二次修改请自担数据安全责任：**勿把密钥写入记忆库**。  
- 改需求请先升 `REQUIREMENTS.md` 版本，勿在 Frozen 文档上静默扩 scope。  
- Issue / PR 欢迎围绕：文档、测试、L-Core 缺陷、接入体验。

---

**维护提示：** 记忆**数据**与**本仓库代码**分离。数据在你本机的 `AGENT_MEMORY_ROOT`；请勿把含隐私的记忆目录提交到 Git。
