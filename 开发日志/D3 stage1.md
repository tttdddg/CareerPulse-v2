# 阶段3实施规格（人岗匹配 / 能力缺口 / 3—5年职业路径）

## 前置结论：阶段2现状核查结果

| 核对项                  | 现状                                                         | 位置                                                         |
| ----------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 学生画像 Schema         | ✅ 已实现 `StudentProfile`/`StudentAbility`/`StudentBasicInfo`，`extra="forbid"`，标签受控 | `backend/app/schemas/profile_schema.py`                      |
| 岗位画像 Schema         | ✅ 已实现 `JobProfile`/`RequiredJobAbility`/`TrendResult`/`JobAgentOutput`，权重和=1.0 | `backend/app/schemas/job_schema.py`                          |
| 统一能力维度            | ✅ 48 个标准标签（5 类）+ 43 条别名 + `AbilityTagNormalizer`  | `backend/app/data/ability_tags.json`、`ability_tag_aliases.json`、`services/ability_normalization.py` |
| ProfileAgent / JobAgent | ✅ 真实 LLM + 规则/Demo fallback，`competitiveness_score` 被强制置 0.0（占位） | `agents/profile_agent.py`、`agents/job_agent.py`             |
| CareerState             | ✅ 12 个业务字段 + `agent_logs` + `apply_agent_data()` 白名单写入 | `orchestrator/career_state.py`                               |
| MatchService            | ✅ 已实现确定性算法（**返回裸 dict，无 Pydantic Schema**）    | `services/match_service.py`                                  |
| MatchAgent / PathAgent  | ⚠️ 仍是 **Mock**，且 MatchAgent 内联重复实现了匹配逻辑，**没有调用 MatchService** | `agents/match_agent.py`、`agents/path_agent.py`              |
| PathService             | ❌ **不存在**（只有 Mock PathAgent 写死 3 阶段）              | —                                                            |
| 数据库模型              | ⚠️ 仅 Pydantic 种子数据模型（`a02_models.py`），**无 `migrations/` 目录** | `models/a02_models.py`                                       |
| 职业图谱数据            | ✅ 10 节点 / 16 边已存在，但**节点无能力向量**                | `data/career_graph.json`                                     |
| FastAPI 接口            | ✅ 3 个端点，但未挂载到 legacy 路由                           | `api/career_agent_api.py`                                    |
| 测试样例                | ✅ `test_match_service.py`（14 例）、`test_ability_normalization.py`、`test_profile_agent.py` | `backend/tests/`、`agents/tests/`                            |

---

## 一、阶段2可直接复用的字段与模块

### 1.1 直接复用的 Schema 字段（无需改动）

**学生侧（`StudentProfile`）**
- `abilities[].tag` — 已通过 `active_ability_tags()` 保证与岗位侧同源，可直接做交集
- `abilities[].level`（1–5）— 匹配分与缺口计算的直接输入
- `abilities[].confidence`（0–1）— **本次要接进证据可信度，但字段本身已存在**
- `basic_info.education_level / graduation_year / years_of_experience / target_job / target_industry` — 硬性条件、路径时间成本、用户偏好的输入
- `completeness / missing_fields` — 缺失数据处理的输入

**岗位侧（`JobProfile`）**
- `required_abilities[].tag / required_level / weight / importance` — 匹配分、硬性条件（`critical`）、缺口优先级的输入
- `required_abilities[].evidence` — 仅作审计/解释素材，不参与评分
- `normalized_title / title / industry` — 与职业图谱节点对齐的锚点

**TrendResult（`hot_skills / rising_skills / declining_skills`）** — 可作为路径「风险」维度的输入（`declining_skills` 命中路径节点能力时降分）

### 1.2 直接复用的模块

| 模块                                                         | 复用方式                                                     |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| `AbilityTagNormalizer`                                       | MatchService 已在用（`normalize_or_raise`）；PathService 解析图谱能力向量时同样复用 |
| `active_ability_tags()`                                      | 校验新 Schema 中所有 `tag` 字段                              |
| `MatchService`                                               | 保留为唯一匹配分计算入口（**MatchAgent 改为调用它**，删除内联重复逻辑） |
| `AbilityTag`/`CareerGraphNode`/`CareerGraphEdge`/`CareerGraph` 种子模型 | PathService 加载 `career_graph.json` 时复用（但需扩展，见下） |
| `BaseAgent`/`AgentResult`/`CareerState`                      | 不动，MatchAgent/PathAgent 继续套此 envelope                 |
| `StudentProfile`/`JobProfile` 的 `extra="forbid"` + 标签校验范式 | 新 Schema 沿用同样严格性                                     |

