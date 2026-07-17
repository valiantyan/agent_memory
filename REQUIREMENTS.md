# 个人 Agent 记忆系统 · 需求清单

| 项 | 内容 |
|----|------|
| 文档 ID | REQ-AGENT-MEMORY |
| 版本 | **v1.2** |
| 状态 | **Frozen** |
| 日期 | 2026-07-17 |
| 前版 | v1.0 → v1.1（一审修复）→ v1.2（二审修复后冻结） |
| 变更规则 | 改需求须升版本号并更新 §16；未变更不得扩大实现范围 |

---

## 0. 一句话目标

在本机构建一套**纯文件**个人记忆库：多个 Agent 按**同一通用协议**读写；支持任务接续、偏好与项目约定、自动沉淀与可干预清洗。  
**v1 不依赖** Git 远端流程、数据库、向量库真相源、MCP、特定厂商插件。

---

## 1. 背景与问题

| 痛点 | 说明 |
|------|------|
| Agent 失忆 | 换窗口/换工具后上下文断裂 |
| 重复教导 | 偏好与约定每会话重讲 |
| 项目串味 | 项目 A 约定污染项目 B |
| 记忆垃圾场 | 乱记导致费 token、答非所问 |
| 工具绑定 | 不能只依赖某一家内置 memory |

---

## 2. 用户与场景

### 2.1 用户

- **唯一用户**：本人（单用户；无多租户、无团队 ACL）

### 2.2 场景与 v1 薄定义

| ID | 场景 | v1 必须达到（薄定义） |
|----|------|----------------------|
| S1 | 换 Agent / 换窗口接续 | 在**参考接入**下，B 仅读记忆库即可接续 A 留下的任务状态（见 AC-1） |
| S2 | 跨会话偏好与硬约束 | T0/全局偏好经**规定注入路径**可用；变更后当前值唯一（见 AC-3、AC-T0） |
| S3 | 项目开发知识 | 项目约定可写入并按 scope 召回；默认不串项目（见 AC-2） |
| S4 | **本机目录可移植** | 整夹拷到本机另一路径，设置 `AGENT_MEMORY_ROOT` 后可用（**不**承诺跨机器自动同步） |
| S5 | 巩固与清洗 | 候选观察、惰性到期、配额、忘掉/驳回/最近列表（见 AC-5、AC-9、AC-10） |

### 2.3 使用习惯（写回约束）

- 用户常**直接关窗口/切聊天**，很少说再见。  
- 写回不能只靠结束语；协议要求 checkpoint（FW-2）。  
- **可验收承诺**收敛为：凡已执行 `checkpoint` / `handoff` / `session-end` 的状态可恢复；未调用前杀进程允许丢失（§12）。

### 2.4 并发与会话假设

- 允许两 Agent 写同一根目录；INDEX **不得**写残。  
- **v1：任意时刻仅一份活跃 working**。双 Agent 同改 working 可能互相覆盖——文档必须写明；不作为「数据永不丢」承诺。

---

## 3. 目标 / 非目标

### 3.1 目标

1. 跨 Agent 共享同一记忆根目录（通用协议）  
2. 纯文件存储；人可直接读、改  
3. 省长度的分层检索：INDEX 命中后再加载细节  
4. 自动产生语义候选；用户可记住/忘掉/驳回/CLI 补写  
5. 项目隔离 + 自动识别；不确定则不写项目级正式语义  
6. 交付：协议文档 + **最小 CLI 工具集**（命令清单 FA-2，**穷尽列举，不得擅自加 P0 命令**）

### 3.2 非目标（v1）

| 非目标 | 说明 |
|--------|------|
| Git/GitHub 同步产品化 | 无 remote/push/pull 验收 |
| 跨机器自动续上 | 用户可自行拷贝目录 |
| DB / 向量库作真相源 | 真相仅为文件 |
| MCP | 延后 |
| 时间范围 rollback | 延后；v1 有 forget/reject/recent |
| 多租户 / ACL | 不做 |
| 绑定厂商私有 memory API | 不做 |
| 任意 Agent 开箱强制遵守 | **不承诺**；见 §4 |
| 劫持产品关窗事件 | 不承诺 |
| 可检索全文聊天归档 | 禁止 |
| 自动将 procedural 升 active | 禁止 |
| 多活跃 working 隔离 | 不做 |
| 分布式强一致 | 不做 |
| 常驻 daemon/cron | **不要求**；到期靠惰性触发（FM-4） |

