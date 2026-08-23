# D4 FeedbackService 实现完成报告

FeedbackService（反馈保存 + 优先级对称调权 + 成长记录快照）已实现并通过 20 项单元测试；全量回归无破坏、compileall 通过。全参数输入不碰 state、不调 LLM、fail-safe（error 返回值不抛异常）、内存存储（`_feedbacks`/`_growth` 实例 dict）、全程确定性，输出裸 dict 对齐 13 §7。`growth_trend` 仅三值（improving/stable/declining，契约+DDL 双锁）。

## 修改文件

| 文件                                         | 动作     | 行数  | 说明                                 |
| ------------------------------------------ | ------ | --- | ---------------------------------- |
| `backend/app/services/feedback_service.py` | **新建** | 248 | 1 个 Service 类 + 2 个模块级私有函数，零改动其他文件 |
| `backend/tests/test_feedback_service.py`   | **新建** | 256 | 20 个测试方法                           |

## Diff 摘要（新增文件 API 面）

### 模块常量（阈值/模板集中，无魔法数字）

| 常量                                                              | 值                              | 用途                 |
| --------------------------------------------------------------- | ------------------------------ | ------------------ |
| `ERR_MISSING_SESSION_ID` / `ERR_MISSING_USER_ID`                | missing_*                      | 必填校验               |
| `ERR_INVALID_SATISFACTION` / `ERR_INVALID_RATING`               | invalid_*                      | 数值校验               |
| `ERR_PRIVACY_VIOLATION`                                         | privacy_violation              | comments 隐私前移      |
| `FLAG_LOW_SATISFACTION_RECORDED`                                | low_satisfaction_recorded      | satisfaction≤2 标记  |
| `FLAG_FIRST_GROWTH_SNAPSHOT`                                    | first_growth_snapshot          | 首次快照标记             |
| `FLAG_COMPETITIVENESS_UNAVAILABLE`                              | competitiveness_unavailable    | overall_score 缺失标记 |
| `TREND_*` / `TRENDS`                                            | improving/stable/declining     | 仅三值（代码层锁死）         |
| `PRIORITY_STEP` / `PRIORITY_FLOOR`                              | 1 / 1                          | 调权步长与下限            |
| `LOW_RATING_THRESHOLD`/`NEUTRAL_RATING`/`HIGH_RATING_THRESHOLD` | 2 / 3 / 4                      | 调权档位               |
| `LOW_SATISFACTION_THRESHOLD`                                    | 2                              | 抑制硬调权阈值            |
| `REASON_RAISE_PRIORITY` / `REASON_LOWER_PRIORITY`               | "训练反馈低，需优先补齐" / "训练反馈良好，紧迫度下调" | reason 确定性模板       |

### 公开 API

```python
FeedbackService()
    # 内存存储：self._feedbacks[session_id]=记录 / self._growth[user_id]=上次快照
save_feedback(session_id=None, user_id=None, satisfaction=None, path_rating=None,
              training_rating=None, resource_rating=None, comments=None,
              skill_gaps=None, abilities=None, completed_trainings=0, completed_phases=0,
              training_target_abilities=None, overall_score=None) -> dict
    # 全部参数带默认值 → 缺失输入走校验 error 而非 TypeError（fail-safe）
get_feedback(session_id) -> dict | None   # 只读接口（深拷贝）
get_growth(user_id) -> dict | None         # 只读接口
```

### 内部协作函数

```python
_validate(session_id, user_id, satisfaction, 3×rating, comments) -> dict | None
    # None=通过；否则返回 {"error":"code:detail"}（首个失败即返回）
_update_growth(user_id, overall_score, completed_trainings, completed_phases)
    # -> (snapshot, growth_flags)；越界 None→0.0+flag；首次→stable+flag；有历史→升降平三值
_adjust_priorities(skill_gaps, training_target_abilities, training_rating, satisfaction)
    # 对称调权；顺序跟随 skill_gaps 传入顺序（优先序自然序）
```

## 关键设计说明

### 校验与隐私

| 校验项                  | 规则                               | error                                |
| -------------------- | -------------------------------- | ------------------------------------ |
| session_id / user_id | 非空字符串                            | missing_session_id / missing_user_id |
| satisfaction         | 非 bool 的 1-5 整数（None→拒）          | invalid_satisfaction                 |
| 三个 rating            | 非 None 时须非 bool 的 1-5 整数         | invalid_rating:<name>=<value>        |
| comments             | 邮箱/手机/身份证正则（沿用 match_service 模式） | privacy_violation                    |

**理解口径**："至少一项评分" = satisfaction（必填）自身即一项，三个 rating 全 None 允许（05 §6.4 前置判定顺延）。