---

## 二、缺失或冲突的字段/模块

> 按严重度排序；标注是否需要 ADR（`AGENTS.md` 要求公共字段变更必须更新 `API_CONTRACTS.md` 并在 `decisions/` 建 ADR）。

### 2.1 命名/结构冲突（必须用 ADR 裁决）

| #    | 冲突点                                                       | 证据                                                         | 建议                                                         |
| ---- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| C1   | 冻结文档写的是 `matching_service.py` + `_rule_fallback_analysis()`，实际文件是 `match_service.py` 且无该方法 | `03_ARCHITECTURE.md §2`、`05_AGENT_CONTRACTS.md §3.7` vs `services/match_service.py` | ADR 统一命名为 `match_service.py`，`_rule_fallback_analysis` 降级由 Agent 层承担 |
| C2   | MatchAgent（Mock）内联重写了匹配算法，**未调用已存在的 MatchService**，且其 `dimensions` 是单个「岗位核心能力」聚合维度 | `match_agent.py` vs `match_service.py`                       | 阶段3 重写 MatchAgent 只做「调 Service + 生成解释」          |
| C3   | `MatchService` 的 `dimensions[].name` 是**按标签**（`name=tag`），而冻结 Demo（`04_API_CONTRACTS §12.3`）的 `dimensions` 是**按聚合维度**（专业技能/学习能力/实践能力/通用素养） | `match_service.py:60` vs `04 §12.3`                          | ADR 定案：`dimensions` 到底按标签还是按 `category` 聚合      |
| C4   | `ability_gaps[].current_level` 对缺失能力用 `0`，但 `04 §4.1` 写「int 1-5」；`§10` 又写「缺失时 0 仅用于 Gap 计算」 | `match_service.py:50` vs `04 §4.1/§10`                       | 保持 Service 现状，ADR 明确 `current_level` 允许 0（仅缺口项） |
| C5   | 冻结 `PathPlan`（§5.1）字段太薄，无法承载阶段3 的 `CandidatePath/CareerStage/CareerRoadmap` | `04 §5.1` vs 阶段3 目标                                      | ADR：扩展 PathPlan 或新增独立 `career_roadmap` 字段          |

### 2.2 缺失字段（阶段3 需要但阶段2 没有）

| #    | 缺失                                                         | 影响                                             | 建议                                                         |
| ---- | ------------------------------------------------------------ | ------------------------------------------------ | ------------------------------------------------------------ |
| M1   | **`MatchResult` 无 Pydantic Schema**（Service 返回裸 dict）  | 无法复用 `extra="forbid"` + 契约校验             | 新增 `schemas/match_schema.py`                               |
| M2   | **无 `PathService`、无 `path_schema.py`**                    | 阶段3 核心                                       | 新增                                                         |
| M3   | **职业图谱节点无能力向量**（`CareerGraphNode` 只有 `level_range`，无 `required_abilities`） | 无法算 `AbilityGapCost`                          | 扩展 `CareerGraphNode` 增加 `required_abilities`（可空，缺省回退到岗位画像查询） |
| M4   | **岗位侧无「学历/年限」硬性要求字段**（`JobProfile` 没有 `education_requirement` / `experience_requirement`） | 硬性条件只能落到 `critical` 能力，无法做学历门槛 | 方案A：给 `JobProfile` 加字段（需 ADR）；方案B：阶段3 硬性条件仅限「critical 能力缺失」 |
| M5   | **`confidence` 未参与任何计算**                              | 证据可信度要求落空                               | MatchService 增加可信度折扣（见 §四.5）                      |
| M6   | **`importance` 未参与任何计算**                              | 硬性条件/加权可解释性落空                        | 接入硬性条件与缺口优先级（见 §四.1）                         |
| M7   | `competitiveness_score` 恒为 0.0（冻结占位）                 | 与阶段3 无直接冲突，但注意这是「确定性计算」欠账 | 不属阶段3 范围，标注即可                                     |
| M8   | 无 `schemas/__init__.py`、`services/__init__.py`、无 `migrations/` 目录 | 新增模块时命名空间/迁移约定                      | 阶段3 补 `__init__.py`；持久化用内存，暂缓迁移               |

---

## 三、阶段3 建议的数据结构

> 约定：🟢=复用阶段2；🟡=新增（不触碰冻结契约）；🔴=新增/改动需 ADR。
> 所有 `tag` 字段沿用 `active_ability_tags()` 校验；所有模型 `extra="forbid"`、`str_strip_whitespace=True`。

