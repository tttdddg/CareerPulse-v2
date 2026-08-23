# D4 阶段4实施规格（训练 / 资源推荐 / 反馈 Service）

## 前置结论：阶段3现状核查结果

| 核对项                                                 | 现状                                                                                                                                                                                   | 位置                                                    |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| TrainingService / ResourceService / FeedbackService | ❌ 均不存在，本任务新建                                                                                                                                                                         | `backend/app/services/`                               |
| 训练题库                                                | ✅ 10 题、3 类（remote_collaboration×4 / ai_office_task×3 / cross_role_communication×3），每题含 evaluation_criteria + reference_answer + target_abilities                                     | `backend/app/data/training_tasks.json`                |
| 学习资源                                                | ✅ 12 条（course/book/practice/certificate），带 target_ability 与内部标记 demo_only                                                                                                            | `backend/app/data/resources.json`                     |
| Mock 参照系                                            | `_generate_and_score_training`：题库过滤选题、评分 `40 + len//4` 封顶 90、ability_updates 恒 0；`_recommend_resources`：gaps 空全推前 10、否则 target_ability 命中；`_save_feedback`：不真存（feedback_saved=false） | `backend/app/tools/mock_tools.py`                     |
| Mock Agent                                          | TrainingAgent 硬编码 1 题；FeedbackAgent 读 student_input.ratings 产出占位结果                                                                                                                   | `agents/training_agent.py`、`agents/feedback_agent.py` |
| 标签体系                                                | ✅ 48 个统一标签，题库/资源引用标签全部合法                                                                                                                                                             | `data/ability_tags.json`                              |
| 冻结契约                                                | TrainingTask/TrainingScore（04 §6）、FeedbackResult/GrowthArchive（04 §7）、工具 Schema（13 §5/6/7）、表定义（06 §2.5-2.9）                                                                          | `docs/a02/`                                           |
| 现有回归                                                | MatchService 23 / PathService 20 / Agents 19 / LLM Client 12 等共 94 项                                                                                                                 | `backend/tests/`、`agents/tests/`                      |

## 一、任务范围与允许修改

**允许修改**：`backend/app/services/training_service.py`、`resource_service.py`、`feedback_service.py` + `backend/tests/test_training_service.py`、`test_resource_service.py`、`test_feedback_service.py`。

**明确不在范围**：Agent 层、Schema、Orchestrator、API/路由、前端、数据文件、契约文档（后置统一处理）。三个 Service 以裸 dict 输出，结构对齐冻结契约，不新建 Pydantic Schema。

**可选项裁决**：mock_interview（模拟面试）**本轮放弃纳入**——契约/数据/校验多处锁 3 类枚举（模型 Literal、init 校验、表 CHECK），纳入需扩权多个文件；已完成全链路兼容分析并记录于"已知边界"，后续需要时按 A2 方案（题库加题 + 模型 Literal + init required_types 集合各加一个元素）扩权启用。

## 二、TrainingService 规格

### 2.1 训练题生成（generate）

- 输入：`training_type`（3 类枚举）+ 可选 `ability_gaps`（来自 `match_result.skill_gaps[].dimension`，已按 priority 排序）。
- 选题规则（确定性，三层）：
  1. 题库按类型过滤；
  2. 按 `target_abilities` 与缺口标签交集数降序；
  3. 交集相同取 `training_id` 字典序第一。
- 非法类型（非 3 类）→ error 标志（fail-safe，不抛异常）。
- 某类题库取空 → error 标志（不做模板兜底）；`init_a02_data.py` 数据关卡强制"题库必须恰好覆盖 3 类声明"，某类取空即数据不合法，如实报错。
- 输出结构对齐 13 §5.2：`mode=generate / training_id / type / title / scenario / task_description / evaluation_criteria[] / target_abilities / reference_answer`。

### 2.2 评分（score）——主路径：Agent 语义解读 + Service 确定性合成

**链路形态**（三层回调）：

```
TrainingAgent（LLM）解读 user_answer → 结构化判定信号（agent_analysis）
TrainingService.score(training_id, user_answer, agent_analysis) → 确定性合成数值
TrainingAgent（LLM）基于数值+判定写评语文字（未来 §13.4 任务）
```

**判定信号格式与约束**：