### 3.3 延后

- Git 托管说明、MCP、时间 rollback、多 working、可重建 sidecar 索引  

---

## 4. 符合性等级（责任归属）

| 等级 | 代号 | 含义 | 保证方 | 验收 |
|------|------|------|--------|------|
| 核心系统 | **L-Core** | CLI 与文件规则的确定行为 | 本系统 | 脚本 + CLI，**无 LLM** |
| 协议期望 | **L-Protocol** | Agent 应读/写/计数/checkpoint 的时机 | 接入规则 + 模型 | **不**因模型偶发违规判实现失败 |
| 参考集成 | **L-Ref** | 一份参考接入 + 演示剧本 | 文档与 demo | 按剧本走通；失败先修文档/接入 |

### 4.1 映射

- 标注 **L-Core** → 必须无 LLM 可测。  
- 标注 **L-Protocol** → 交付进 PROTOCOL 正文。  
- 标注 **L-Ref** → AC 标明 L-Ref。

### 4.2 抽取链路（防真空）

| 环节 | 等级 | 要求 |
|------|------|------|
| `extract` 从 episode 文件生成 staging | L-Core | **必须实现**；支持纯规则/夹具模式以便 CI |
| Agent 是否每会话调用 extract/session-end | L-Protocol | 协议要求调用 |
| 参考 Agent 演示一次完整沉淀 | L-Ref | 剧本覆盖 |

---

## 5. 术语

| 术语 | 含义 |
|------|------|
| 记忆根目录 | `AGENT_MEMORY_ROOT`；未设置时实现定义默认路径并在 `--help`/文档写明 |
| schema_version | 根目录版本文件；不兼容则 CLI 对写操作失败并提示 |
| T0 | 硬约束与风格文本 |
| Working | **唯一**活跃任务态 |
| Handoff | 交接快照 |
| Episode | 情节摘要（非全文聊天） |
| Semantic active | 默认可检索正式语义 |
| Staging | 候选；**默认不进** search 结果 |
| INDEX.semantic / INDEX.episodic | 分表 L0；禁止混排 top_k |
| Checkpoint | 将 working 等落到磁盘 |
| 惰性到期 | 无 daemon；在 FM-4 所列命令中处理观察期 |
| 字符 | 见 §9.1 唯一定义 |
| Slot | 偏好/事实槽位键，如 `fruit`、`test.framework` |

---

## 6. 需求基线（锁定）

| ID | 需求 |
|----|------|
| B1 | 纯文件；DB 非真相源 |
| B2 | 仅本机可移植；无 Git 流程 |
| B3 | 项目隔离 + 自动识别 |
| B4 | 识别 low → 禁 project 语义写；允许 episode/working |
| B5 | 必须能产生语义候选（`extract` L-Core） |
| B6 | importance≥7 到期转正；&lt;7 到期丢弃；remember 立刻 active |
| B7 | handoff 接续 |
| B8 | 协议层：每 N 轮 + 里程碑 checkpoint |
| B9 | 协议 + FA-2 命令集 |
| B10 | L-Protocol 写回 + L-Core 一键补写 |
| B11 | forget 检索立即生效 + recent；无时间 rollback |
| B12 | 全局偏好 + 项目约定 |
| B13 | §4 三等级验收 |
| B14 | 单一活跃 working |

---

## 7. 功能需求