### 3.1 MatchRequest 🟢
匹配计算的入参包装。

| 字段              | 类型                   | 说明                                                         |
| ----------------- | ---------------------- | ------------------------------------------------------------ |
| `student_profile` | `StudentProfile`       | 🟢 直接复用                                                   |
| `job_profile`     | `JobProfile`           | 🟢 直接复用                                                   |
| `options`         | `MatchOptions \| None` | 🟡 可选：`hard_gate_policy`（`strict`/`lenient`，默认 `lenient`）、`confidence_floor`（默认 0.3） |

### 3.2 DimensionMatch 🟡（对应现有 `dimensions[]` 的扩展）
单维度（能力）匹配明细。

| 字段             | 类型          | 来源 | 说明                                     |
| ---------------- | ------------- | ---- | ---------------------------------------- |
| `name`           | `str`         | 现有 | 维度名（标签或聚合维度，取决于 C3 裁决） |
| `tag`            | `str \| None` | 🟡    | 规范标签；聚合维度时为 None              |
| `category`       | `str \| None` | 🟡    | 标签一级分类（hard_skill…）              |
| `student_score`  | `float`       | 现有 | 0–100                                    |
| `job_required`   | `float`       | 现有 | 固定 100                                 |
| `gap`            | `float`       | 现有 | `student_score - 100`                    |
| `weight`         | `float`       | 现有 | 岗位权重                                 |
| `current_level`  | `int`         | 🟡    | 0–5                                      |
| `required_level` | `int`         | 🟡    | 1–5                                      |
| `importance`     | `str`         | 🟡    | `critical/important/nice_to_have`        |
| `confidence`     | `float`       | 🟡    | 学生证据可信度（缺失=0）                 |
| `status`         | `str`         | 🟡    | `adequate/insufficient/missing`          |

### 3.3 SkillGap 🟡（对应现有 `ability_gaps[]` 的扩展）
关键能力缺口。

| 字段               | 类型    | 来源 | 说明                                        |
| ------------------ | ------- | ---- | ------------------------------------------- |
| `tag`              | `str`   | 现有 |                                             |
| `current_level`    | `int`   | 现有 | 0–5（缺失=0，见 C4）                        |
| `required_level`   | `int`   | 现有 | 1–5                                         |
| `gap`              | `int`   | 现有 | `max(required-current,0)`                   |
| `priority`         | `int`   | 现有 | 1 起，Service 计算                          |
| `importance`       | `str`   | 🟡    | 用于硬性条件与优先级 tie-break              |
| `weight`           | `float` | 🟡    | 岗位权重                                    |
| `difficulty`       | `float` | 🟡    | 标签难度系数（1–3）                         |
| `confidence`       | `float` | 🟡    | 证据可信度                                  |
| `estimated_effort` | `float` | 🟡    | `gap × difficulty`，供 PathService 阶段拆解 |

### 3.4 MatchResult 🔴（扩展冻结契约 §4.1，需 ADR）
顶层匹配结果。**保留全部冻结字段**，仅追加。

| 字段                         | 类型                   | 来源             | 说明                                                      |
| ---------------------------- | ---------------------- | ---------------- | --------------------------------------------------------- |
| `overall_score`              | `float`                | 现有             | **冻结公式，不许变**（见 §四.6）                          |
| `confidence_adjusted_score`  | `float`                | 🟡 追加           | 接入可信度后的参考分（不改 `overall_score` 以守契约）     |
| `skill_coverage`             | `float`                | 🟡 追加           | 技能覆盖率 0–1（见 §四.3）                                |
| `match_level`                | `str`                  | 🟡 追加           | `high/good/fair/weak/low`（见 §四.7）                     |
| `hard_condition_result`      | `dict`                 | 🟡 追加           | `{passed: bool, failed: [...]}`                           |
| `dimensions`                 | `list[DimensionMatch]` | 现有（结构升级） |                                                           |
| `ability_gaps`               | `list[SkillGap]`       | 现有（结构升级） |                                                           |
| `gap_analysis`               | `list[...]`            | 现有             | `item/status/suggestion`，`suggestion` 由 MatchAgent 生成 |
| `strengths`                  | `list[str]`            | 现有             | MatchAgent 生成                                           |
| `missing_data_flags`         | `list[str]`            | 🟡 追加           | 缺失数据处理标记（见 §四.8）                              |
| `matching_algorithm_version` | `str`                  | 现有             | 固定 `deterministic-v1`                                   |

### 3.5 CareerNode 🔴（扩展 `CareerGraphNode`，需 ADR）
运行时路径节点。

