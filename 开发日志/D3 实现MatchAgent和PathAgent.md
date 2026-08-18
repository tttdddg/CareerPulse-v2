阶段3第6步已完成：实现MatchAgent和PathAgent，扩展CareerState支持career_roadmap。未对接百宝箱平台工具、未开发TrainingAgent/FeedbackAgent、未修改前端，已提交Git。

### 1. 修改文件

核心代码：

- [career_state.py](backend/app/orchestrator/career_state.py)：增加 `career_roadmap`/`career_preferences`/`desired_city` 字段，`apply_agent_data` 白名单自动覆盖新字段
- [match_agent.py](backend/app/agents/match_agent.py)：从Mock（内联算分 `_calculate`）完全重写为真实Agent，调用MatchService确定性匹配，可选LLM生成suggestion/strengths文案
- [path_agent.py](backend/app/agents/path_agent.py)：从Mock（硬编码3阶段 `_build`）完全重写为真实Agent，调用PathService图搜索+路径推荐，三输出（path_plan旧格式投影 + learning_plan + career_roadmap），可选LLM生成阶段描述

测试：

- [test_match_agent.py](backend/app/agents/tests/test_match_agent.py)：新增10项测试（正常/空数据/LLM失败/隐私/确定性/Schema校验/依赖fallback/拍平函数×3）
- [test_path_agent.py](backend/app/agents/tests/test_path_agent.py)：新增9项测试（正常三输出/career_roadmap完整/依赖fallback/LLM失败/隐私/确定性/apply_agent_data/拍平函数/偏好提取）

### 2. 关键设计

#### 数据格式适配

ProfileAgent输出统一StudentProfile（`ability_dimensions`按维度分组），而MatchService/PathService期望旧格式（`abilities`拍平列表）。两个Agent各自实现 `_flatten_profile()` 做转换：

- `ability_dimensions[].tags[]` → 每条 `{tag, level, confidence, evidence}`
- 维度级别继承到每个标签
- 多证据合并为 `"; "` 分隔文本
- `profile_completeness` → `completeness`，`missing_fields` 透传
- 旧格式直接透传（兼容历史数据）

#### MatchAgent 流程

```
_execute:
  ① _flatten_profile(state.student_profile)         ← 统一→旧格式
  ② MatchService().calculate(flat_profile, job)     ← 确定性匹配
  ③ _enhance_with_llm(result)                       ← 可选LLM写建议文案
  ④ return {"match_result": result}

_fallback:
  ① 同上① ②（跳过LLM）
  ② return {"match_result": result}                  ← Service即使数据不全也返回有效结果
```

LLM数据源从 `skill_gaps` 读取（仅含真实缺口维度，含 `gap`/`priority`/`difficulty`），不读取 `gap_analysis`（含所有维度含已达标的）。LLM失败静默捕获，Service默认值（`suggestion=""`）保持不变。

#### PathAgent 流程

```
_execute:
  ① _flatten_profile(state.student_profile)         ← 统一→旧格式（含student_id/name/basic_info/cscore）
  ② _extract_preferences(state.student_profile)     ← 从basic_info提取偏好
  ③ PathService().calculate(flat, job, match, pref) ← 图搜索+评分+阶段拆解
  ④ _enhance_with_llm(result)                       ← 可选LLM生成阶段描述
  ⑤ return {
       "path_plan": _build_path_plan(result),         ← 旧格式投影（§5.1冻结契约）
       "learning_plan": _build_learning_plan(result), ← 学习计划（§5.2冻结契约）
       "career_roadmap": result,                      ← 完整PathResult（含双向roadmap）
     }

_fallback:
  ① 尝试调PathService
  ② 失败时_build_fallback_result()                   ← 构造合法空PathResult
```

#### 三输出结构

| 输出               | 格式依据      | 内容                                                                                               |
| ---------------- | --------- | ------------------------------------------------------------------------------------------------ |
| `path_plan`      | 冻结契约§5.1  | `target_job/plan_3year{phases,total_score}/plan_5year{alternative_paths/path_algorithm_version}` |
| `learning_plan`  | 冻结契约§5.2  | `phases{phase,title,tasks}/certificate_suggestions/project_suggestions`                          |
| `career_roadmap` | ADR-002扩展 | 完整PathResult（含`status/candidate_paths/path_scores/three_year_roadmap/five_year_roadmap`）         |

### 3. 修复记录

| 问题                       | 根因                                                   | 修复                                             |
| ------------------------ | ---------------------------------------------------- | ---------------------------------------------- |
| MatchAgent status=failed | 同一能力标签跨维度出现 → MatchService拒绝重复tag                    | `_flatten_profile()` 增加 `seen` 集合去重            |
| PathAgent status=failed  | 旧StudentProfile `extra="forbid"` 拒绝 `name`/`city` 字段 | `_flatten_profile()` 从basic_info中pop name和city |
| LLM数据源用gap_analysis      | gap_analysis不含gap数值，所有缺口gap=0                        | 改为从 `skill_gaps` 读取（真实gap/priority/difficulty） |

### 4. 测试结果

```
MatchService                   23/23 passed (20 subtests)
PathService                    20/20 passed
AbilityTagNormalizer            5/5 passed
统一Schema                     5/5 passed
LLM Client                    12/12 passed
---
ProfileAgent                  10/10 passed
MatchAgent                    10/10 passed
PathAgent                      9/9 passed
---
合计                          94/94 passed (71 subtests)
```

额外验证：

- 全链路6 Agent正常输入 → 全部success，零fallback
- LLM启用实测 → MatchAgent生成strengths文案，PathAgent生成3年/5年阶段描述
- Demo Mode（无LLM Key） → 无Agent状态为failed
- `compileall` 通过
- 隐私检查通过（日志无手机号/邮箱/身份证）

### 5. 匹配示例（LLM启用，演示学生C × 数据分析师）

```
Overall Score:     90.42  (high)
Matched Skills:    数据分析, Python, 数据可视化
Skill Gaps:        SQL/数据库(gap=1, priority=1), 沟通表达(gap=1, priority=2)
LLM Strengths:    "具备Python数据处理和可视化基础，在数据分析岗位的技术实施方面有优势"
```

### 6. 路径示例（同上）

```
3年路径 → 3阶段:
  第1年: 数据分析助理 → 以数据清洗和基础分析能力为主
  第2年: 数据分析岗实践 → 深化业务分析和数据驱动决策
  第3年: 数据分析师 → 达到岗位核心能力要求

5年路径 → 5阶段:
  第1年: 数据分析助理
  第2年: 独立完成数据分析任务
  第3年: 数据分析师岗位
  第4年: 深化高级分析方法
  第5年: 巩固岗位能力，评估晋升或横向机会
```

### 7. 已知后续边界

- `final_report` 不含 `career_roadmap`：CareerOrchestrator为冻结代码，下游直接读 `state.career_roadmap`
- `career_preferences`/`desired_city` 已预留字段，当前PathAgent仅读取不写回
- MatchAgent/PathAgent的平台工具注册属于阶段5（百宝箱正式集成），本次不涉及
- TrainingAgent/FeedbackAgent仍为Mock，接真实Service属阶段4范围
- 数据格式转换（`_flatten_profile`）两个Agent各有一份实现，后续可考虑提取公用函数
