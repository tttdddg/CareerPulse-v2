## PA-N-01

【测试ID】PA-N-01
【输入摘要】匿名学生 A；信息管理本科，提供 Python、数据分析、用户访谈和课程展示事实；相同输入重复两次。
【Agent状态】`success`
【Schema是否通过】是
【能力数量】4
【Evidence质量】通过；均能对应输入事实
【是否发现幻觉】否
【是否Fallback】否
【问题】仅验证了受控输出的一致性，未验证真实模型随机性
【建议】配置固定 provider/model 后至少重复运行 5–10 次，统计核心标签和等级漂移

## PA-N-02

【测试ID】PA-N-02
【输入摘要】匿名学生 B；软件技术专科，提供 Java、数据库、后端 API 项目和版本控制事实；相同输入重复两次。
【Agent状态】`success`
【Schema是否通过】是
【能力数量】4
【Evidence质量】通过；没有扩展为云计算、Docker 或未提供的框架
【是否发现幻觉】否
【是否Fallback】否
【问题】真实模型一致性尚未验证
【建议】真实 provider 测试时重点检查是否从 API 项目过度推断 API 设计、Spring 或微服务

## PA-N-03

【测试ID】PA-N-03
【输入摘要】匿名学生 C；统计学硕士，提供 Python、SQL、数据分析、可视化及汇报事实；相同输入重复两次。
【Agent状态】`success`
【Schema是否通过】是
【能力数量】5
【Evidence质量】通过
【是否发现幻觉】否；未增加机器学习、深度学习或证书
【是否Fallback】否
【问题】真实模型一致性尚未验证
【建议】真实 provider 测试时检查是否从“统计建模”自动升级为机器学习能力

## PA-I-01

【测试ID】PA-I-01
【输入摘要】缺少毕业年份、目标行业、经验及详细项目；仅有三项明确的入门能力事实。
【Agent状态】`success`
【Schema是否通过】是
【能力数量】3
【Evidence质量】通过；没有为了扩充画像增加额外能力
【是否发现幻觉】否
【是否Fallback】否
【问题】无；受控输出的 `completeness=0.35`，正确低于正常样例的 `0.68–0.80`
【建议】真实模型测试需继续确认信息不足时不会为了满足最少三项能力而编造标签

## PA-E-01

【测试ID】PA-E-01
【输入摘要】匿名学生 B，模拟 provider 调用异常。
【Agent状态】`partial`
【Schema是否通过】是
【能力数量】4
【Evidence质量】较弱；fallback 仅输出“输入中明确提及某标签”，没有保留项目级事实
【是否发现幻觉】否；标签都在输入中明确出现
【是否Fallback】是，`fallback_used=true`
【问题】fallback 的 `completeness=1.0`，高于原匿名样例的 `0.68`；补充信息中的“实习经历缺失”未进入 `missing_fields`
【建议】后续把 fallback completeness 改为确定性字段覆盖规则，并保留明确的缺失信息

## PA-J-01

【测试ID】PA-J-01
【输入摘要】匿名学生 C；前两次模拟非法 JSON，第三次返回修复后的合法结构。
【Agent状态】`success`
【Schema是否通过】是
【能力数量】5
【Evidence质量】通过
【是否发现幻觉】否
【是否Fallback】否
【问题】无；共调用 3 次，首次请求不含 repair 指令，后两次均包含 `<schema_repair>`
【建议】后续日志可增加不含敏感内容的 retry 次数指标，方便监控 provider 质量

## 其他验证

以下项目全部通过：

- 所有最终画像均通过 Pydantic。
- 所有 `level` 均在 1–5。
- 所有 `confidence` 均在 0–1。
- Agent 返回格式字段完整。
- `CareerState.student_profile` 与 Agent 返回数据一致。
- 日志不包含完整简历哨兵、邮箱或手机号。
- 模型异常只调用一次并真实进入 fallback。
- 非法 JSON 最多执行两次结构修复。
- 受控重复运行的核心标签和等级一致。

## 发现的代码风险

对抗测试中，模拟模型返回了结构合法但内容虚构的结果：

- 未提供 PMP，却输出 PMP 证书能力。
- 表单为 0 年经验，却输出 5 年经验。
- 信息有限，却输出 `completeness=1.0`。
- 同一输入两次返回完全不同的能力核心。

这些结果全部通过 ProfileSchema，并被 Agent 以 `success` 接受。

根因是当前 Schema 只能验证字段、范围和标签合法性，无法验证：

- evidence 是否真正来自输入；
- 证书是否被明确提供；
- 工作年限是否与表单一致；
- completeness 是否符合输入覆盖度；
- 重复运行的核心能力是否发生异常漂移。

建议后续单独授权修复：

1. 基本信息由表单确定性覆盖，不接受 LLM 改写。
2. 增加 evidence/source grounding 或原文引用定位。
3. 证书标签必须存在显式证据。
4. completeness 改为代码计算。
5. 增加真实 provider 的多次重复运行测试与核心标签漂移阈值。

本轮没有修改 ProfileAgent、JobAgent、MatchService 或其他业务逻辑，也没有提交 Git。仅更新了 planning-with-files 的任务记录。