### 7.1 配置与完整性（L-Core）

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FC0-1 | P0 | L-Core | 所有命令尊重 `AGENT_MEMORY_ROOT` |
| FC0-2 | P0 | L-Core | 读写前检查 `schema_version`；不兼容则写失败、非零退出 |
| FC0-3 | P0 | L-Core | `doctor`：INDEX/正文不一致、坏文件、超配额、高危串 |
| FC0-4 | P0 | L-Core | `reindex`：从正文重建 INDEX |
| FC0-5 | P0 | L-Core | id 冲突 → 拒绝写入、非零退出 |
| FC0-6 | P0 | L-Core | `init`：合法空库（schema_version、T0 模板、空 INDEX、空 working 骨架） |

### 7.2 读 / 检索（L-Core 为主）

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FR-1 | P0 | L-Core | **`context` 必须实现**：打包输出 T0（≤预算）+ working（若有）+ 一次语义 search 命中详情（≤预算）；T0 **不占** top_k 名额 |
| FR-2 | P0 | L-Core | **`search` 必须实现**：语义或情节检索（分模式/分 flag，默认语义）；默认不含 staging |
| FR-3 | P0 | L-Core | 语义只扫 INDEX.semantic 的 active；命中后再读详情 |
| FR-4 | P0 | L-Core | 情节只扫 INDEX.episodic；与语义禁止同一 top_k 混排 |
| FR-5 | P0 | L-Core | 默认 scope=`global`∪`project:<current>`；`--project` 可覆盖 current |
| FR-6 | P0 | L-Core | 无命中 → 空列表；不捏造 id |
| FR-7 | P0 | L-Core | top_k 与长度硬上限 §9；截断须有明确标记 |
| FR-8 | P0 | L-Core | active 行数≥300 时，新增 active 失败（除非先 gc 降下来） |
| FR-9 | P0 | L-Core | 默认 search/context **不含** staging；`--include-staging` 可显式列出 |
| FR-10 | P1 | L-Core | `--history` 才包含 superseded |
| FR-11 | P0 | L-Protocol | Agent 无命中不得谎称库中有记载 |

### 7.3 写 / Working / Checkpoint

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FW-W | P0 | L-Core | 仅一份活跃 working 路径 |
| FW-1 | P0 | L-Protocol | Agent 任务中更新 working |
| FW-2 | P0 | L-Protocol | 每 **N=8** 次用户消息 checkpoint；里程碑（§7.3.1）checkpoint |
| FW-3 | P0 | L-Core | `checkpoint`：更新 working 规定字段 + `updated_at`；并执行 **惰性到期**（FM-4） |
| FW-4 | P0 | L-Core | `handoff`：写出 goal、decisions、next_steps、related_ids、project_id、session_id、updated_at |
| FW-5 | P0 | L-Core | `session-end`：checkpoint + **新写 1 条** episode；正文 &gt;8000 字符 → **失败**（不截断）；并惰性到期 |
| FW-6 | P0 | L-Core | `extract --from <episode_id>`：只写 staging，不写 active |
| FW-7 | P0 | L-Core | 写入必须含 source.kind；白名单含 `user_explicit` / `extracted` / `handoff` |
| FW-8 | P0 | L-Core | `tool_output` / `web`：**不得** promote/remember 成 semantic active；误标则拒绝 |
| FW-9 | P0 | L-Core | `remember --slot <slot> --content ...`：立刻 active + supersede 同 slot；过安全门；惰性到期 |
| FW-10 | P0 | L-Core | **所有** CLI 写路径执行 SEC 门禁（working/handoff/episode/staging/active） |
| FW-11 | P0 | L-Core | `get <id>`：打印单条正文与元数据 |

#### 7.3.1 里程碑（L-Protocol）

Agent 应 checkpoint 的情况包括但不限于：形成明确技术决策、可运行里程碑完成、即将切换 Agent/项目。  
**L-Core 不**解析自然语言聊天流。

