JobAgent 阶段2结构化 Schema 已完成，只新增允许的业务文件，没有修改 JobAgent、ProfileAgent、Service 或 CareerState。

公开模型：

- `RequiredJobAbility`
- `JobProfile` → 写入 `CareerState.job_profile`
- `TrendResult` → 写入 `CareerState.trend_result`
- `JobAgentOutput` → 校验一次 LLM 返回中的两个独立结果

实现文件：[job_schema.py (line 1)](D:/vue/CareerPulse-Pro/backend/app/schemas/job_schema.py:1)

### 合法 JSON 示例

```
{
  "job_profile": {
    "job_id": 91002,
    "title": "数据分析师",
    "normalized_title": "数据分析师",
    "industry": "电子商务",
    "required_abilities": [
      {
        "tag": "数据分析",
        "required_level": 4,
        "weight": 0.6,
        "importance": "critical",
        "evidence": "岗位职责要求独立完成业务数据分析并输出结论。"
      },
      {
        "tag": "SQL/数据库",
        "required_level": 3,
        "weight": 0.4,
        "importance": "important",
        "evidence": "岗位要求使用 SQL 完成数据查询和指标提取。"
      }
    ],
    "soft_skills": [
      "沟通表达",
      "解决问题"
    ],
    "salary_range": null,
    "job_description": "负责业务数据分析、指标监控和分析结论表达。"
  },
  "trend_result": {
    "job_title": "数据分析师",
    "industry": "电子商务",
    "trend_summary": "岗位正在提高对业务理解和数据表达能力的要求。",
    "hot_skills": [
      "数据分析",
      "SQL/数据库"
    ],
    "rising_skills": [
      "数据可视化"
    ],
    "declining_skills": [],
    "ai_risk_assessment": "medium",
    "ai_risk_detail": "重复性数据整理可能被自动化，但业务分析和结论解释仍需要人工判断。",
    "development_opportunities": [
      "向业务分析和数据驱动决策方向发展"
    ],
    "development_risks": [
      "仅掌握基础报表工具时竞争力可能下降"
    ],
    "data_source": "匿名演示岗位资料与岗位趋势知识库摘要"
  }
}
```

### 非法案例一：等级越界

```
{
  "tag": "数据分析",
  "required_level": 6,
  "weight": 1.0,
  "importance": "critical",
  "evidence": "岗位要求完成业务分析。"
}
```

校验结果：

```
required_abilities.0.required_level
Input should be less than or equal to 5
```

### 非法案例二：权重总和不为 1

```
{
  "required_abilities": [
    {
      "tag": "数据分析",
      "required_level": 4,
      "weight": 0.5,
      "importance": "critical",
      "evidence": "岗位要求完成业务分析。"
    },
    {
      "tag": "SQL/数据库",
      "required_level": 3,
      "weight": 0.3,
      "importance": "important",
      "evidence": "岗位要求使用 SQL。"
    }
  ]
}
```

校验结果：

```
Value error: required_abilities weights must sum to 1.0
```

### 测试结果

- 现有岗位样例：3/3 通过
- 合法趋势样例：1/1 通过
- 非法探针：5/5 按预期拒绝
  - 等级越界
  - 权重总和错误
  - 非标准趋势标签
  - 非法 AI 风险枚举
  - 额外 `match_score` 字段
- ProfileAgent 回归：7/7 通过
- `py_compile`：通过

### 关键 diff

- 标准能力标签必须来自 `ability_tags.json`
- `required_level` 限制为 1–5
- `weight` 限制为 0–1，岗位能力权重总和必须为 1
- 岗位能力标签禁止重复
- `evidence` 支持 JD 原文依据；无 JD 的 fallback 可明确为 `null`
- 技能趋势拆分为 hot、rising、declining 三类标准标签
- AI 风险限制为 `low / medium / high`
- 要求趋势说明、风险说明和数据来源可解释
- 禁止 Schema 外字段，因此匹配分、Gap、路径和录用概率会被拒绝
- 组合模型保证 `job_profile` 和 `trend_result` 的岗位名称、行业一致

契约兼容说明：

- 冻结契约使用 `normalized_title` 表示归一化岗位类型。
- 冻结契约使用 `job_description` 承载自然语言岗位摘要。
- `evidence` 是本次需求新增的嵌套字段，但尚未出现在冻结 API 契约中，后续正式开放公共 API 前应由技术负责人同步契约文档。
- CareerState 仍分别保存 `job_profile` 和 `trend_result`，没有合并状态字段。

没有统一 `schemas/__init__.py`，因此未新增导出修改。没有新增依赖，也没有提交 Git。