```json
{
  "agent_analysis": {
    "dimensions": [
      {"dimension": "信息完整", "coverage": "fully|mostly|partial|barely|missing",
       "reason": "一句话依据"}
    ]
  }
}
```

| #   | 约束                                                           | 目的                                                                                 |
| --- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| 1   | `coverage` 五档枚举：fully/mostly/partial/barely/missing          | 语义档位是 LLM 可靠能力边界，封堵连续打分幻觉                                                          |
| 2   | dimensions 与题目 evaluation_criteria **一一对应**（按 dimension 名比对） | 防漏维/多维；缺失维度按 missing 计 + flag `incomplete_analysis:<dimension>`（不重归一——"没答"不能从分母洗掉） |
| 3   | reason 必填、≤200 字、过隐私校验（禁邮箱/手机/身份证）                           | 评语素材 + 日志安全                                                                        |
| 4   | **禁止任何数值字段**（score/total/level 一律不得出现）                       | 红线：LLM 只出判定，不出数值；违反 → 拒信号走兜底                                                       |

**合成算法（确定性）**：

```
coverage 映射：fully=1.0 / mostly=0.75 / partial=0.5 / barely=0.25 / missing=0.0
内容维度分：c_k = coverage_k × 100
长度修正：user_answer 去空白后
  空 → 全维度 0 分 + flag empty_answer
  <20 字 → c_k 封顶 80（短答即使判定覆盖也不给满分）
dimension_score_k = round(c_k, 2)
total_score = Σ w_k × dimension_score_k          # 与 MatchService 同构：自底向上加权合成
```

**长度定位**：不再是保底分（杜绝"长空话高分"），只做最小门槛（空=0、<20 字封顶 80）。

### 2.3 评分兜底路径（无 LLM / 信号校验失败时）

- 素材：题库现成 `dimension` 字段（维度名），**不建关键词表**。
- 命中：维度名按 2 字滑动窗口切（"信息完整"→ 信息/息完/完整），回答包含任意窗口即命中（**不严格命中**：近似表述也响应）。
- 规则：命中率 = 命中窗口数 / 窗口总数；维度分 = 命中率 × 100；**否定拦截**：命中窗口前 3 字符含"无/未/没/不/缺少"不计命中；长度修正与主路径一致（空=0+flag、<20 字封顶 80）；total = Σ w × 维度分（同构）。
- 明确区别：兜底路径刻意不用 reference_answer（参考答案是面向 LLM 语义解读的素材，兜底是字面匹配，不混用）。

### 2.4 能力更新项（ability_updates）

```
total_score ≥ 80.0 → 训练 target_abilities 每个 level_change = +1
40.0 ≤ total_score < 80.0 → 0
total_score < 40.0 → -1
```

`level_change` 是建议增量，不直接改写画像；画像落库属成长档案/后续环节。

### 2.5 fail-safe 清单

非法 training_id → error；非法类型 → error；user_answer 含邮箱/手机/身份证 → error（隐私前移，与 Match 先例一致）；信号校验失败 → 拒信号走兜底；兜底也无素材 → 最低保底值。

## 三、ResourceService 规格

- 输入：`ability_gaps`（标签数组，已按 priority 序）+ 可选 `target_job`（当前不参与）。
- 标签归一：**必须共用 `AbilityTagNormalizer`**（strip+lower+别名表），禁止各写各的（D3 教训：英文/空格标签落空）。
- 匹配：`target_ability` normalize 后与 gap 标签精确匹配。
- 无 gaps 输入 → 推荐全部资源（resource_id 升序，上限 10，与现 Mock 行为一致）。
- 有 gaps → **跟随 gaps 顺序**返回（组内 resource_id 升序）；无命中 gap → flag `no_resource_for_tag:<tag>`（不虚构）。
- job_resources：无岗位资源数据源 → 恒空数组 + flag `job_resources_unavailable`。
- certificate_suggestions：命中资源中 type=certificate → 输出其 `target_ability`；无 → 空数组。
- 非法标签（不在 48 标签内）→ 跳过该 gap + flag `unknown_tag:<tag>`（fail-safe，不炸整单）。
- 输出字段：**剔除 demo_only / resource_id**（契约 13 §6.2 与 06 §3.6 均未定义这两个字段，属数据/模型层内部标记；演示模式水印由工具层 envelope 负责）。
- 输出结构对齐 13 §6.2：learning_resources[{title,type,url,target_ability,description}] + job_resources[] + certificate_suggestions[]。