### 7.4 候选 / 转正 / 重要性

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FM-1 | P0 | L-Core | 候选字段：id, importance(1–10), content_kind, created_at, scope, source |
| FM-2 | P0 | L-Core | **出厂打分默认**：content_kind∈{constraint,preference,decision} → importance 至少 7；fact 默认 5；其它 4；`remember` 视为 10 且立即 active |
| FM-3 | P0 | L-Core | 观察期 **D=5 个自然日**（按日期差，见 §9.2）：到期且未 reject 时，importance≥7 → active 并进 INDEX；importance&lt;7 → 丢弃/discarded 且不进默认检索 |
| FM-4 | P0 | L-Core | **惰性到期强制触发命令**（不可配置关闭）：`gc`、`checkpoint`、`session-end`、`remember`、`promote`、`search`、`context`。`dream` 若实现也须触发 |
| FM-5 | P0 | L-Core | `reject <id>`：候选永不再自动转正 |
| FM-6 | P0 | L-Core | `promote <id>`：手动转正（安全+配额+source 门禁） |
| FM-7 | P0 | L-Core | 同 slot 仅一份 active；新写 supersede 旧写 |

### 7.5 忘掉与最近列表

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FF-1 | P0 | L-Core | `forget <id>`：退出默认检索 |
| FF-2 | P0 | L-Core | 默认软删（status=deleted 或移出 INDEX）；`forget --hard` 删文件 |
| FF-3 | P0 | L-Core | `recent [--n 20]`：最近写入 id/time/kind/path |
| FF-4 | P0 | L-Core | recent 元数据保留 **≥30 个自然日** |

### 7.6 偏好

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FP-1 | P0 | L-Core | 同 slot 一份 current |
| FP-2 | P0 | L-Core | 未显式否定不写「不喜欢旧值」 |
| FP-3 | P1 | L-Core | superseded 可查 `--history` |

### 7.7 程序记忆

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FPr-1 | P1 | L-Core | 允许 procedural candidate 文件 |
| FPr-2 | P0 | L-Core | **禁止**自动路径写 procedural active；`promote` 程序记忆须 `--user-confirmed` 或关联 ≥2 个 episode id |
| FPr-3 | P1 | L-Protocol | v1 **不要求** Agent 自动抽 procedural |

### 7.8 项目识别

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FJ-1 | P0 | L-Core | `project-detect` 输出 project_id + confidence∈{high,low} |
| FJ-2 | P0 | L-Core | low 时写入 scope=project:* 的 semantic（staging/active）**失败** |
| FJ-3 | P0 | L-Core | working.project_id 覆盖检测结果 |
| FJ-4 | P0 | L-Core | **测试钩子** `--force-confidence=low|high`（仅测试/调试；文档标明）以满足 AC-10 |
| FJ-5 | P1 | L-Core | 启发式顺序：标记文件 → git 根名 → …（细节设计定） |

### 7.9 并发

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FC-1 | P0 | L-Core | 一记忆一文件 |
| FC-2 | P0 | L-Core | INDEX：临时文件 + 原子 rename；AC-11 |
| FC-3 | P1 | L-Core | 可选 lock 文件 |
| FC-4 | P0 | — | 文档：working 覆盖风险 |

### 7.10 巩固与 GC

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FG-1 | P0 | L-Core | `gc`：到期处理 + 配额检查 + 过期 episode 策略入口 |
| FG-2 | P0 | L-Core | episode 超过 90 自然日：gc 时归档或删详情（设计定一种并文档化；须可测） |
| FG-3 | P0 | L-Core | 超 300 active 阻断新增 |
| FG-4 | P1 | L-Core | 近重复候选合并 |
| FG-5 | P2 | L-Core | `dream` 报告（可选命令） |

### 7.11 交付物

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| FA-1 | P0 | L-Core | PROTOCOL 文本（含 §4、§7.12、N=8、里程碑、禁写） |
| FA-2 | P0 | L-Core | **v1 命令穷尽列表（必须全部实现）**：`init`, `doctor`, `reindex`, `context`, `search`, `get`, `checkpoint`, `handoff`, `session-end`, `extract`, `remember`, `forget`, `reject`, `promote`, `recent`, `gc`, `project-detect` |
| FA-2b | P2 | L-Core | 可选命令：`dream`, `touch`（不做不挡 v1） |
| FA-3 | P0 | — | 与 AGENTS.md 等共存，不强制取消 |
| FA-4 | P0 | L-Ref | 参考接入说明 + AC-1 演示剧本 |

