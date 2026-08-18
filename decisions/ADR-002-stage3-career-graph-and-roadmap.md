# ADR-002：阶段3职业图谱扩展与确定性 CareerRoadmap

- 状态：Accepted
- 日期：2026-08-13
- 范围：职业图谱、候选路径、路径评分和3/5年路线

## 背景

D2 图谱只有岗位身份和边成本，无法计算能力跨度、节点时长或路径风险；冻结
`path_plan` 又不足以表达候选路径、评分分解、数据置信度及年度阶段。现有图还包含
合法的横向往返，因此不能假设它是 DAG。

## 决策

1. 加法扩展 `CareerGraphNode/Edge`：节点增加统一能力向量、典型时长、岗位风险和
   可空城市；边增加转换能力要求和转岗风险。
2. 使用 V002 迁移扩展数据库，V001 不改；边增加唯一索引，初始化脚本使用 upsert。
3. `CareerGraphRepository` 校验引用、权重、标签、孤立节点和 vertical 升级关系；
   `detect_cycles()` 报告横向环但不拒绝整图。
4. PathService 使用 path-local visited、最多6节点、连续 lateral 最多2次的受限 DFS，
   不依赖 LLM 或第三方图包。
5. 候选节点只来自图谱。未知/不可达目标只能回退到图内可达节点并明确标记，绝不
   创建推断岗位节点。
6. 路径基础分保留冻结公式 `GrowthValue - TransferCost - AbilityGapCost`，偏好、
   行业连续性、地域、风险和目标一致性使用集中配置做确定性调整。
7. 城市缺失时不计分并标记；节点风险缺失默认 medium 并扣数据置信度；能力向量
   缺失仅可从同名 JobProfile 回退，否则返回数据不足。
8. 新 PathResult 同时返回候选路径和独立的3年/5年年度 Roadmap；冻结 path_plan
   保留，待后续 PathAgent 集成时做兼容投影。本步骤不修改 PathAgent/CareerState。
9. 阶段目标、行动和完成条件由确定性模板生成，只表达方向，不生成阶段4训练、课程、
   资源或执行计划。

## 影响

- 3年固定3个年度阶段，5年固定5个年度阶段，二者不复制同一列表。
- 图中可能存在环，但任何候选路径都是无重复节点的 simple path。
- `direct/robust/extension` 某类不存在时明确输出 data-quality flag，不伪造候选。
- 当前 PathAgent、百宝箱和前端仍使用旧 Mock/契约；只有 Repository 和 PathService
  已实现并测试。
