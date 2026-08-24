# TrainingService 实现完成报告

TrainingService（训练题生成 generate + 评分 score，主/兜底双路径 + ability_updates）已实现并通过 29 项单元测试；全量回归无破坏、compileall 通过。输出为裸 dict 对齐 13 §5.2/§5.3，不调 LLM、不 import state/agent、fail-safe（error 用返回值不抛异常）、全程确定性（round 2 + 定序）。

---

## 修改文件

| 文件                                         | 动作     | 行数  | 说明                                 |
| ------------------------------------------ | ------ | --- | ---------------------------------- |
| `backend/app/services/training_service.py` | **新建** | 384 | 1 个 Service 类 + 6 个模块级私有函数，零改动其他文件 |
| `backend/tests/test_training_service.py`   | **新建** | 309 | 29 个测试方法（pytest 收集 29 项）           |

## Diff 摘要（新增文件 API 面）

### 模块常量（集中阈值，无魔法数字）

| 常量                                   | 值                                                                                              | 用途                 |
| ------------------------------------ | ---------------------------------------------------------------------------------------------- | ------------------ |
| `TRAINING_TYPES`                     | 3 类元组                                                                                          | generate 类型白名单     |
| `COVERAGE_LEVELS`                    | fully/mostly/partial/barely/missing                                                            | 信号五档               |
| `COVERAGE_SCORE`                     | {fully:1.0, mostly:0.75, partial:0.5, barely:0.25, missing:0.0}                                | 合成映射表              |
| `SHORT_ANSWER_LENGTH_THRESHOLD`      | 20                                                                                             | <20 字触发封顶          |
| `SHORT_ANSWER_SCORE_CAP`             | 80.0                                                                                           | 短答封顶值              |
| `MAX_REASON_LENGTH`                  | 200                                                                                            | 信号 reason 长度上限     |
| `NEGATION_WINDOW_RADIUS`             | 3                                                                                              | 否定拦截向前 3 字符        |
| `NEGATION_WORDS`                     | 无/未/没/不/缺少                                                                                     | 否定词表               |
| `ABILITY_UPDATE_UPGRADE_THRESHOLD`   | 80.0                                                                                           | ≥80 → +1           |
| `ABILITY_UPDATE_DOWNGRADE_THRESHOLD` | 40.0                                                                                           | <40 → -1，40~80 → 0 |
| `ERR_*`（4 个）                         | unsupported_training_type / no_training_task_for_type / training_not_found / privacy_violation | error code         |

### 公开 API

```python
TrainingService(training_tasks_file=None, tasks=None)
    # 构造注入 data 源：文件路径或直接 tasks 列表（测试用）；构造期建 _tasks_by_id / _tasks_by_type 索引
generate(training_type: str, ability_gaps: list[str] | None = None) -> dict
score(training_id: str, user_answer: str, agent_analysis: dict | None = None) -> dict
```

### 内部协作函数（评审/接入关键）

```python
_validate_signal(agent_analysis, criteria) -> dict | None
    # None = 无信号；{"valid":True,"coverage_by_dim":...,"flags":[缺失维 flag]}
    # {"valid":False,"problem_flags":[agent_analysis_rejected:<code>]} = 拒收走兜底
_synthesize_main(criteria, coverage_by_dim) -> list[float]      # 主路径 c_k = coverage×100
_synthesize_fallback(criteria, answer_text) -> list[float]      # 兜底窗口命中率
_apply_length_correction(dim_scores, answer_text, answer_empty) # 就地修正：空=0 / <20=min(80)
_windows(dimension) -> list[str]   # 2 字滑动窗口，dict.fromkeys 去重保序
_window_hit(answer, window) -> bool  # re.finditer + 前 3 字符否定拦截（任一未被否定即命中）
_signal_has_numeric_fields(value) -> bool  # 递归：键名含 score/total/level 或任何数值 → True
_build_score_output(...) -> dict  # 组装 mode=score 输出 + data_quality_flags
（模块级）_comment / _overall_comment / _improvement_suggestions / _ability_updates
```

---

## 关键设计说明

### generate 选题（三层确定性排序）

```
① 题库按类型过滤
② target_abilities ∩ ability_gaps 交集数降序
③ 交集相同 training_id 字典序第一（min(key=(-overlap, training_id))）
```

- 非法类型 → `{"error":"unsupported_training_type:<type>"}`
- 某类取空 → `{"error":"no_training_task_for_type:<type>"}`（不造模板兜底，数据关卡职责前移）

### score 主路径（LLM 五档信号 → Service 确定性合成）

信号校验 4 项（任一失败 → `agent_analysis_rejected:<code>` 拒收走兜底）：

