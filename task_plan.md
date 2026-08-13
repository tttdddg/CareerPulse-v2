# CareerPulse A02 阶段3开发计划

## 目标
基于现有 FastAPI、Pydantic、数据库、CareerState、简历解析和测试结构，建立统一能力维度与学生画像、岗位画像、职业趋势、Agent 响应 Schema，并保持接口兼容。

## 阶段
- [x] 1. 完整盘点仓库与现有数据结构
- [x] 2. 设计兼容的请求/领域/响应 Schema 关系
- [x] 3. 实现统一能力维度与核心 Schema
- [x] 4. 补充合法/非法样例及单元测试
- [x] 5. 运行测试并检查变更范围
- [x] 6. 汇总交付、风险与后续步骤

## 第2步：统一 LLM Client
- [x] 1. 盘点现有模型调用、配置、环境变量、异步客户端、日志和测试
- [x] 2. 设计兼容的统一 Client、配置与异常/兜底契约
- [x] 3. 扩展现有 LLM Client，并迁移现有 Agent 依赖
- [x] 4. 补充成功、JSON/Schema 错误、超时、重试与 Mock 测试
- [x] 5. 运行相关回归并检查敏感信息与变更范围
- [x] 6. 汇总配置、示例、重试逻辑、测试结果和后续内容

## 边界
- 不开发或修改百宝箱、MCP、Tool Calling、`/api/tbox/chat`。
- 不删除既有字段；公共字段变化需同步 `API_CONTRACTS.md`。
- 不修改不属于本任务且已有他人改动的文件。
- 不自动提交 Git。

## 错误记录
| 错误 | 次数 | 处理 |
|---|---:|---|
| 技能的 `scripts/session-catchup.py` 文件不存在 | 1 | 通过 `git status` 和现有计划文件手动检查会话状态 |
| 在 `backend/` 工作目录下误用 `backend/...` 相对路径，导致一组只读文件未找到 | 1 | 返回仓库根目录后使用正确路径；版本检查结果有效 |
| `app/schemas.py` 与无 `__init__.py` 的 `app/schemas/` 冲突，目录 Schema 无法导入 | 1 | 将目录正式化为包，并在包入口兼容导出旧 API Schema |
| 全量 unittest discover 导入数据库模块时缺少 `psycopg2` | 1 | 记录为环境依赖问题；先运行相关的纯 Schema/Agent/Service 测试 |
| 从仓库根目录启动后端 unittest，`app` 不在模块路径 | 1 | 改在 `backend/` 下用 discover 指定测试目录 |
| Agent 迁移补丁因历史字符编码内容无法匹配 `_repair_prompt` 段落 | 1 | 改用小范围 ASCII 上下文，只替换 `_execute`，不触碰历史提示文本 |
| 在 `backend/` 工作目录进行死代码扫描时误用 `backend/app` 前缀 | 1 | 改用正确的 `app/` 路径；同批测试与 diff 检查结果有效 |
