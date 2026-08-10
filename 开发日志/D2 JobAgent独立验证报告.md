阶段2 JobAgent 独立验证已完成。共执行 8 个主场景和 3 个专项对抗探针。

重要前提：当前未配置真实 LLM API，仓库也没有独立岗位趋势资料文件。因此正常场景使用受控 Fake LLM 和匿名模拟 JD/趋势上下文，验证代码链路、结构和事实边界，不代表真实模型幻觉率或真实市场趋势准确率。

## 测试报告

【测试ID】JOB-NORMAL-1
【岗位】AI产品经理
【Agent状态】success
【能力数量】7
【Schema】JobProfile、TrendResult 均通过
【Evidence】7 项均可回溯到模拟 JD
【趋势合理性】趋势技能只取自提供的趋势上下文
【是否发现幻觉】否
【Fallback】否
【问题】样例属于匿名模拟 JD，不是真实招聘信息
【建议】接入真实 JD 后验证同义词映射与 evidence 误拒率  

【测试ID】JOB-NORMAL-2
【岗位】数据分析师
【Agent状态】success
【能力数量】5
【Schema】通过
【Evidence】全部能在 JD 中归一化回溯
【趋势合理性】趋势标签与输入资料对应，未增加数字
【是否发现幻觉】否
【Fallback】否
【问题】当前趋势资料是非统计性模拟上下文
【建议】后续使用带明确来源的趋势知识库资料  

【测试ID】JOB-NORMAL-3
【岗位】后端开发工程师
【Agent状态】success
【能力数量】6
【Schema】通过
【Evidence】全部对应 JD 中的能力事实
【趋势合理性】趋势能力没有混入当前 JD 硬性要求
【是否发现幻觉】否
【Fallback】否
【问题】没有验证 Spring、云原生等复杂同义映射
【建议】加入真实技术 JD 边界样例  

【测试ID】JOB-SPARSE
【岗位】数据分析师
【Agent状态】success
【能力数量】1
【Schema】通过，权重为 1.0
【Evidence】对应稀疏 JD 中唯一明确能力
【趋势合理性】未为满足能力数量补造要求
【是否发现幻觉】否
【Fallback】否
【问题】单项能力画像信息有限
【建议】上层应提示补充完整 JD  

【测试ID】JOB-NO-TREND
【岗位】数据分析师
【Agent状态】success
【能力数量】5
【Schema】通过
【Evidence】均可回溯到 JD
【趋势合理性】hot/rising/declining 均为空，AI 风险为 medium 中性占位，并明确资料缺失
【是否发现幻觉】否
【Fallback】否
【问题】Schema 没有 `unknown` AI 风险枚举
【建议】后续由技术负责人评估是否扩展公共契约  

【测试ID】JOB-INVALID-JSON
【岗位】数据分析师
【Agent状态】success
【能力数量】5
【Schema】最终通过
【Evidence】修复后仍对应 JD
【趋势合理性】通过
【是否发现幻觉】否
【Fallback】否
【问题】前两次返回非法 JSON
【建议】无；第三次调用结构修复成功，调用次数符合“首次 + 最多两次 retry”  

【测试ID】JOB-MODEL-ERROR
【岗位】数据分析师
【Agent状态】partial
【能力数量】6
【Schema】fallback 结果通过
【Evidence】规则从 JD 句子提取，邮箱和手机号会脱敏
【趋势合理性】规则 fallback 不自行判断趋势方向
【是否发现幻觉】否
【Fallback】是
【问题】模拟 provider 不可用
【建议】上层根据 `fallback_used=true` 明确展示降级状态  

【测试ID】JOB-ADVERSARIAL
【岗位】AI产品经理
【Agent状态】partial
【能力数量】1
【Schema】最终 fallback 结果通过
【Evidence】伪造 evidence 被拦截，fallback evidence 可回溯
【趋势合理性】未支持的趋势技能和 38% 虚构数字没有进入 CareerState
【是否发现幻觉】发现造假尝试，但已被拦截
【Fallback】是
【问题】修复前结构合法的幻觉能够以 success 写入状态
【建议】保留当前 grounding 门禁并增加持久化对抗测试  

## 发现并修复的小 Bug

修复前，对抗输出可以包含：

- JD 未提供的 6 项额外能力
- 无法回溯的 evidence
- 趋势资料未出现的技能
- 未提供的“增长 38%”
- 虚构趋势来源

这些内容虽然通过 Pydantic，但会以 `success` 写入 CareerState。

现已在 [job_agent.py (line 214)](D:/vue/CareerPulse-Pro/backend/app/agents/job_agent.py:214) 增加确定性 grounding 校验：

- evidence 必须能在 JD 中归一化回溯
- 薪资范围必须来自 JD
- 趋势技能必须在 trend_context 中出现
- 趋势输出中的数字必须由 trend_context 提供
- 无趋势资料时必须保持空趋势列表、中性风险和缺失说明
- grounding 失败不进行结构 retry，直接 fallback

专项探针结果：

- 未支持趋势技能：已拦截
- 未提供百分比：已拦截
- 空趋势下的确定性增长结论：已拦截
- 虚构 evidence/额外硬性能力：已拦截

## 其他验证

- CareerState 的 `job_profile`、`trend_result` 均正确更新
- AgentResult 与 AgentLog 的 status、fallback_used 一致
- 非法 JSON 调用次数为 3
- Provider 异常只调用模型 1 次
- 日志不包含完整 JD、邮箱、手机号或测试哨兵
- ProfileAgent 回归：7/7
- 受控 ProfileAgent + JobAgent 平台链路：7/7
- `compileall`：通过

## 剩余风险

- 字符串 grounding 较保守，真实模型的忠实意译可能因不是 JD 原文子串而被误判，进入 fallback。
- 非数字的趋势摘要、机会、风险和虚构机构名称仍无法完全通过确定性规则识别。
- 未知岗位且 JD 无有效标签时，Demo fallback 可能使用默认岗位向量；必须结合 `fallback_used=true` 展示。
- 没有真实 provider 和真实趋势资料，尚未验证模型稳定性、误拒率和漏检率。
- 本轮测试仍为隔离脚本，尚未持久化为 JobAgent 自动化测试文件。

没有修改 MatchService、MatchAgent、PathAgent，也没有提交 Git。