### 7.12 协议义务摘要（L-Protocol · 须写入 PROTOCOL）

1. 启动：`context`（或等价读 T0+working+search）  
2. 每 8 次用户消息：`checkpoint`  
3. 里程碑 / 换工具前：`handoff` 或 `session-end`  
4. 无命中不谎称  
5. 不把推断标成 user_explicit  
6. 不写密钥  
7. 单一 working：换任务先 handoff/session-end  

---

## 8. 安全与隐私

| ID | 优先级 | 等级 | 需求 |
|----|--------|------|------|
| SEC-1 | P0 | L-Core | 拒绝密钥模式（含 api_key、sk-、Bearer、私钥头等夹具集；设计列模式表，AC 用固定夹具） |
| SEC-2 | P0 | L-Core | 拒绝身份证/银行卡明显模式；**密钥类禁止 --force 绕过**；非密钥误报允许 `--force` 并 warning |
| SEC-3 | P0 | L-Core | episode/正文硬上限；禁止当全文聊天库用 |
| SEC-4 | P0 | L-Core | promote/remember 拒绝 tool_output/web → active |
| SEC-5 | P0 | L-Core | forget 后默认 search/context 语义命中不可见 |
| SEC-6 | P0 | L-Core | 门禁覆盖一切 CLI 写路径 |
| SEC-7 | P0 | L-Protocol | 禁止 Agent 直写绕过；doctor 扫描高危 |
| SEC-8 | P0 | L-Core | 密钥夹具 `forget --hard` 后文件不存在 |

**AC-8 范围**：仅约束 **CLI 路径**。直写文件绕过 = 协议违规 + doctor 尽力检出，**不**单独判 CLI 失败。

---

## 9. 量化参数

### 9.1 字符定义（唯一）

- **字符** = Unicode code point 个数，与 Python 3 `len(str)` 一致。  
- **禁止**用「按字节」或「按 tokenizer」做验收计量。  
- 文档可注释「约等于 token 量级」，**验收只认字符**。

### 9.2 自然日

- 「D 个自然日」= 按根目录约定时区（默认本地时区）的日历日期差 ≥ D。  
- 测试允许**直接修改**候选文件 `created_at` 字段以构造到期（AC-9）。

### 9.3 出厂默认表

| 参数 | 值 |
|------|-----|
| 语义 top_k | 5 |
| context 内语义详情总长 | ≤ 4800 字符 |
| T0 段总长 | ≤ 1600 字符 |
| 观察期 D | 5 自然日 |
| 转正阈值 | importance ≥ 7 |
| Checkpoint N | 每 8 次用户消息（L-Protocol） |
| Episode TTL | 90 自然日 |
| INDEX.semantic active 上限 | 300 |
| recent 默认 n | 20 |
| recent 保留 | ≥ 30 自然日 |
| episode 正文上限 | 8000 字符（超则失败） |
| one_liner | ≤ 80 字符 |

---

## 10. 验收标准

### 10.1 总则

| 规则 | 内容 |
|------|------|
| L-Core | 无 LLM；脚本 + CLI；失败 ⇒ v1 未完成 |
| L-Ref | 按官方剧本；失败 ⇒ 修接入文档/demo |
| 测试数据 | 允许直接改 yaml/front matter 时间戳；允许 `--force-confidence` |
| 签字包 | **全部 L-Core AC 通过** + **AC-1 的 L-Ref 步骤通过** |

### 10.2 L-Core 用例

#### AC-T0

1. `init`；改 T0 插入唯一串 `T0MARK`  
2. `context` 输出含 `T0MARK` 且 T0 段 ≤1600 字符  

#### AC-2 项目不串味

1. `remember` 或等价写入 active：scope=project:A，正文含 `MOCK_A_ONLY`  
2. `search --project B`（或 current=B）→ 不含 `MOCK_A_ONLY`  
3. `search --project A` → 含 `MOCK_A_ONLY`  

#### AC-3 偏好唯一

1. `remember --slot fruit --content 喜欢苹果` → current 苹果  
2. `remember --slot fruit --content 喜欢橘子` → current 橘子  
3. 默认 search 不以苹果为 current  