## 四、FeedbackService 规格

### 4.1 输入与职责

- 输入：`session_id`（必填）/ `user_id`（必填）/ `satisfaction`（必填 1-5）/ path/training/resource_rating（可选 1-5）/ `comments`（可选）/ `skill_gaps`（可选，含 tag/priority）/ `abilities`（可选，快照用）。
- **调用方传参，Service 不碰 state**（03 职责边界：Service 独立层，与 Match/Path Service 一致）。
- 三动作：保存反馈 → 对称调权 → 更新成长记录。纯确定性，不调 LLM。

### 4.2 保存

- 校验：satisfaction 缺失/越界/非整数 → error；全部评分缺失（05 §6.4 前置）→ error；user_id 缺失 → error。
- comments 过隐私校验（邮箱/手机/身份证 → 拒绝）。
- 存储：Service 内存 dict（session_id → 反馈记录），`feedback_saved=true`。

### 4.3 对称调权（README §13.2"反馈基础调权"）

| 反馈                  | 动作                                                       |
| ------------------- | -------------------------------------------------------- |
| training_rating ≤ 2 | 对应能力（训练 target_abilities ∩ 缺口）priority 升 1 级（数值 -1，下限 1） |
| training_rating ≥ 4 | 对应能力 priority 降 1 级（数值 +1，上限 = 缺口总数 N）——**缓和通道**         |
| = 3                 | 不调                                                       |
| satisfaction ≤ 2    | 不硬调权（全局不满无能力指向，仅标记）                                      |
| 能力不在缺口列表            | 不调（信号无对象不编造）                                             |

输出 `updated_priorities[{tag, old_priority, new_priority, reason}]`。

**自平衡论证**：① 单次反馈只对一道题（target_abilities 1-2 个）→ 触发面天然受限，不存在"一次全升到 1"；② 好评降权提供回落；③ 会话内有效、跨会话不累积（内存无持久化，新会话 MatchService 重算 priority）→ "长期单调收敛全为 1"在现有流程下不成立。调权语义 = 会话内短期信号，不是跨会话档案。

### 4.4 成长记录（GrowthArchive 快照）

- 输出对齐 13 §7.2：`growth_snapshot{competitiveness_score, completed_trainings, completed_phases, growth_trend}`。
- `competitiveness_score` = 最近一次 `match_result.overall_score`——**近似值**：画像侧竞争力加权算法未实现（D2 起占位 0.0），以匹配度近似并在文档标注，非真实竞争力算法产出。
- `completed_trainings / completed_phases` 由调用方传入（Service 不跨模块追踪），缺省 0。
- `growth_trend`：仅三值 improving/stable/declining（04 §7.2 契约枚举 + 06 §2.7 CHECK 双重锁死、NOT NULL 必填）；首次快照（无历史可对比）→ `stable`（恰好等于表 DEFAULT），+ 标记"首次快照"，不臆断涨跌；有历史 → 与上次快照对比（competitiveness/训练完成数升→improving、降→declining、平→stable）。
- 存储：Service 内存 dict（user_id → 上次快照），与当前全项目落地一致（D3 约定"持久化用内存，暂缓迁移"）；06 §2.7/§2.9 表定义是持久化阶段迁移蓝图，本轮不落库。

## 五、红线与职责边界

| 能力                                            | 归属                                   |
| --------------------------------------------- | ------------------------------------ |
| 训练生成选题、评分合成、total/维度分/ability_updates、调权、快照数值 | **三 Service（确定性）**                   |
| 训练维度判定信号（五档 + 依据文字）                           | **Agent（LLM）**——只出枚举判定，**禁任何数值字段**   |
| 评语文字（训练建议、反馈 reason 措辞等）                      | Service 模板兜底；LLM 增强属 §13.4 Agent 任务  |
| 演示模式水印、envelope                               | 工具层（阶段5）                             |
| 不虚构原则                                         | 无题/无资源/无数据源/无历史 → error/flag，一律不造假数据 |

## 六、实施顺序与文件清单