| 字段                                                         | 类型                             | 来源                     | 说明                                                         |
| ------------------------------------------------------------ | -------------------------------- | ------------------------ | ------------------------------------------------------------ |
| `node_key` / `job_title` / `level_range` / `industry` / `description` | —                                | 🟢 复用 `CareerGraphNode` |                                                              |
| `required_abilities`                                         | `list[JobAbilityWeight] \| None` | 🟡 追加                   | **能力向量**（PathService 算差距成本的关键，M3）；空时回退 `JobService` 查询 |

### 3.6 CareerEdge 🔴（扩展 `CareerGraphEdge`，需 ADR）
运行时路径边。

| 字段                                                         | 类型                | 来源   | 说明                                                      |
| ------------------------------------------------------------ | ------------------- | ------ | --------------------------------------------------------- |
| `source_key`/`target_key`/`relation_type`/`reason`/`transfer_cost`/`growth_value`/`source_industry`/`target_industry` | —                   | 🟢 复用 |                                                           |
| `required_new_abilities`                                     | `list[str] \| None` | 🟡 追加 | 跨边需新学的标签（缺省回退「目标节点能力 − 源节点能力」） |

### 3.7 CandidatePath 🟡
一条从起点到目标的候选路径。

| 字段                   | 类型               | 说明                             |
| ---------------------- | ------------------ | -------------------------------- |
| `path_id`              | `str`              | 稳定 id                          |
| `nodes`                | `list[CareerNode]` | 有序节点序列                     |
| `edges`                | `list[CareerEdge]` | 有序边序列                       |
| `relation_mix`         | `str`              | `vertical` / `lateral` / `mixed` |
| `target_node`          | `CareerNode`       | 终点节点                         |
| `feasibility`          | `bool`             | 可行性（见 §五.3）               |
| `time_estimate_months` | `int`              | 时间成本（见 §五.5）             |
| `score`                | `PathScore`        | 分解评分                         |

### 3.8 PathScore 🟡
路径评分分解（对应冻结 §5.3 公式，扩展为可解释分解）。

| 字段                         | 类型    | 说明                                                        |
| ---------------------------- | ------- | ----------------------------------------------------------- |
| `growth_value`               | `float` | Σ 目标能力等级 × 市场溢价（现有概念，**待定溢价系数来源**） |
| `transfer_cost`              | `float` | Σ 新能力数 × 学习难度（现有概念）                           |
| `ability_gap_cost`           | `float` | Σ `Gap_k × Difficulty_k`（现有概念）                        |
| `user_preference_adjustment` | `float` | 🟡 偏好修正（±，见 §五.6）                                   |
| `risk_penalty`               | `float` | 🟡 风险扣分（≥0，见 §五.8）                                  |
| `target_consistency`         | `float` | 🟡 目标一致性 0–1（见 §五.7）                                |
| `total_score`                | `float` | **冻结主公式结果 + 调整项**                                 |

### 3.9 CareerStage 🟡（对应冻结 `phase`，扩展为「目标+能力要求+行动」）
单个阶段。

| 字段                 | 类型             | 说明                                       |
| -------------------- | ---------------- | ------------------------------------------ |
| `stage_index`        | `int`            | 1 起                                       |
| `duration_months`    | `int`            | 🟢 复用 `phase.duration_months`             |
| `target_role`        | `str`            | 🟢 复用 `phase.target_role`                 |
| `objectives`         | `list[str]`      | 🟡 阶段目标                                 |
| `required_abilities` | `list[SkillGap]` | 🟡 本阶段要补齐的能力（含目标等级）         |
| `actions`            | `list[str]`      | 🟡 行动任务（PathAgent 生成描述）           |
| `milestone`          | `str`            | 🟢 复用 `phase.milestone`（PathAgent 生成） |

### 3.10 CareerRoadmap 🔴（扩展/替代冻结 `PathPlan` §5.1，需 ADR）
3 年/5 年路径总成。

| 字段                     | 类型                  | 说明                                            |
| ------------------------ | --------------------- | ----------------------------------------------- |
| `target_job`             | `str`                 | 🟢 复用                                          |
| `plan_3year`             | `list[CareerStage]`   | 🟢（结构升级）                                   |
| `plan_5year`             | `list[CareerStage]`   | 🟢（结构升级）                                   |
| `candidate_paths`        | `list[CandidatePath]` | 🟡 已排序候选                                    |
| `selected_path_id`       | `str \| None`         | 🟡 排序第一                                      |
| `path_algorithm_version` | `str`                 | 🟢 复用 `graph-search-v1`（如有算法升级再 bump） |