#### AC-4 checkpoint 落盘

1. `checkpoint` 写入 goal=`G2MARK`  
2. 读 working 含 `G2MARK` 且 updated_at 变化  
3. （不测杀进程丢数据）  

#### AC-5 forget + recent

1. `remember` 后 `recent` 可见 id  
2. `forget id` 后默认 search 不可见  
3. 密钥夹具写入失败或 hard forget 后文件不存在（与 AC-8 交叉）  

#### AC-6 分层与预算

1. ≥6 条可命中 active → search 默认 ≤5  
2. 超长详情 → 总长 ≤4800 或带截断标记且 ≤4800 输出  
3. 空库 search → 空列表  

#### AC-7 可移植

1. 写入一条 active  
2. 拷贝整根到新路径；`AGENT_MEMORY_ROOT=新路径` → search 仍命中  

#### AC-8 安全

1. `remember` 含夹具 `api_key=sk-test-forbidden` → 非零退出，无新 active  
2. `session-end` 正文 &gt;8000 字符 → 非零退出  
3. 将 source 标为 tool_output 的条目 `promote` → 拒绝  

#### AC-9 到期

1. 造 staging importance=8，`created_at` 为 6 日前 → 跑 `gc`（或 `search` 触发惰性）→ 成 active 且 INDEX 可见  
2. staging importance=4，6 日前 → 处理后默认 search 不可见  
3. `reject` 后即使到期也不 active  

#### AC-10 项目 low

1. `project-detect --force-confidence=low`  
2. 尝试写入 project scope semantic → 失败  
3. 写 episode → 成功  

#### AC-11 INDEX 原子性

1. 并行脚本两次写 INDEX 路径操作  
2. 结束后 INDEX 可完整解析，无半行截断  

#### AC-P 程序记忆

1. 仅 extract 出 procedural 形态 → 无 procedural active  
2. `promote` 无 `--user-confirmed` 且无双 episode 证明 → 拒绝  

#### AC-X extract

1. 写入合法 episode  
2. `extract --from <id>` → staging 出现候选；默认 search 不见  

### 10.3 L-Ref 用例

#### AC-1 换工具接续

| 步骤 | 期望 |
|------|------|
| 1. CLI `handoff` 含 goal=`G1MARK`，next_steps 含 `STEP1MARK` | 文件层通过 |
| 2. 新会话参考 Agent 仅按接入文档启动（无旧聊天） | 首次响应或执行的 `context` 使用中体现 G1MARK 与 STEP1MARK |
| 3. 用户问「下一步做什么」 | 回答覆盖 STEP1MARK 要点 |

L-Core 子集：仅步骤 1 + `context`/`get` 能读出标记 ⇒ 文件层通过；**签字包需要步骤 2–3**。

#### AC-4R（可选抽检，非签字阻塞）

参考 Agent 在模拟 ≥8 轮后是否调用 checkpoint；失败则改 PROTOCOL/demo，不单独否决 L-Core。

---

## 11. 业界对齐摘要

自动候选 + 门禁 + 可删；程序记忆严于语义；INDEX→详情；文件库尽力并发；本地可移植；三等级责任。

---

## 12. 依赖、假设与产品限制

1. 本机可跑 CLI。  
2. 不保证任意 Agent 预装协议。  
3. **未 checkpoint 即杀进程允许丢最后若干轮**。  
4. 单用户可信。  
5. 项目识别可误判 → 偏向少写项目语义。  
6. 安全模式匹配非密码学级。  
7. 验收计量只用 §9.1 字符定义。  
8. 无常驻进程；若用户从不触发 FM-4 命令，到期不处理——**正常**；常用 `search`/`context`/`checkpoint` 会触发。

---

## 13. 里程碑状态

| 阶段 | 状态 |
|------|------|
| 需求澄清 | 完成 |
| 一审对抗 + v1.1 | 完成 |
| 二审对抗 + v1.2 | **完成并 Frozen** |
| 设计 | **下一步** |
| 实现 / 验收 | 设计冻结后 |

---

