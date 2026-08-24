# D4 训练、资源推荐与反馈Service 验收报告

## 结论

阶段4交付**验收通过**。三个确定性 Service（TrainingService / ResourceService / FeedbackService）全部实现并测试完备：全量回归 **155 passed / 85 subtests**（D3 基线 94 项零破坏，新增 61 项全绿），端到端独立消费验证 16 项检查全部通过，compileall 无错误。实现全程遵守项目红线：数值一律 Service 计算、不调 LLM、不碰 state、fail-safe 返回、确定性输出、隐私前移。设计规格、三次分步审查、最终验收证据均在本报告汇总。

## 一、交付总览

| 项 | 内容 |
|---|---|
| 新增文件 | `backend/app/services/training_service.py`（383 行）、`resource_service.py`（100 行）、`feedback_service.py`（247 行） |
| 新增测试 | `backend/tests/test_training_service.py`（29 项）、`test_resource_service.py`（12 项）、`test_feedback_service.py`（20 项，含 14 subtests） |
| 测试结果 | 三个 Service 单测 61 项全绿；全量 `pytest tests/ app/agents/tests/` = 155 passed / 85 subtests |
| 改动范围 | 仅上述 6 个文件；Agent / Schema / Orchestrator / 工具 / 数据 / 契约文档 / 前端 / 数据库零改动 |
| 输出契约 | 裸 dict 对齐冻结契约（13 §5.2/§5.3、§6.2、§7.2），不新建 Pydantic Schema |

## 二、三个 Service 交付审查（Step 2/4/6 合成）

### 2.1 TrainingService —— 审查通过

**核心设计**：训练题生成（三类选题：类型过滤 → 缺口交集优先 → training_id 字典序）+ 评分双路径。

**主路径（LLM 语义判定 + Service 确定性合成）**：
- 判定信号五档枚举 `fully/mostly/partial/barely/missing` → 映射 100/75/50/25/0；
- 信号约束四项全落实：五档枚举校验、维度与 evaluation_criteria 一一对应（缺维按 missing + `incomplete_analysis` flag，无关维度拒收）、reason 必填 ≤200 字过隐私、**全信号递归禁数值字段**（违反拒收走兜底）；
- 合成 `total = Σ w×维度分`（与 MatchService 同构），round 2；
- 长度仅做最小门槛：空回答 → 全 0 + `empty_answer` flag；<20 字 → 封顶 80（不做保底分，杜绝长空话高分）。

**兜底路径（无 LLM/信号拒收）**：题库现成 `dimension` 名 2 字滑动窗口不严格命中 + 否定拦截（命中前 3 字符含"无/未/没/不/缺少"不计命中）；刻意不用 reference_answer（面向 LLM 语义的素材不混用于字面匹配）。

**ability_updates**：total ≥80 → +1 / 40≤total<80 → 0 / <40 → -1（作用于 target_abilities，实测 80.0/78.75/40.0/32.5 边界）。

**fail-safe**：非法类型、某类题库取空、未知 training_id、回答含隐私 → 全部 error 返回不抛异常。

### 2.2 ResourceService —— 审查通过

**核心设计**：能力缺口 → 学习资源匹配推荐。

- **AbilityTagNormalizer 同模块复用**（唯一归一入口，禁止自写匹配，防英文/空格/别名标签落空）；
- 空 gaps → 全推（resource_id 升序，上限 10）；有 gaps → 跟随缺口顺序（组内 resource_id 升序）；
- 无命中 gap → `no_resource_for_tag:<tag>`；非法标签/非字符串 → 跳过 + `unknown_tag:<tag>`（fail-safe 不炸整单）；
- job_resources 无数据源 → 恒空 + `job_resources_unavailable`；certificate_suggestions 输出命中证书资源的 target_ability（如 PMP）；
- 输出剔除 `demo_only`/`resource_id`（契约 13 §6.2 与 06 §3.6 均未定义，属数据/模型层内部标记）。

### 2.3 FeedbackService —— 审查通过

**核心设计**：反馈保存 + 对称调权 + 成长快照，全参数输入（13 个入参），不碰 state。