> **兼容性建议**：阶段3 保留 `path_plan`（冻结 §5.1）不变，将 `CareerRoadmap` 作为**新增的 `state.career_roadmap` 字段**并行产出，避免破坏既有 `path_plan` 消费者；是否废弃 `path_plan` 用 ADR 后续裁决。

---

## 四、MatchService 确定性计算方案

> 原则：**所有数值由代码算，LLM 只填 `suggestion`/`strengths` 自然语言**（`04 §4.2` 红线）。

### 4.1 硬性条件处理
数据前提：岗位侧无学历/年限要求字段（M4），故硬性条件保守实现为：

- **Hard Gate = `importance == "critical"` 且学生 `current_level == 0`（完全缺失）**
- 策略（`options.hard_gate_policy`）：
  - `lenient`（默认，学习平台语义）：不判死，但 `match_level` 强制上限 `weak`，`hard_condition_result.failed` 记录该标签，`overall_score` 照算；
  - `strict`（未来招聘语义）：任一 critical 缺失 → `passed=false`，`overall_score` 封顶（如 60）。
- 若后续 ADR 给 `JobProfile` 加 `education_requirement`，则学历不匹配同样进入 hard gate（本阶段不实现）。

### 4.2 各能力维度匹配（复用冻结公式）
```
ratio_k   = min(Suk / Jik, 1.0)     # 学生等级 / 岗位要求等级，封顶 1
base_k    = ratio_k × 100
```
维度对齐：按 `required_abilities` 逐个遍历（学生侧无该标签即 `Suk=0`）；`dimensions` 是否按 `category` 聚合由 C3 裁决（建议：`dimensions[]` 输出**按标签**，另加 `category` 字段供前端聚合，避免破坏现有 14 条测试语义）。

### 4.3 技能覆盖率（新增）
```
coverage = |{tag ∈ required ∩ student 且 level ≥ 1}| / |required|
```
与「等级分」正交：区分「你有几项技能」（覆盖率）和「技能够不够深」（等级分）。加权版 `Σ weight[覆盖标签]` 可作备选，默认用计数版。

### 4.4 能力等级差
```
Gap_k = max(Jik - Suk, 0)
Priority_k = Gap_k × weight_k × (1 / difficulty_k)   # 完全复现现有实现
```
排序：`priority_score` 降序，tie-break 按 `importance`（critical > important > nice_to_have）再按 `tag`，保证确定性。

### 4.5 证据可信度（新增，接入 `confidence`）
不污染冻结的 `overall_score`，只产出**并行参考分**：
```
confidence_adjusted_score = Σ wk × min(Suk/Jik, 1) × confidence_k × 100
confidence_k = 学生该标签 confidence；缺失标签 = 0.0
```
同时：`confidence < options.confidence_floor(0.3)` 的标签 → 写入 `missing_data_flags`（提示追问），**不降级、不判死**（与 `04 §2.2` 的追问语义一致）。

### 4.6 总分计算（冻结，禁止改动）
```
overall_score = Σ wk × min(Suk / Jik, 1.0) × 100     # 04 §4.2 原文
```
`overall_score` 是公共契约字段，阶段3 **不改公式**；可信度只进 `confidence_adjusted_score`（新增字段）。

### 4.7 匹配等级（新增，纯阈值映射）
```
overall_score ≥ 80  → high（高度匹配）
          60–79  → good（良好匹配）
          40–59  → fair（一般匹配）
          20–39  → weak（待提升）
          < 20   → low（低匹配）
```
hard gate 命中时按 §4.1 策略封顶。

### 4.8 缺失数据处理（确定性规则）
| 情况                                          | 处理                                                         |
| --------------------------------------------- | ------------------------------------------------------------ |
| 学生缺某 required 标签                        | `current_level=0` → 维度贡献 0（现状已覆盖）                 |
| `required_abilities` 为空                     | 返回固定空结果（现状 + 已测试 `test_empty_job_abilities_returns_fixed_schema`） |
| `evidence` 为 None                            | 不影响评分（仅审计/解释用）                                  |
| `confidence < 0.3`                            | 标记 `missing_data_flags`，不判死                            |
| `completeness < 0.5` 或 `missing_fields` 非空 | 标记 `missing_data_flags`（画像不完整），不参与评分          |
| 未映射标签                                    | `AbilityTagNormalizer.normalize_or_raise` 抛错 → Agent 层走 fallback（现状已覆盖） |

---

## 五、PathService 方案

