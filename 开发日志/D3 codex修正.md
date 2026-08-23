已完成 Hermes 报告要求的最小范围收尾，没有修改业务算法、Mock 适配器或执行 Git commit。

## 导入问题

已将测试改为规范包结构：

- 新增 [backend/tests/__init__.py](D:/vue/CareerPulse-Pro/backend/tests/__init__.py)
- 共享匿名数据和离线 LLM double 移到 [stage3_fixtures.py (line 8)](D:/vue/CareerPulse-Pro/backend/tests/stage3_fixtures.py:8)
- 两个测试改用包内相对导入：
  - [test_stage3_e2e.py (line 22)](D:/vue/CareerPulse-Pro/backend/tests/test_stage3_e2e.py:22)
  - [test_tbox_stage3_tools.py (line 24)](D:/vue/CareerPulse-Pro/backend/tests/test_tbox_stage3_tools.py:24)
- 新增 [pytest.ini (line 1)](D:/vue/CareerPulse-Pro/backend/pytest.ini:1)，使用相对源码根，不含本机绝对路径或代码级 `sys.path` 修改。

仓库根目录和 `backend` 目录均验证通过。

## httpx2 方案

最终不额外锁定 `httpx2`，依据如下：

- [test_mcp_server.py (line 11)](D:/vue/CareerPulse-Pro/backend/tests/test_mcp_server.py:11) 确实直接导入 `httpx2`。
- 官方 `mcp==2.0.0` 包元数据明确声明：

```
Requires-Dist: httpx2>=2.5.0
```

- 当前由 MCP 依赖自动解析得到 `httpx2==2.12.0`。
- `pip check` 返回 `No broken requirements found`。
- 项目已经在 [requirements.txt (line 12)](D:/vue/CareerPulse-Pro/backend/requirements.txt:12) 固定 `mcp==2.0.0`，重新安装会自动安装 `httpx2`，不是依赖 Hermes 手工额外安装。
- 没有增加重复的 `httpx/httpx2` 测试实现。

## 工具目录

已更新 [13_MCP_TOOL_CATALOG.md (line 8)](D:/vue/CareerPulse-Pro/docs/a02/13_MCP_TOOL_CATALOG.md:8)：

- 明确当前只注册四个标准 MCP 工具。
- 七个历史名称逐项标记为“历史语义参考”或“规划中、尚未注册”。
- 总览改为[历史/规划工具清单 (line 752)](D:/vue/CareerPulse-Pro/docs/a02/13_MCP_TOOL_CATALOG.md:752)。
- 修正了历史路径说明中“尚未接入 PathAgent/MCP”的过时表述。

## Token 检查

检查结果正常：

- [.env.example (line 29)](D:/vue/CareerPulse-Pro/.env.example:29) 中 `MCP_API_TOKEN` 为空。
- 文档使用 `example-local-token-change-me`、`<deployment-secret>` 等明确示例。
- 测试只使用 `test-only-mcp-token`。
- 暂存区为空，暂存差异中没有 Token。
- 测试输出和日志没有打印 Token。
- 生产 Token 继续通过 `MCP_API_TOKEN` 环境变量配置。

## 验证结果

| 验证                                     | 结果                          |
| ---------------------------------------- | ----------------------------- |
| 仓库根运行 `test_tbox_stage3_tools.py`   | 5 passed                      |
| backend 运行 `test_tbox_stage3_tools.py` | 5 passed                      |
| MCP 定向测试                             | 6 passed                      |
| 阶段3 E2E                                | 10 passed                     |
| `backend/tests` 全量                     | 86 passed，71 subtests passed |
| `pip check`                              | 通过                          |
| `compileall app tests scripts`           | 通过                          |
| `git diff --check`                       | 退出码 0                      |
| MatchService / PathService diff          | 无                            |
| `tbox_adapter.py` diff                   | 无                            |

## 本轮修改文件

- `backend/pytest.ini`
- `backend/tests/__init__.py`
- `backend/tests/stage3_fixtures.py`
- `backend/tests/test_stage3_e2e.py`
- `backend/tests/test_tbox_stage3_tools.py`
- `docs/a02/13_MCP_TOOL_CATALOG.md`
- `task_plan.md`
- `findings.md`
- `progress.md`

可以进入 Git commit 前的选择性暂存阶段。当前暂存区仍为空，而且工作区包含前序阶段的大量改动及 `backend/.idea/`，因此应按预期文件选择性 `git add`，不要直接提交整个工作区。本轮未执行 commit。