| #   | 约束                             | 失败 flag                                                             |
| --- | ------------------------------ | ------------------------------------------------------------------- |
| 1   | coverage 五档枚举                  | `invalid_coverage:<dim>`                                            |
| 2a  | 无关维度（不在题目 criteria）            | `unrelated_dimension:<dim>`                                         |
| 2b  | 缺维度（题目有、信号无）                   | **不拒收**，missing 计 + `incomplete_analysis:<dim>`                     |
| 3   | reason 必填 / ≤200 字 / 过隐私       | `empty_reason:<dim>` / `long_reason:<dim>` / `privacy_reason:<dim>` |
| 4   | 禁数值字段（键名或值含 score/total/level） | `numeric_field`                                                     |

合成公式：`c_k = coverage×100`（round 2）→ `total = Σ weight_k × c_k`（round 2）。

### score 兜底路径（无 LLM / 信号拒收时）

- 素材 = 维度名 2 字滑动窗口（**刻意不用 reference_answer**）
- 命中率 = 命中窗口数 / 窗口总数 → 维度分 = 命中率×100（round 2）
- 否定拦截：窗口出现位置前 3 字符含 无/未/没/不/缺少 → 该出现不计（`re.finditer` 逐出现判断，任一非否定即命中）

### 长度修正（两路径共用）

| 条件（去空白后）    | 行为                            |
| ----------- | ----------------------------- |
| 空回答         | 全维度 0 分 + `empty_answer` flag |
| 0 < 长度 < 20 | 各维度分 `min(score, 80.0)`       |

### ability_updates（作用于该题 target_abilities 全部）

`total ≥ 80.0 → +1`；`40.0 ≤ total < 80.0 → 0`；`total < 40.0 → -1`

### 确定性保障

- 数据集操作只用于交集**计数**（顺序无关）；选 min 键定序
- 全部浮点 round 2；列表按 criteria 顺序、窗口去重保序
- 主/兜底路径各重复 10 次逐字节一致（`serialize` 断言）

### fail-safe 与隐私

- error 一律 `{"error":"code:detail"}` 返回；构造期唯一 TypeError（数据加载，同模块惯例）
- user_answer / reason 过邮箱/手机/身份证正则（逐字沿用 match_service 模式）

---

## 测试清单（映射验收标准 1-10）

| 验收项                     | 测试方法                                                                                                                                                                                               |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 三类选题/交集优先/字典序/确定性     | generate_modes_pick_matching_pool / generate_ability_gap_prioritizes_overlap / generate_overlap_2_beats_overlap_1 / generate_tie_break_is_lexicographic / generate_is_deterministic                |
| 2 非法类型/题库取空             | generate_unsupported_type_returns_error / generate_empty_type_pool_returns_error（构造注入）                                                                                                             |
| 3 主路径全五档/缺维 flag/信号拒收×4 | score_main_path_full_coverage / mixed_coverage_values / missing_dimension_flag / empty_signal_is_all_missing / unrelated_dimension / invalid_coverage / numeric_field / privacy_reason（后 4 个断言走兜底） |
| 4 长度修正                  | score_empty_answer_resets_to_zero / score_shorter_than_twenty_chars_capped_at_80                                                                                                                   |
| 5 ability_updates 阈值边界  | score_ability_update_threshold_boundaries（80.0→+1 / 78.75→0 / 40.0→0 / 32.5→-1）                                                                                                                    |
| 6 兜底窗口/否定拦截/不用参考答案      | score_fallback_window_hit_ratio / all_windows_hit / negation_intercepts / does_not_use_reference_answer                                                                                            |
| 7 隐私                    | score_private_info_returns_error（email/phone/id 三模式）                                                                                                                                               |
| 8 输出结构对齐                | generate_output_structure / score_output_structure_and_criteria_alignment                                                                                                                          |
| 9 确定性                   | generate_is_deterministic / score_main_path_is_deterministic / score_fallback_path_is_deterministic / unsupported_inputs_are_fail_safe_and_deterministic                                           |
| 10 回归                   | 全量 155 passed（含本步 29）                                                                                                                                                                              |

边界说明（**对接 Agent 时须知**）：79.9/39.9 因 coverage 离散五档不可达，测试用最近可达值（78.75/32.5）验证分档；80.0/40.0 由离散档可达（fully/mostly/partial→80.0、missing/partial/fully→40.0）。`data_quality_flags` 为追加字段（不删契约字段）。信号中重复维度不拒收（后写覆盖）。

## 验证结果

| 套件                                            | 结果                             |
| --------------------------------------------- | ------------------------------ |
| `test_training_service.py`                    | 29 passed                      |
| 全量 `backend/tests/ backend/app/agents/tests/` | 155 passed, 85 subtests（零回归破坏） |
| `compileall backend`                          | 无错误                            |

# 