### 5.1 职业图谱结构
- 数据源：`data/career_graph.json`（10 节点/16 边），加载后校验 `CareerGraph`（节点 ≥10、边 ≥15）。
- 关键改造（M3/M6）：给节点补 `required_abilities` 能力向量；边补 `required_new_abilities`。缺失时回退：节点能力向量 = 按 `normalized_title` 查岗位画像（Demo 3 岗位已能在图谱对齐：`ai-product-manager`/`backend-engineer`/`data-analyst`）。
- 图用 `networkx.DiGraph` 或纯 dict 邻接表（项目目前无 networkx 依赖，**建议纯 dict 实现，避免新增重依赖**）。

### 5.2 候选路径生成
- 起点：由 `StudentProfile.basic_info.target_job` 反查图谱节点（取 `level_range` 最低、或与学生当前能力最贴近的节点）；找不到就取与目标 `industry` 一致的 entry 节点。
- 目标：`JobProfile.normalized_title` 对应节点。
- 算法：从起点到目标做**受限搜索**——`DFS`（深度上限 = 节点数，去重、禁止环）取全部简单路径，再按评分取 Top-K（K=3）；图谱规模小，无需 Yen's k-shortest。无向通路时按边方向走（`vertical` 只能 `entry→junior→mid→senior→lead` 递进，`lateral` 可跨行业）。

### 5.3 路径可行性
- 规则过滤：① 边方向合法（`vertical` 等级须递增）；② `relation_type` 与边定义一致；③ 路径无环；④ 节点数 ≤ 上限（如 6）；⑤ `lateral` 边不允许连续 >2 跳（避免无意义反复横跳）。
- 不可行路径直接丢弃，不进入排序。

### 5.4 能力跨度
```
AbilityGapCost(path) = Σ_node Σ_k  Gap_k(node) × difficulty_k
                       （学生当前画像 vs 节点 required_abilities）
```
复用 `MatchService` 的标签对齐与 `difficulty` 表，避免重复实现；对路径终点节点，直接引用 `match_result.ability_gaps` 的缺口作初值（避免重复计算）。

### 5.5 时间成本
```
time_estimate_months = Σ_edge transfer_cost × MONTHS_PER_COST(如 6)
                     + Σ 关键缺口 SkillGap.estimated_effort × TIME_PER_EFFORT(如 3)
```
输出为整数月，供 `CareerStage.duration_months` 拆解；`graduation_year`/`years_of_experience` 可作校准（应届 vs 有经验），本阶段先用固定系数。

### 5.6 用户偏好
```
preference_adjustment =
  +P_industry  若路径终点 industry == basic_info.target_industry
  +P_job       若路径经过 target_job 对应节点
  +P_direction 若关系类型符合学生历史倾向（本阶段缺历史，退化为默认 0）
```
系数为常量（如 +5/+5/+0），写入常量表保证确定性。

### 5.7 目标一致性
```
target_consistency = 1.0 若终点 == 目标节点
                   = 0.5 若终点与目标同 industry 但不同岗位
                   = 0.0 否则
```
并入 `total_score` 作为乘性或加性项（建议加性：`+ target_consistency × CONSISTENCY_WEIGHT`）。

### 5.8 风险
```
risk_penalty = Σ RISK_PER_DECLINING  若路径节点能力 ∈ trend_result.declining_skills
             + RISK_PER_HARD_JUMP    若某边 required_level 跳跃 ≥ 3
             + RISK_PER_LATERAL      若 lateral 边 × LATERAL_PENALTY
```
`trend_result` 缺失时风险项退化为 0（不得虚构趋势，遵守 AGENTS.md「不虚构行业趋势」）。

### 5.9 路径评分与排序（冻结公式 + 调整项）
```
主公式（冻结，04 §5.3）：
  PathScore_base = GrowthValue − TransferCost − AbilityGapCost

total_score = PathScore_base
            + user_preference_adjustment
            − risk_penalty
            + target_consistency × CONSISTENCY_WEIGHT
```
- `growth_value` 市场溢价系数：阶段2 无该系数表 → **本阶段以 `difficulty` 作代理**（`growth_value_node = Σ level × difficulty`），并明确标记为「代理系数，待阶段4 市场数据补齐」，不虚构溢价。
- 排序：`total_score` 降序 → tie-break `time_estimate_months` 升序 → `path_id` 升序，保证确定性。
- Top-1 设为 `selected_path_id`；全部候选写入 `candidate_paths`。

---

## 六、Service 确定性计算 vs Agent 解释 的边界

