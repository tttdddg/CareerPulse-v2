已完成 ProfileAgent 阶段2结构化输出 Schema，未修改 Agent、LLM Client、Orchestrator、Service、数据库或前端，也未提交 Git。

修改文件：

- [profile_schema.py](D:/vue/CareerPulse-Pro/backend/app/schemas/profile_schema.py)
- `task_plan.md`、`findings.md`、`progress.md`：任务过程记录

当前没有统一的 `schemas/__init__.py`，因此未新增导出文件。

公开模型：

- `StudentBasicInfo`
- `StudentAbility`
- `StudentProfile`
- `active_ability_tags()`

使用方式：

```
profile = StudentProfile.model_validate(llm_output)
state.student_profile = profile.model_dump()
```

核心校验：

- `abilities`：3–30 项且标签不能重复
- `tag`：必须来自当前 `ability_tags.json` 的有效标签
- `level`：1–5
- `confidence`：0.0–1.0
- `evidence`：必填，最长 500 字，并拦截明显的邮箱、手机号、身份证号
- `competitiveness_score`：0.0–100.0
- `completeness`：0.0–1.0
- 可空字段使用明确的 `int | None`、`float | None`、`str | None`
- 所有模型禁止额外字段，因此匹配度、能力 Gap、职业路径等字段无法混入

合法示例：

```
{
  "student_id": null,
  "name": "匿名用户A",
  "basic_info": {
    "education_level": "本科",
    "major": "信息管理",
    "graduation_year": 2027,
    "target_job": "数据分析师",
    "target_industry": "企业服务/SaaS",
    "years_of_experience": 0.5
  },
  "abilities": [
    {
      "tag": "Python",
      "level": 3,
      "confidence": 0.82,
      "evidence": "完成过匿名化课程数据处理项目"
    },
    {
      "tag": "数据分析",
      "level": 3,
      "confidence": 0.78,
      "evidence": "在课程实践中完成指标分析与结论汇报"
    },
    {
      "tag": "沟通表达",
      "level": 2,
      "confidence": 0.65,
      "evidence": "参与团队项目汇报并负责整理分析结论"
    }
  ],
  "competitiveness_score": 48.0,
  "completeness": 0.72,
  "missing_fields": [
    "实习经历详情"
  ]
}
```

两个非法示例及结果：

```
{
  "abilities": [
    {
      "tag": "Python",
      "level": 6,
      "confidence": 0.8,
      "evidence": "完成课程项目"
    }
  ]
}
```

校验结果：拒绝于 `abilities.0.level`，错误类型 `less_than_equal`，因为等级不能超过 5。

```
{
  "completeness": -0.1
}
```

校验结果：拒绝于 `completeness`，错误类型 `greater_than_equal`，因为完整度不能小于 0。

测试结果：

- Schema 综合测试：合法输入 1 项、非法输入 8 项全部符合预期
- 最终非法样例 smoke test：通过
- Schema 编译检查：通过
- 现有 Mock Agent 回归测试：7/7 通过

关键 diff 摘要：

- 新增严格的三级 Pydantic 模型。
- 基于当前 43 个有效能力标签进行动态校验。
- 增加能力数量、范围、重复标签及额外字段校验。
- 增加 evidence 隐私信息拦截。
- 保持冻结 StudentProfile 公共字段完全兼容。
- 未加入匹配度、Gap、职业路径或阶段3字段。
- 未新增依赖。

竞争力评分风险：公共契约已经冻结该字段，同时 `04_API_CONTRACTS.md §10` 明确其应“由能力等级加权计算得出”。因此本次保留该字段以维持兼容，但仅依靠 Schema 的 0–100 范围校验无法证明分数来源可靠。更合理的后续方案是让 LLM 只生成基本信息、能力、置信度、证据和完整度，再由确定性 Service 根据能力等级和固定权重计算 `competitiveness_score`，最后组装并执行 `StudentProfile` 校验。