### 对称调权（仅 skill_gaps 且 training_target_abilities 均提供时）

| 条件                                  | 动作                    | 边界                                 |
| ----------------------------------- | --------------------- | ---------------------------------- |
| `training_rating ≤ 2`               | priority 数值 -1（更紧迫）   | 下限 `PRIORITY_FLOOR=1`；reason 升权模板  |
| `training_rating ≥ 4`               | priority 数值 +1（紧迫度下调） | 上限 `N=len(skill_gaps)`；reason 降权模板 |
| `training_rating == 3` 或 None       | 不调                    | —                                  |
| 目标不在缺口 / gap 无 dimension 或 priority | 不调                    | 信号无对象不编造                           |
| `satisfaction ≤ 2`                  | 不硬调权                  | 仅 `low_satisfaction_recorded` flag |

输出 `updated_priorities[{tag, old_priority, new_priority, reason}]`，无调权 → `[]`。**自平衡**：单题 target_abilities 有限、好评降权提供回落、内存无跨会话累积。

### 成长快照（按 user_id 内存 dict）

- `competitiveness_score` = 传入 `overall_score`（None → 0.0 + `competitiveness_unavailable`），round 2；**语义为近似值**（画像侧竞争力算法未实现，以最近匹配分近似）
- 首次（无历史）→ `stable` + `first_growth_snapshot`；有历史 → `improved = score↑ or completed↑`、`declined = score↓ or completed↓`：improved 且非 declined→improving；declined 且非 improved→declining；否则（含升降矛盾）→stable
- 更新 `self._growth[user_id]` = 本次快照（供下次对比）；`growth_archive_updated=true`

### 存储与输出

- `_feedbacks[session_id]` 存记录：原始输入 + `skill_gaps`/`abilities` 深拷贝、`training_target_abilities` 转 list
- 输出结构：`{feedback_saved, growth_archive_updated, updated_priorities, growth_snapshot, data_quality_flags}`
- `data_quality_flags` 顺序固定：growth flag（competitiveness_unavailable 先、first_growth_snapshot 后）→ `low_satisfaction_recorded` 追加

## 测试清单（映射验收标准 1-10）

| 验收项                                    | 测试方法                                                                                                                                                                                                                                                                                                      |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 校验（缺失/越界/非整数/隐私）                     | validation_rejects_bad_inputs（14 子场景）/ validation_rejects_private_comments（3 模式）                                                                                                                                                                                                                          |
| 2 保存 + 内存可读                            | save_persists_record_in_memory / missing_feedback_record_returns_none（get_feedback 只读接口）                                                                                                                                                                                                                  |
| 3 对称调权（差评升/好评降/中性/缺口外/satisfaction 抑制） | low_training_rating_raises_priority / priority_adjustment_floor_is_one / high_training_rating_lowers_priority / priority_adjustment_cap_is_gap_count / neutral_rating_does_not_adjust / target_not_in_gaps_does_not_adjust / no_skill_gaps_does_not_adjust / low_satisfaction_blocks_adjustment_with_flag |
| 4 调权输出结构 / 无调权空数组                      | updated_priorities_item_structure                                                                                                                                                                                                                                                                         |
| 5 快照（首次 stable / 升降平 / 完成数驱动）          | growth_first_snapshot_is_stable / growth_trend_improving_declining_stable / growth_trend_from_completed_counts                                                                                                                                                                                            |
| 6 competitiveness（传入值 / None+flag）     | growth_first_snapshot_is_stable / growth_competitiveness_unavailable_flag                                                                                                                                                                                                                                 |
| 7 trend 仅三值                            | only_three_trend_values_are_produced（遍历实例历史断言 TRENDS）                                                                                                                                                                                                                                                     |
| 8 隐私                                   | validation_rejects_private_comments                                                                                                                                                                                                                                                                       |
| 9 确定性                                  | is_deterministic_across_fresh_instances（10 次逐字节一致，含调权+快照+flag 全链路）                                                                                                                                                                                                                                        |
| 10 回归                                  | 全量 155 passed                                                                                                                                                                                                                                                                                             |

已知边界说明（**对接 Agent 时须知**）：趋势对比采用"任一升→improving、任一降→declining、无变化或升降矛盾→stable"；调权上限 N 直接取 `len(skill_gaps)`（含无 dimension 条目即计）；`abilities` 参数仅暂存记录未参与计算（本轮快照最小实现）。

## 验证结果

| 套件                                            | 结果                             |
| --------------------------------------------- | ------------------------------ |
| `test_feedback_service.py`                    | 20 passed, 14 subtests         |
| 全量 `backend/tests/ backend/app/agents/tests/` | 155 passed, 85 subtests（零回归破坏） |
| `compileall backend`                          | 无错误                            |

# 