> 核心红线（`04 §4.2`、`05 §3.6/§4.6`）：**数值一律 Service 算，LLM 只填文字，严禁 LLM 覆盖数值。**

| 能力                                                         | 归属                                                         | 说明                            |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------- |
| `overall_score` / `confidence_adjusted_score` / `skill_coverage` / `match_level` | **MatchService**                                             | 确定性，禁止 LLM                |
| `dimensions[]` 数值、`ability_gaps[]`（等级/缺口/优先级）    | **MatchService**                                             | 禁止 LLM                        |
| 硬性条件判定 `hard_condition_result`                         | **MatchService**                                             | 禁止 LLM                        |
| `gap_analysis[].suggestion`、`strengths` 的自然语言          | **MatchAgent（LLM）**                                        | 仅解释，数值由 Service 传入     |
| `gap_analysis[].item/status`                                 | **MatchService**（`status` 由 gap 推导）；LLM 只写 `suggestion` | 见 C-区分，避免 LLM 篡改 status |
| 路径图搜索、候选路径生成、可行性过滤                         | **PathService**                                              | 禁止 LLM                        |
| `PathScore` 全部分解项与 `total_score`、排序                 | **PathService**                                              | 禁止 LLM                        |
| `CareerStage.duration_months` / `required_abilities`         | **PathService**                                              | 由时间成本 + 缺口推导           |
| `CareerStage.objectives` / `actions` / `milestone`、`CandidatePath` 的理由文字 | **PathAgent（LLM）**                                         | 仅解释                          |
| `match_level` 的等级标签含义、匹配结论的一句话说辞           | **MatchAgent（LLM）**                                        | 不可反向修改 `match_level`      |

**MatchAgent 改造要点**（解决 C2）：
```
MatchAgent._execute:
  1. result = MatchService.calculate(student_profile, job_profile)
  2. 仅对 result.ability_gaps + result.strengths 调用 LLM 生成 suggestion / 强项说明
  3. 组装 MatchResult（数值字段来自 Service，文字字段来自 LLM）
```
**PathAgent 改造要点**：
```
PathAgent._execute:
  1. roadmap = PathService.search(student_profile, job_profile, match_result)
  2. 仅对每个 CareerStage 的 objectives/actions/milestone 与候选路径 reason 调用 LLM
  3. 组装 CareerRoadmap（数值/结构来自 Service）
```

---

## 七、Codex 实施顺序、修改文件建议与测试清单

### 7.1 建议实施顺序（每步可独立跑测试）

| 步骤 | 内容                                                         | 产出                                                         |
| ---- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| S1   | 先写 ADR：统一 `match_service.py` 命名（C1）、定 `dimensions` 粒度（C3）、`current_level=0`（C4）、PathPlan 扩展（C5）、节点能力向量（M3） | `decisions/ADR-*` + 更新 `04/05_API_CONTRACTS.md`、`03_ARCHITECTURE.md`、`06_DATA_DICTIONARY.md` |
| S2   | 新增 `schemas/match_schema.py`（MatchRequest/DimensionMatch/SkillGap/MatchResult） | 纯新增，不破坏现有                                           |
| S3   | 扩展 `MatchService`：接入 `confidence`/`importance`/`coverage`/`match_level`/`hard_gate`/`missing_data_flags`，返回 `MatchResult`（而非裸 dict） | 保持 14 条现有测试语义不变                                   |
| S4   | 重写 `MatchAgent`：调用 MatchService + LLM 只生成 `suggestion`/`strengths` | 删除内联重复逻辑                                             |
| S5   | 扩展 `CareerGraphNode/Edge` 模型 + `career_graph.json` 补能力向量（M3） | 数据 + 种子模型                                              |
| S6   | 新增 `schemas/path_schema.py`（CareerNode/Edge/CandidatePath/PathScore/CareerStage/CareerRoadmap） | 纯新增                                                       |
| S7   | 新增 `services/path_service.py`：图搜索 + 评分 + 排序 + 时间成本 + 阶段拆解 | 阶段3 核心                                                   |
| S8   | 重写 `PathAgent`：调用 PathService + LLM 只生成阶段文字/理由 | 删除写死 3 阶段                                              |
| S9   | `CareerState` 增加 `career_roadmap` 字段（并行于 `path_plan`）；orchestrator 顺序不变 | 需同步 `apply_agent_data` 白名单                             |

### 7.2 修改/新增文件清单

