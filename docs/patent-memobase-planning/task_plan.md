# CareerPulse 第二件发明专利成文计划

## 目标

依据 CareerPulse 项目文件夹与 `12 3 4 5亮点.md`，完成第二件 Memobase 方向的证据约束型中国发明专利交底书和正式申请文件；不把开源 Memobase 本体、通用长期记忆或未经材料支持的实验结果包装为本项目发明。

## 路径判定

- `source_format`: `mixed-project`
- `task_mode`: `full-draft`
- `invention_type`: `algorithm-software`
- `case_id`: `career-temporal-evidence-memory`
- `patent_type`: `invention`
- `start_mode`: `from_zero`

## 阶段

- [completed] 阶段 1：读取技能规则、亮点文件与项目证据，建立案卷、术语表和证据台账
- [completed] 阶段 2：完成轻量现有技术检索、D1/D2 对比和发明点门禁
- [completed] 阶段 3：生成技术交底书、附图、公式规划和 DOCX
- [completed] 阶段 4：生成权利要求书、说明书、摘要、说明书附图和摘要附图
- [completed] 阶段 5：执行一致性、支持性、隐私、结构检查及项目测试
- [completed] 阶段 6：更新案卷、问题清单和交付说明

## 发明边界

- 不申请 `memodb-io/memobase` 的公开基础能力或品牌名称。
- 保护重点暂定为职业阶段化的时序证据记忆、事实/确定性结果/模型推断分层、冲突保留与消解、角色及隐私约束投影、预算约束上下文装配。
- 代码中已存在的画像合并、历史查询、职业状态、反馈和日志仅作为证据基础；拟新增机制必须标记为 `needs-confirmation`，无支持特征不得进入正式权利要求。
- 不输出真实简历、身份信息、令牌或密钥。

## 错误记录

| 错误 | 尝试 | 处理 |
|---|---:|---|
| `planning-with-files/scripts/session-catchup.py` 不存在 | 1 | 记录后继续；使用独立规划目录，不覆盖第一件专利规划文件 |
| Mermaid 浏览器渲染因环境返回 `WinError 5 拒绝访问` | 1 | 保留 Mermaid 源码；改用申请附图确定性黑白渲染器生成图1、图2及摘要附图 |
| LibreOffice `soffice.exe` 不在 PATH，Word COM 导出在当前会话返回 `CO_E_SERVER_EXEC_FAILURE` | 2 | 完成 DOCX 结构/媒体检查并逐幅检查确定性附图；将文档渲染限制列入交付风险，待本机 Word/LibreOffice 可用时复核分页 |
