## 职业图谱结构

当前样例图谱包含：

- 10 个岗位节点
- 16 条有向职业转换边
- 数据分析、AI产品、后端开发三条主线
- 2 个真实横向循环，由搜索算法安全处理

节点新增：

- `required_skills`：统一能力标签向量
- `typical_duration`：典型停留月数
- `risk_level`：岗位风险
- `cities`：城市数据；当前保持 `null`

边新增：

- `transition_requirements`
- `risk_level`
- 原有 `transfer_cost`、`growth_value`、`vertical/lateral` 关系保留

`CareerNode`、`CareerEdge` 作为扩展图模型的公开名称导出。所有能力均来自现有48个统一能力标签。

## 路径生成算法

1. 从图谱 `entry` 节点开始；有一年以上经验时允许 `junior` 节点。
2. 对每个入口调用 MatchService。
3. 起点依次按以下规则选择：
   - 可观测能力权重覆盖率最高
   - 已知能力 Gap 成本最低
   - confidence 最高
   - match score 最高
   - `node_key` 字典序
4. 使用受限 DFS 搜索所有 simple paths：
   - 路径内 `visited` 防止循环
   - 最多6个节点
   - 连续 lateral 转换最多2次
   - vertical 边必须严格向更高层级移动
5. 分类选取：
   - `direct`：节点数最少
   - `robust`：所有节点和边均为 low risk
   - `extension`：至少包含一条 lateral 边
6. 排序规则：

```
total_score 降序
→ time_estimate_months 升序
→ path_id 升序
```

某类路径不存在时输出 `candidate_type_unavailable:*`，不会伪造候选。

未知岗位只允许回退至图中可达节点并明确标记；完全无通路返回 `no_reachable_path`；能力向量不足返回 `insufficient_data`。

## 路径评分公式

```
AbilityGapCost =
  Σ 已知SkillGap.gap × difficulty

BaseScore =
  GrowthValue - TransferCost - AbilityGapCost

AdjustedScore =
  BaseScore
  + PreferenceAdjustment
  + IndustryContinuity × 5
  + RegionFit × 5
  - RiskPenalty

TotalScore =
  AdjustedScore × TargetConsistency
```

其中：

- 目标岗位完全一致：`TargetConsistency=1.0`
- 同行业图内替代岗位：`0.5`
- 其他岗位：`0.0`
- 城市数据缺失：`RegionFit=null`，不参与评分
- 未提供能力不按 level 0 计算，只降低路径 confidence
- 所有权重和阈值集中在 [path_config.py](D:/vue/CareerPulse-Pro/backend/app/services/path_config.py)

## 3年路径示例

仓库真实 Demo：`演示学生A → AI产品经理`。

推荐路线：

```
数据分析助理
→ 数据产品助理
→ AI产品经理
```

路径评分：

```
{
  "growth_value": 3.8,
  "transfer_cost": 2.3,
  "ability_gap_cost": 3.3,
  "base_score": -1.8,
  "preference_adjustment": 12.0,
  "risk_penalty": 6.0,
  "target_consistency": 1.0,
  "data_confidence": 0.7,
  "total_score": 4.2
}
```

年度路线：

- 第1年：数据分析助理——验证 SQL/数据库、数据分析与数据可视化能力
- 第2年：数据产品助理——深化需求分析、数据驱动决策和跨角色沟通
- 第3年：AI产品经理——达到岗位核心职责边界并形成可验证成果

## 5年路径示例

同一推荐图路径生成独立的5阶段路线：

- 第1年：建立数据分析助理核心能力
- 第2年：进入数据产品助理职责范围
- 第3年：进入AI产品经理岗位并完成首次应用验证
- 第4年：深化AI产品规划、需求分析和大模型应用
- 第5年：巩固AI产品经理能力，并评估高级岗位或横向机会

3年和5年 Roadmap 分别包含3个和5个独立阶段，不共享同一个阶段列表。

## 主要修改文件

实现：

- [path_schema.py](D:/vue/CareerPulse-Pro/backend/app/schemas/path_schema.py)
- [career_graph_repository.py](D:/vue/CareerPulse-Pro/backend/app/services/career_graph_repository.py)
- [path_service.py](D:/vue/CareerPulse-Pro/backend/app/services/path_service.py)
- [path_config.py](D:/vue/CareerPulse-Pro/backend/app/services/path_config.py)
- [a02_models.py](D:/vue/CareerPulse-Pro/backend/app/models/a02_models.py)
- [career_graph.json](D:/vue/CareerPulse-Pro/backend/app/data/career_graph.json)

数据库：

- [V002__extend_career_graph_for_path_planning.sql](D:/vue/CareerPulse-Pro/backend/migrations/V002__extend_career_graph_for_path_planning.sql)
- [init_a02_data.py](D:/vue/CareerPulse-Pro/backend/scripts/init_a02_data.py)

测试：

- [test_path_service.py](D:/vue/CareerPulse-Pro/backend/tests/test_path_service.py)

契约与决策：

- [ADR-002-stage3-career-graph-and-roadmap.md](D:/vue/CareerPulse-Pro/decisions/ADR-002-stage3-career-graph-and-roadmap.md)
- [03_ARCHITECTURE.md](D:/vue/CareerPulse-Pro/docs/a02/03_ARCHITECTURE.md)
- [04_API_CONTRACTS.md](D:/vue/CareerPulse-Pro/docs/a02/04_API_CONTRACTS.md)
- [05_AGENT_CONTRACTS.md](D:/vue/CareerPulse-Pro/docs/a02/05_AGENT_CONTRACTS.md)
- [06_DATA_DICTIONARY.md](D:/vue/CareerPulse-Pro/docs/a02/06_DATA_DICTIONARY.md)
- [13_MCP_TOOL_CATALOG.md](D:/vue/CareerPulse-Pro/docs/a02/13_MCP_TOOL_CATALOG.md)

## 测试结果

```
CareerGraphRepository + PathService  20/20 passed
MatchService                         23/23 passed
AbilityTagNormalizer                  5/5 passed
ProfileAgent阶段2回归                 7/7 passed
------------------------------------------------
核心相关测试                         55/55 passed
```

额外检查：

- 10节点/16边种子验证通过
- 48个统一能力标签校验通过
- V001九张表检查通过
- V002五类扩展字段检查通过
- 初始化脚本幂等 edge upsert 已验证
- 隐私检查通过
- 7个现有 Mock 工具 envelope 检查通过
- `compileall` 通过
- `git diff --check` 通过

平台旧基线仍为 `5/7`，两个失败与开发前一致：无 LLM 配置时旧测试仍要求全链 `success` 和 TBox `code=0`。本步骤没有修改 Agent 或平台层。