- **校验**：session_id/user_id 非空字符串、satisfaction/ratings 排除 bool 须 1-5 整数、comments 过隐私正则（与 match_service 逐字一致）；
- **对称调权**（会话内短期信号）：差评 training_rating≤2 → 相交缺口 priority 升 1（下限 1）；好评 ≥4 → 降 1（上限 = 缺口总数 N）；中性 3/None → 不动；目标不在缺口 → 不动；satisfaction≤2 → 整体不调权 + flag。**自平衡论证**：单次反馈只对 1-2 个 target_abilities（触发面受限）+ 好评回落通道 + 内存无跨会话累积（新会话 MatchService 重算 priority）——不存在单调收敛全为 1 的路径；
- **成长快照**：competitiveness_score = 传入最近匹配分（None → 0.0 + `competitiveness_unavailable`，规格标注近似语义）；growth_trend 仅三值（契约 + 06 DDL CHECK 双重锁死），首次稳定 + `first_growth_snapshot` flag，有历史按竞争力/完成数升降平判定；
- 内存存储（`_feedbacks`/`_growth` dict）+ `get_feedback`/`get_growth` 只读接口（深/浅拷贝防篡改）。

### 2.4 三次审查观察项处置汇总

| 来源 | 观察项 | 处置 |
|---|---|---|
| Step2-1 | 字符串含英文 score/total/level 字样也拒信号（保守方向，比规格严） | 归档不处理（保守可接受） |
| Step2-2 | 信号重复维度不拒收（规格未定义项） | 归档不处理 |
| Step2-3 | Step1 报告"全量回归 101"实际全量 123（表述不全，数字真实） | 本文档按全量 155 统一修正 |
| Step4-1 | 未知标签资源两分支行为不一致（真实数据不触发） | 归档不处理 |
| Step4-2 | 证书建议不受资源条数上限截断（语义更合理） | 归档不处理 |
| Step6-1 | abilities 参数存储多于输出（任务卡授权"可存可用"） | 归档不处理 |
| Step6-2 | satisfaction≤2 完全跳过调权（含好评，与规格"不硬调"一致） | 归档不处理 |
| Step7 | 端到端脚本 2 处断言口径错误（脚本自省修正，服务零改动） | 已处置 |

## 三、最终验收证据

### 3.1 全量回归（独立运行确认）

```
cd backend && python -m pytest tests/ app/agents/tests/ -q
155 passed, 85 subtests passed
```

| 分组 | 数量 |
|---|---|
| D3 基线（Match 23 / Path 20 / Agents 29 / 其余 22） | 94 |
| TrainingService 新增 | 29 |
| ResourceService 新增 | 12 |
| FeedbackService 新增 | 20 |
| **合计** | **155** |

### 3.2 端到端独立消费（验收脚本，16 项检查，跑完即删）

| 检查项 | 结果 |
|---|---|
| generate 三类各一次：mode/type/9 必填字段/权重和 1.0 | PASS |
| generate 缺口交集优先（远程协作类选中 train-remote-003） | PASS |
| score 五档信号合成：真实权重期望 total=78.75 逐值吻合 | PASS |
| score ability_updates 阈值分档（78.75 → 0，符合 [40,80) 档） | PASS |
| score 兜底窗口命中（维度名全覆盖 → 100.0） | PASS |
| score 隐私拒绝（邮箱 → error） | PASS |
| resource 空 gaps：10 条截断 + job flag + PMP 建议 | PASS |
| resource 有 gaps：顺序输出 + 无命中/未知标签双 flag | PASS |
| resource 字段剔除（仅 5 契约字段） | PASS |
| feedback 差评升权 + 下限 1 + reason | PASS |
| feedback 快照二次趋势 improving + 竞争力分 72.0 | PASS |
| feedback 隐私拒绝（comments 邮箱 → error） | PASS |
| 确定性抽查（training/resource 同输入逐字节一致） | PASS |

### 3.3 红线核对

- **数值一律 Service**：五档判定信号、合成公式、调权、快照全部确定性代码计算——LLM 仅在未来 Agent 层出判定/文字，Service 层零 LLM 依赖；
- **不碰 state**：三 Service 全参数输入，无任何 agent/orchestrator/career_state import；
- **fail-safe**：error 标志返回（非法类型/题库取空/未知 id/隐私/校验失败），无运行期意外异常；
- **确定性**：排序规则定死、无随机/集合顺序依赖、round 2，同输入逐字节一致（含跨新实例）；
- **隐私**：email/phone/身份证正则三 Service 一致（沿用 match_service 模式），评分回答、信号 reason、comments 全部前移拒绝；
- **不虚构**：无题/无资源/无数据源/无历史 → error 或 flag，一律不造假数据。