## 14. 草稿目录

`agent-memory/` 历史草稿 **不是** 交付物与验收基线；实现可全新 scaffold。

---

## 15. 设计开放项（不阻塞需求）

| ID | 项 | 约束 |
|----|----|------|
| D-1 | 目录树与文件名 | 须满足本需求语义 |
| D-2 | project-detect 启发式细节 | 须支持 FJ-4 测试钩子 |
| D-3 | CLI 语言与发行 | — |
| D-4 | 配置文件是否覆盖 importance 默认 | 出厂默认不可删 |
| D-5 | extract 规则 vs LLM | **必须**有确定性夹具模式跑 AC-X/AC-9 |
| D-6 | INDEX 存储格式 | 须可原子写与 doctor 解析 |
| D-7 | 密钥正则表 | 须覆盖 AC-8 夹具 |

---

## 16. 版本变更摘要

### v1.1 ← v1.0（一审）

符合性三等级；S4 可移植；惰性到期；单 working；staging 默认不可检索；全路径安全；AC 可执行；字符预算；CLI 清单；tool/web 禁 active 等。

### v1.2 ← v1.1（二审必改）

| 问题 | 修复 |
|------|------|
| search 惰性到期可关导致永不到期 | FM-4 **强制**含 search/context/checkpoint/session-end/remember/promote/gc |
| context 或 search 二选一模糊 | **两者皆必须**；context 定义明确 |
| 字符定义两可 | 锁定 Python3 `len(str)` code point |
| episode 超长可截断可失败 | **只允许失败** |
| AC-9 无法造时间 | 允许改 created_at |
| AC-10 无法造 low | `--force-confidence` |
| remember 无 slot | `remember --slot` 为 P0 |
| extract 无独立 AC | 增 AC-X |
| 命令「上限」易膨胀 | 改为 **穷尽列表** FA-2 |
| 关窗 vs AC-4 | 签字仅 L-Core checkpoint；限制写入 §2.3/§12 |

---

## 17. 第二轮对抗式审查结论（v1.2）

### 17.1 审查方法

站在「外包实现方 vs 验收方」对立面，检查：责任真空、不可测 AC、内部矛盾、范围膨胀、安全旁路、与用户关窗习惯是否再过约。

### 17.2 P0 清零结果

| 原 P0 风险 | v1.2 状态 |
|------------|-----------|
| Agent 自觉当系统保证 | 已用 §4 拆开 |
| 观察期无人跑 | FM-4 强制挂到常用命令 |
| AC 不可执行 | §10 分步 + 钩子 |
| Working 多会话互踩未声明 | B14 + 产品限制 |
| 安全仅 semantic | FW-10/SEC-6 |
| tool/web 进 active | FW-8/SEC-4/AC-8 |
| 字符/token 扯皮 | §9.1 |
| 命令清单膨胀 | FA-2 穷尽 |
| 关窗假承诺 | AC-4 收敛 |

### 17.3 残余风险（接受为 P2/产品限制，不阻塞冻结）

| ID | 残余 | 处理 |
|----|------|------|
| R1 | 模型不调用 checkpoint 仍丢进度 | §12 明示；L-Protocol + L-Ref 抽检 |
| R2 | Agent 绕过 CLI 直写脏文件 | doctor 尽力；不设 100% |
| R3 | 安全正则可被绕过 | 启发式；密钥 --force 禁止 |
| R4 | extract 夹具模式与「智能抽取」质量差 | 质量属体验；正确性靠门禁与 forget |
| R5 | 单 working 限制并行项目体验 | 非目标；v2 可做多 session |

**裁决：无剩余 P0 需求缺陷；v1.2 予以 Frozen。**

---

## 18. 冻结声明

```text
文档: REQUIREMENTS.md
版本: v1.2
状态: Frozen
日期: 2026-07-17
下一阶段: 设计（DESIGN），不得在未改本文件版本号的情况下扩大需求范围
```

实现与设计必须可追溯到本文件 ID（FR/FW/AC/…）。  
若需改需求：先发 v1.3+ 变更说明，再改设计/代码。