| 步骤  | 内容                                                 | 负责人          |
| --- | -------------------------------------------------- | ------------ |
| S1  | 规格设计（本文件）                                          | Hermes       |
| S2  | 实现 TrainingService + test_training_service.py      | Codex        |
| S3  | 审查训练评分（主路径信号约束/兜底/五档/红线）                           | Hermes       |
| S4  | 实现 ResourceService + test_resource_service.py      | Codex        |
| S5  | 审查资源推荐（归一/无资源/字段剔除）                                | Hermes       |
| S6  | 实现 FeedbackService + test_feedback_service.py      | Codex        |
| S7  | 审查反馈（对称调权/快照/隐私）                                   | Hermes       |
| S8  | 全量回归（现有 94 项不破坏）+ 本地端到端（Mock Agent 调用三 Service 验证） | Codex/Hermes |
| S9  | 阶段4最终验收（全量测试证据 + 隐私 + 确定性 + 边界）                    | Hermes       |

文件：新增 `services/{training,resource,feedback}_service.py`、`tests/test_{training,resource,feedback}_service.py`，其余零改动。

**测试清单要点**：

- Training：三类选题确定性/缺口匹配/非法类型/题库取空；主路径注入固定五档信号断言合成数值；兜底（2 字窗口命中/否定拦截/空答/<20字封顶80）；ability_updates 阈值边界（79.9/80.0、39.9/40.0）；信号校验（多维/缺维/数值字段/隐私）；隐私；同输入 10 次逐字节一致。
- Resource：gaps 空全推/有 gaps 跟随顺序/无命中 flag/非法标签跳过/job_resources 空 + flag/证书建议/字段剔除/归一命中（英文/空格）/上限 10/确定性。
- Feedback：保存校验（缺失/越界/全空/user_id 缺）/对称调权（差评升/好评降/中性不动/缺口外不调/上下限）/快照（首次 stable/有历史对比/completeness 近似标注)/隐私/内存存储行为/确定性。

## 七、已拍板决策点记录

1. mock_interview 暂时搁置（A2 全链路分析见"已知边界"）。
2. 训练评分 = Agent 五档语义判定 + Service 确定性合成（三层回调：解读→合成→评语）。
3. 兜底不用 reference_answer；素材 = dimension 名 2 字窗口不严格命中 + 否定拦截。
4. 长度仅做最小门槛（空=0、<20 字封顶 80），不做保底。
5. ability_updates 阈值：≥80→+1 / 40-79→0 / <40→-1。
6. 资源：gaps 空全推、跟随顺序、certificate 输出 target_ability、剔除 demo_only/resource_id。
7. 反馈：对称调权（差评升/好评降/中性不动）、satisfaction 低不硬调、缺口中无对象不调。
8. competitiveness_score 用匹配分近似并标注；growth_trend 仅三值、首次 stable。
9. 存储：三 Service 内存实现；持久化以 06 表为蓝图留待后续。
10. 输出一律裸 dict 对齐冻结契约，不新建 Schema。

## 八、已知边界与后续事项

- **mock_interview 扩展预案（A2 全链路分析）**：纳入需动 `models/a02_models.py`（TrainingTask.type Literal 加值）、`scripts/init_a02_data.py`（required_types 集合加元素）、题库加题（target_abilities 须在 48 标签内、evaluation_criteria 满分和=100/权重和=1.0）、持久化时 V001 CHECK 放宽（V003）；契约文档 04/05/13/06 枚举同步走 ADR。其余层（mock_tools 自动兼容、编排/状态/前端零影响）已核验。
- **持久化**：06 §2.5-2.9 表已冻结（training_records / learning_plans / growth_archives / agent_logs / user_feedback），D3 约定内存落地，重启丢失属已知设计；持久化阶段按 DDL 迁移。
- **Agent 层（§13.4 任务）**：TrainingAgent/FeedbackAgent 真实化、training_schema/feedback_schema、判定信号 prompt（score.txt）、评语 LLM、CareerState 接入、工具参数校验。
- **平台工具注册**：阶段5（百宝箱正式集成），本轮仅 HTTP API 侧无动作。
- **维度判分增强**：主路径依赖 LLM；若未来无 LLM 场景需要更强兜底，可给题库加 keywords 字段（扩权）或启用 reference_answer 短语匹配（当前刻意不用）。

---

本文件为阶段4设计规格。实施按 S1-S9 由 Codex 执行，Hermes 审查与验收。