### 3.4 范围与边界确认

按规格与任务卡：仅新增 3 Service + 3 测试；Agent/Schema/Orchestrator/工具/数据文件/契约文档/前端/数据库零修改；未落库（内存存储，06 表为持久化阶段蓝图）；mock_interview 未纳入（预案见下文）。

## 四、消费链路提示（供 Agent 接入参考）

这是后续阶段（README §13.4：TrainingAgent/FeedbackAgent 真实化）必须遵守的接口事实，比规格更具体：

1. **TrainingService.generate**：`training_type` 必须是三枚举之一，否则 error；`ability_gaps` 直接取 `match_result.skill_gaps[].dimension`（已按 priority 序，直接顺延即可）；
2. **TrainingService.score 主路径信号格式**：

```json
{"dimensions": [{"dimension": "维度名", "coverage": "fully|mostly|partial|barely|missing", "reason": "依据（≤200字，禁隐私）"}]}
```

Agent 层**禁止输出任何数值字段**（score/total/level 的键名或数值都会被拒收走兜底）；维度必须与题面 evaluation_criteria 一一对应；
3. **ResourceService.recommend_resources**：`ability_gaps` 同上取 `skill_gaps[].dimension`；
4. **FeedbackService.save_feedback**：调权需传 `skill_gaps`（含 dimension/priority）+ `training_target_abilities`；快照 `overall_score` 传最近 match_result 总分（近似语义，规格有标注）；satisfaction 必填、其余 rating 可选；
5. 三个 Service 均支持注入数据构造（`tasks=`/`resources=` 参数）用于隔离测试，生产走默认数据文件。

## 五、风险与后续建议

1. **观察项遗留**（均在"不予处理"归档）：信号重复维度不拒收、字符串含英文 score 字样拒信号偏严——若未来 Agent 层信号质量不稳定，建议在 Agent 接入阶段重新评估；
2. **mock_interview 启用条件**（A2 预案已记录在规格"已知边界"）：需动 `models/a02_models.py`（TrainingTask.type Literal 加值）+ `scripts/init_a02_data.py`（required_types 集合加元素）+ 题库补题（target_abilities 必须在 48 标签内、evaluation_criteria 满分和=100/权重和=1.0）+ 持久化时 V001 CHECK 放宽（V003）+ 契约文档 04/05/13/06 枚举同步（ADR）；本轮不涉及，届时按预案执行；
3. **调权语义边界**：优先级调整是**会话内短期信号**（跨会话不累积、新会话 MatchService 重算）——后续若接入持久化（06 的 growth_archives/user_feedback 表），需重新明确调权结果是否跨会话生效，那是持久化阶段的设计决策，不在本轮；
4. **训练评分主路径强依赖 LLM 判定质量**：兜底（窗口命中）只是无 LLM 时的低配——Agent 接入时判定 prompt 的设计（五档语义、reason 约束）是评分质量的关键，README §13.4 任务应优先落实；
5. **持久化前检查**：三 Service 的内存存储重启即丢（与 CareerOrchestrator._sessions 同款已知边界）；06 表 DDL 已冻结，持久化阶段按 DDL 迁移即可，无结构障碍。

## 六、决策记录（本轮已拍板）

1. mock_interview 本轮放弃，A2 预案归档；
2. 训练评分 = LLM 五档判定信号 + Service 确定性合成（数值红线保持）；
3. 兜底 = dimension 名 2 字窗口不严格命中 + 否定拦截，不用 reference_answer；
4. 长度仅最小门槛（空=0、<20 字封顶 80），不做保底；
5. ability_updates 阈值 ≥80→+1 / 40-79→0 / <40→-1；
6. 资源：空 gaps 全推、跟随缺口顺序、certificate 输出 target_ability、剔除 demo_only/resource_id；
7. 反馈：对称调权（差评升/好评降/中性不动）、satisfaction≤2 不硬调、缺口外不调；
8. 快照 competitiveness 用匹配分近似并标注；growth_trend 仅三值；
9. 三 Service 内存存储；输出裸 dict 对齐契约，不新建 Schema。

---

验收动作：规格对照（红线/边界/决策点）、三次分步审查合成、全量回归独立运行（155/85）、端到端独立脚本（16 项，跑完删除）。阶段4 交付完毕，可进入下一阶段任务（README §13.4 Agent 层 / 平台接入）。