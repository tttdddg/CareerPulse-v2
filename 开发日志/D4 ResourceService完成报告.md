ResourceService（能力缺口 → 学习资源推荐）已实现并通过 12 项单元测试；全量回归无破坏、compileall 通过。复用 `AbilityTagNormalizer` 同模块（禁止复制实现的红线落实）、输出裸 dict 对齐 13 §6.2（剔除 demo_only/resource_id）、不调 LLM、不碰 state、fail-safe（run 期无异常路径，全部以 flag 表达）、全程确定性。

## 修改文件

| 文件                                         | 动作     | 行数  | 说明                                |
| ------------------------------------------ | ------ | --- | --------------------------------- |
| `backend/app/services/resource_service.py` | **新建** | 101 | 1 个 Service 类 + 1 个私有静态方法，零改动其他文件 |
| `backend/tests/test_resource_service.py`   | **新建** | 154 | 12 个测试方法                          |

## Diff 摘要（新增文件 API 面）

### 模块常量

| 常量                               | 值                                         | 用途              |
| -------------------------------- | ----------------------------------------- | --------------- |
| `RESOURCE_LIMIT`                 | 10                                        | 学习资源上限          |
| `FLAG_NO_RESOURCE_FOR_TAG`       | "no_resource_for_tag"                     | gap 无命中 flag 前缀 |
| `FLAG_UNKNOWN_TAG`               | "unknown_tag"                             | 非法标签 flag 前缀    |
| `FLAG_JOB_RESOURCES_UNAVAILABLE` | "job_resources_unavailable"               | 岗位资源恒空 flag     |
| `_OUTPUT_FIELD_NAMES`            | title/type/url/target_ability/description | 输出字段白名单（剔除内部标记） |

### 公开 API

```python
ResourceService(resources_file=None, resources=None)
    # 构造注入数据源：文件路径或直接 resources 列表（测试用）
    # 构造期：AbilityTagNormalizer 预归一 target_ability 建 _by_tag 索引（组内 resource_id 升序）+ _all 全量升序
recommend_resources(ability_gaps: list[str], target_job: str | None = None) -> dict
    # target_job 仅接收，当前不参与匹配（预留）
```

### 输出结构（对齐 13 §6.2 + 追加 data_quality_flags）

```python
{
  "learning_resources": [{"title","type","url","target_ability","description"}],
  "job_resources": [],
  "certificate_suggestions": [...],
  "data_quality_flags": [...],
}
```

## 关键设计说明

### 归一复用（红线）

- `from .ability_normalization import AbilityTagNormalizer`（**同一模块对象**，无复制实现）
- 构造期每条资源 `target_ability` 归一：`mapped=False` 的资源跳过索引（真实数据 12 条全部合法）；
  命中 tag → 组内 `resource_id` 升序排序
- 运行期每个 gap 归一后与 `_by_tag` 精确匹配：`standard_tag` 相等为命中

### 匹配与排序（确定性定死）

| 场景                | 规则                                                          |
| ----------------- | ----------------------------------------------------------- |
| 空 gaps            | `_all`（resource_id 升序）→ 输出前 `[:10]` 截断                      |
| 有 gaps            | 按传入顺序逐 gap 匹配；命中资源入该 gap 分组（组内 resource_id 升序）；输出按 gap 顺序拼接 |
| gap 无命中           | `no_resource_for_tag:<gap>` flag（不虚构）                       |
| 非法标签（非字符串 / 归一失败） | 跳过该 gap + `unknown_tag:<gap>` flag（不炸整单）                    |

### flag 规则

- `certificate_suggestions` = 命中列表中 type=certificate 的 `target_ability`（截断前统计，认证建议不被学习条数上限砍掉）
- `job_resources` 恒空 + `job_resources_unavailable` flag（追加在 gap flag 之后，顺序固定）
- 输出字段仅五字段白名单，`resource_id`/`demo_only` 剔除（契约 13 §6.2 未定义）

## 测试清单（映射验收标准 1-11）

| 验收项                     | 测试方法                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| 1 有 gaps 顺序             | gaps_follow_input_order / cross_tag_multi_resources_preserve_group_order                     |
| 2 空 gaps 全推+截断          | empty_gaps_recommend_all_sorted_and_truncated（断言 res-011/012 被截掉）                            |
| 3 无命中 flag              | gap_without_resource_produces_flag（机器学习 → no_resource_for_tag）                               |
| 4 非法标签跳过                | unknown_tag_is_skipped_with_flag / non_string_gap_is_skipped_with_flag                       |
| 5 job_resources 恒空+flag | job_resources_always_empty_with_flag                                                         |
| 6 证书建议                  | certificate_suggestions_from_certificate_resources（PMP → ["PMP"]）                            |
| 7 归一命中变体                | normalization_variants_match_canonical_resource（Python/python/  PYTHON  /Python 编程/Python编程） |
| 8 字段剔除                  | output_fields_exclude_internal_marks（断言五字段白名单 + 无 resource_id/demo_only）                     |
| 9 上限 10 截断              | limit_truncation_when_over_ten_matches（12 条同标签注入 → 10 条）                                     |
| 10 确定性                  | output_is_deterministic（含无命中+非法标签混合输入，10 次逐字节一致）                                             |
| 11 回归                   | 全量 155 passed                                                                                |

已知边界说明（**对接 Agent 时须知**）：构造注入场景下"target_ability 未知标签"的资源在空 gaps 分支仍会全推（真实数据不触发）；证书建议不受学习资源上限截断（语义：建议列表不是资源槽）。

## 验证结果

| 套件                                            | 结果                             |
| --------------------------------------------- | ------------------------------ |
| `test_resource_service.py`                    | 12 passed                      |
| 全量 `backend/tests/ backend/app/agents/tests/` | 155 passed, 85 subtests（零回归破坏） |
| `compileall backend`                          | 无错误                            |

# 
