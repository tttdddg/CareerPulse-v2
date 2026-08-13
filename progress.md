# 阶段3第1步进度

## 2026-08-13
- 已读取并启用 `planning-with-files` 技能。
- 已确认根目录、工作树状态及已有计划文件位置。
- 会话恢复脚本缺失，已改为手动恢复检查。
- 正在进行仓库与后端结构盘点。
- 已枚举后端、文档、测试文件并定位所有 Pydantic/FastAPI/CareerState/简历相关代码。
- 已检查现有画像与岗位 Schema、种子模型、CareerState 和传统请求响应 Schema。
- 已新增唯一能力维度枚举、统一请求/领域/响应 Schema 及合法/非法样例测试。
- 已将 `app/schemas/` 正式化为包，并兼容导出旧 `schemas.py` 的请求响应类型。
- 新 Schema 测试 5/5 通过；既有 ProfileAgent 回归 7/7 通过。
- Service 测试因当前 Python 环境缺少 requirements 中的 `psycopg2` 而在收集阶段阻断。
- `compileall`、新旧 Schema 导入兼容检查、`git diff --check` 均通过。
- Mock 全链路 7 项中 5 项通过、2 项失败；诊断确认未配置 `A02_LLM_API_KEY` 导致 ProfileAgent/JobAgent 按设计 fallback，最终状态为 `partial`，与本次 Schema 变更无关。

## 阶段3第2步

- 已恢复第1步未提交变更并确认不会覆盖。
- 正在检查现有模型调用、配置、日志和测试替身。
- 已完成现有统一 Client、配置、环境变量、直调 SDK、日志与异步测试方式盘点。
- 已扩展现有 `httpx` Client，完成 messages、结构化重试、JSON fence、Mock、fallback、工厂注入、分类异常和安全日志。
- ProfileAgent/JobAgent 已迁移到 `generate_structured`，结构重试职责由 Client 统一承担。
- 学生路由已移除 `AsyncOpenAI` 直调；匹配 Service 已移除同步 `OpenAI` 直调并恢复确定性评分。
- Client 单测 12/12、ProfileAgent 回归 7/7、阶段3 Schema 5/5 通过；编译、配置工厂、SDK 直调扫描及 diff 检查通过。

## 阶段3第3步

- 已恢复前两步未提交改动并确认继续增量开发。
- 正在盘点 ProfileAgent 相关数据与调用链。
- 已新增确定性 ProfileService，复用现有标签字典/别名，完成资料合并、证据映射、等级/置信度、完整度、竞争力和追问计算。
- 已将 ProfileAgent 与独立 Prompt 切换为统一画像流程；LLM仅输出候选证据，Service过滤无依据候选并重算所有分值。
- 已覆盖用户指定七类场景，并增加Prompt安全、评分确定性与日志隐私测试。
- 48个有效标准标签已全部覆盖七个维度；明确项目/比赛/实习/工作证据会同步形成项目实践维度，但不会新增无证据标签。
- Profile 10项、LLM Client 12项、Schema 5项、标签归一化5项、确定性匹配14项测试均通过。