| 文件                                                         | 动作                        | 风险               |
| ------------------------------------------------------------ | --------------------------- | ------------------ |
| `docs/a02/04_API_CONTRACTS.md`、`05_AGENT_CONTRACTS.md`、`03_ARCHITECTURE.md`、`06_DATA_DICTIONARY.md` | 更新（配合 ADR）            | 冻结契约，必须 ADR |
| `decisions/ADR-*`（新建）                                    | 新增                        | —                  |
| `backend/app/schemas/match_schema.py`                        | 新增                        | 低                 |
| `backend/app/schemas/path_schema.py`                         | 新增                        | 低                 |
| `backend/app/schemas/__init__.py`、`services/__init__.py`    | 新增                        | 低                 |
| `backend/app/services/match_service.py`                      | 扩展                        | 中（勿改冻结公式） |
| `backend/app/services/path_service.py`                       | 新增                        | 中                 |
| `backend/app/agents/match_agent.py`                          | 重写                        | 中                 |
| `backend/app/agents/path_agent.py`                           | 重写                        | 中                 |
| `backend/app/models/a02_models.py`                           | 扩展 `CareerGraphNode/Edge` | 中（种子数据契约） |
| `backend/app/data/career_graph.json`                         | 补节点能力向量              | 中                 |
| `backend/app/orchestrator/career_state.py`                   | 加 `career_roadmap`         | 低                 |
| `backend/tests/test_match_service.py`                        | 扩展                        | —                  |
| `backend/tests/test_path_service.py`（新）                   | 新增                        | —                  |
| `backend/app/agents/tests/test_match_agent.py`、`test_path_agent.py`（新） | 新增                        | —                  |

### 7.3 测试清单

**MatchService（扩展现有 + 新增）**
- 回归：现有 14 条 `test_match_service.py` 全部保持通过（尤其 `overall_score` 数值不变）
- 新增：
  - `confidence_adjusted_score` 随 `confidence` 单调变化，且 `overall_score` 不变
  - `skill_coverage` 计算正确（全命中=1，全缺失=0，部分命中=加权/计数）
  - `match_level` 阈值边界（79.99/80.0、59.99/60.0 等）
  - hard gate：critical 缺失在 `lenient` 封顶、`strict` 判 `passed=false`
  - `missing_data_flags`：低 confidence、低 completeness、缺失字段分别触发
  - 确定性：同输入 10 次结果逐字节一致（沿用现有 `test_same_input_is_exactly_deterministic` 风格）
  - 失败用例：非法 `required_level`、权重和≠1、未映射标签、难度非法

**PathService（新建）**
- 图加载：节点/边数量校验、环检测、孤立节点报错
- 候选路径：起点→目标存在 ≥1 条简单路径；无通路返回空 `candidate_paths`
- 可行性：`vertical` 等级倒挂被过滤、连续 >2 `lateral` 被过滤、含环被过滤
- 评分：`PathScore` 各分项单调性（growth 越高分越高、gap 越大分越低）；排序 tie-break 确定性
- 时间成本：`duration_months` 正整数且阶段和 ≈ `time_estimate_months`
- 缺失数据：无 `trend_result` 时 `risk_penalty=0`；节点无能力向量时回退岗位画像
- 代理系数：确认 `growth_value` 用 `difficulty` 代理并带显式标记

**MatchAgent / PathAgent（新建，含 success + failure 两态）**
- 成功：LLM client 假件（double）返回合法结构 → Agent 只生成文字、数值与 Service 输出一致
- LLM 失败：触发 fallback → 数值仍为 Service 计算值，文字用固定模板
- 数值红线：断言 Agent 无法改写 Service 数值（构造恶意 LLM 输出验证被拒/被覆盖）
- 隐私：日志 `input_summary/output_summary` 无手机号/邮箱/身份证/完整简历

---

### 需要你拍板的 4 个决策点

1. **C3 — `dimensions[]` 按标签还是按聚合维度？** 我建议按标签（+`category` 字段供前端聚合），改动最小。
2. **M4 — 硬性条件是否要给 `JobProfile` 加学历/年限要求字段？** 加则需 ADR；本阶段可先只做「critical 能力缺失」硬门。
3. **C5 — `CareerRoadmap` 是扩展冻结 `path_plan`，还是新增并行 `career_roadmap` 字段？** 我建议并行新增，不破坏现有消费者。
4. **`growth_value` 市场溢价系数**：阶段2 无此数据，本阶段用 `difficulty` 代理是否可接受（明确标注为代理、不虚构）？

---

需要我把这份规格落盘为 `docs/a02/14_STAGE3_SPEC.md`（或写入 `.hermes/plan` 供 Codex 读取）吗？另外，如果你确认了上面 4 个决策点，我可以据此把「S1 的 ADR 草稿」也一并起草好。