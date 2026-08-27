# 阶段4 MCP 仓库侧接入执行日志（2026-08-27）

- 已完整读取 `planning-with-files` 技能并启用文件化计划。
- session catchup 脚本缺失；已记录错误并通过现有计划、发现、进度和 Git diff 恢复上下文。
- 已确认任务开始时 MCP Server、MCP 测试、API 契约和集成说明存在上一任务未提交的扁平参数改动，本轮将保留并增量修改。
- 已建立五阶段执行计划，当前进入实现与测试契约审计。
- 已完整读取现有 MCP Server、MCP 基础 Schema、阶段4内部 Schema 及三个 handler 实现。
- 已确认三个 handler 和严格结果 envelope 可直接复用；注册层只需构造 Request 并调用对应 service 方法。
- 已确认注册后的统一 `extra=forbid` Schema 重建循环会自动覆盖新增工具；不会为测试放宽任何 Schema。
- 已完整读取 MCP 协议测试，确认需把工具集合/远程数量从 4 更新为 7，并将真实 Training/Feedback Agent 注入测试 Orchestrator。
- 已核查三份 MCP 公共文档，确认阶段4旧规划输入与真实 session-state 契约不一致，需同步为真实注册状态而非仅修改标题。
- 已冻结三个 MCP 公开签名：Training 合并模式、Resource 纯 session-state、Feedback 严格 1–5 rating；不新增或改写业务字段。
- 已决定把 Server 能力版本更新为 `stage4-mcp-v1`，同时在文档明确其不代表百宝箱现场配置完成。
- 已核对公共契约修改流程；本轮会新增 ADR-003 记录阶段4三工具注册决策，满足冻结文档的变更要求。
- 已注册三个阶段4薄适配器、升级 Server 元信息，并扩展 MCP 测试 fixture/Schema/连续链/失败覆盖。
- 首轮 MCP 定向测试 `10 passed, 1 error`；唯一错误是新测试误用内部返回对象下标，协议实现和三个新工具成功链均已通过，正在改用官方 Client 路径。
- 修正失败测试后，MCP 定向测试 `11/11` 通过；阶段4注册、Schema、成功/失败、连续 session 和原鉴权均已获得协议级证据。
- 已核对 `05_AGENT_CONTRACTS.md`，确认需随公共 MCP 契约同步少量 Training/Feedback 真实边界，避免保留已不存在的默认分数/Redis 等规划声明。
- 已新增 ADR-003，并同步 API、Agent、MCP 工具目录和接入说明；正在用实际 Schema/Service 输出做最终文档复核。
- 已直接打印运行时 MCP Schema，确认 `tools/list=7`、三个新工具均 `additionalProperties=false` 且必填/枚举/rating 边界正确。
- 已对照 ResourceService/FeedbackService 真实返回字段复核文档，不声明未实现的岗位资源或保存 fallback。
- 已完成 ADR-003、API/Agent 契约、MCP 工具目录和接入说明同步；文档明确总数 7、Training 合并模式、真实请求/响应/错误及平台现场未完成边界。
- `git diff --check` 当前通过，仅有工作树既有 LF/CRLF 提示；进入分组与完整回归阶段。
- 阶段4分组回归 29/29 通过（MCP 11 + 内部工具 14 + 最终 E2E 4）。
- 阶段3分组回归 26/26 通过（MCP 11 + HTTP 平台工具 5 + 阶段3 E2E 10）。
- `backend/tests` 完整发现测试 180/180 通过。
- `backend/app` 内嵌套件 70/77 通过；7 个未通过均为既有 Profile prompt 缺失的直接/级联失败，已分类记录，不越界修复。
- Match/Path/Training/Feedback Agent 适用回归 60/60 通过。
- compileall 与 `git diff --check` 通过；受保护的 Service/handler/Orchestrator/main/platform 无 diff。
- 已逐段复核 Server diff，确认任务前扁平参数改动未被覆盖或回退。
- 最终 MCP 再跑 11/11；阶段4文档 8 个 JSON 块解析通过；运行时 `tools/list` 精确为 7 个预期名称。
- 指定活动文档无过期“4工具/阶段4未注册”声明；feedback_schema 工作树与 HEAD hash 相同，无交付内容差异。
- 本轮仓库侧阶段4 MCP 接入完成，未执行 Git commit，未进入百宝箱/Cloudflare/Token/现场配置。

---

# MCP 百宝箱入参兼容修复执行日志（2026-08-27）

- 已读取 planning-with-files 技能并启用文件化计划。
- 技能引用的 session-catchup 脚本不存在；已记录错误，改由现有规划文件和 Git 状态恢复上下文。
- 已确认现有规划文件属于历史任务，本轮仅追加记录，不覆盖旧内容。
- 已定位根因：MCP SDK 从两个注册函数的 Pydantic 参数注解生成嵌套对象，平台传 String 时在函数调用前校验失败。
- 已核对两个输入模型真实字段；Student 输入不是单文本模型，不能按“单文本字段”例外继续公开 `student_input: str`。
- 已确认共享 MCP 工具 Service 可保持不变，适配函数内部重建 Request 即可。
- 已核对所有现有 MCP 调用点、远程 HTTP 传输测试与契约文档；修改范围冻结为 MCP 注册、MCP 测试及两份直接相关文档。
- 已将两个 MCP 工具改为扁平基础类型签名，并在适配层内部构造原 `StudentProfileInput` / `TargetJobInput`。
- 已新增两项普通 JSON 调用测试，更新四工具链调用和 `tools/list` 无 `$ref/$defs` 断言。
- 已同步公共 API 契约中的 MCP 小节和百宝箱接入 JSON 样例；HTTP API 契约明确保持不变。
- MCP 定向套件首轮 `8/8` 通过，包含两个新增扁平 JSON 调用、四工具完整链、Schema、远程鉴权和 HTTP 一致性回归。
- 已直接输出注册后的两个 input schema，确认无 `$ref/$defs` 和业务 object 入参。
- 追加阶段3 HTTP 工具 `5/5`、阶段3 E2E `10/10` 回归，全部通过。
- backend 全套回归 `177/177` 通过；没有历史 Profile prompt 失败，本工作树当前基线全绿。
- compileall、`git diff --check` 和禁止范围 diff 审计通过；Service、平台/鉴权、HTTP 挂载及输入模型定义无改动。
- 本次兼容修复完成，未执行 Git commit、部署或百宝箱现场配置修改。

---

# D4-2.6 阶段4最终端到端验证执行日志

## 2026-08-24

- 已完整读取 planning-with-files 技能；其 session-catchup 脚本为前序已知缺失项，本轮不重复失败。
- 已恢复 D4-2.1～D4-2.5 未提交成果、测试清单和 `236 passed / 96 subtests，5 failed` 的前序基线。
- 已建立 D4-2.6 分阶段验收计划，正在盘点现有端到端覆盖与离线 LLM 测试夹具。
- 第一轮覆盖盘点完成：既有测试对单节点和异常覆盖充分，但缺少一个同 session 的阶段3 Match/Path → 阶段4 Training/Resource/Feedback 连续内部验收测试。
- 决定只新增连续接线测试，并复用已有 Service 异常/确定性测试，不复制冻结算法断言。
- 已冻结连续验收设计：真实 Match/Path Service、合法五档 mock LLM、真实 Training/Resource/Feedback Service、同 session State 持久化。
- 已确认 ProfileAgent 5 项失败根因仍是阶段3 prompt 文件缺失；该问题不是 D4 新增接线，按范围不补写未知 prompt，将在最终结果中独立披露。
- 已用真实 MatchService/TrainingService/ResourceService 计算匿名 fixture 的确定性样本，确认真实 gaps 能命中训练任务和资源，并自然覆盖 no-resource/job-unavailable flags。
- 已确认非法 coverage 与数值污染在 Agent→Service 边界采用两种不同 fallback 路径；将加入工具级稳定性断言。
- 已新增 `backend/tests/test_stage4_final_e2e.py`，包含完整连续主链、非法 coverage、数值污染和 unknown resource tag 四项离线验收。
- 新增最终 E2E 首轮结果：`4 passed`；未发现需要修改业务代码的 D4 接线错误。
- D4 相关 Agent/State/tool/E2E 与三个冻结 Service 组合回归：`130 passed / 25 subtests`。
- 阶段3 Match/Path、HTTP E2E、TBox tools、MCP server 回归：`40 passed`。
- ProfileAgent 定向结果：`5 failed, 5 passed`；5 项全部可归因于两个既有 prompt 文件缺失，未修改测试或越界补写 prompt。
- 定向阶段未发现 D4 接线实现错误，进入完整套件、compileall 与静态审计。
- 完整 `tests + app/agents/tests + app/platform/tests`：`245 passed / 96 subtests，7 failed`。
- 7 项均由既有 Profile prompt 缺失直接或级联导致（5 ProfileAgent + 2 历史 Mock 全链）；未改测试预期，继续运行精确排除该既有阻塞的适用全量与静态验收。
- 精确排除 7 个已知阻塞节点后的适用全量：`245 passed / 96 subtests`。
- 三个冻结 Service 独立回归：`61 passed / 14 subtests`。
- `python -m compileall -q app tests` 通过。
- 静态审计确认真实路径不引用 `call_mock_tool`，阶段4无 MCP 注册、无 ResourceAgent、无网络测试客户端。
- 隐私审计确认 user_answer/comments 不持久化到 State/Agent log；调用账本仅保存请求 fingerprint。
- 禁止范围审计和 `git diff --check` 通过；冻结 Service、platform/API、MCP server、mock_tools、migration 无 diff。
- 阶段4五个新增/重建测试文件共 69 个测试函数；D4-2.6 仅新增最终 E2E 测试与报告材料，未修改业务实现。
- 测试与静态验收阶段完成，开始写入最终开发日志报告。
- 按 D4-2.5 相同范围复跑：`240 passed / 96 subtests，5 failed`，较前序 `236 passed` 恰好增加本轮 4 个通过项，既有 5 个失败不变。
- 已写入 `开发日志/D4 阶段4最终内部链路验收报告.md`，包含架构、调用链、文件、测试、隐私、fail-safe、mock 审计、能力清单和未执行事项。
- 最终禁止范围审计为空，`git diff --check` 通过；D4-2.6 完成，未执行平台接入、部署或 Git commit。

---

# D4-2.5 Orchestrator 与内部工具链执行日志

## 2026-08-24

- 已重新读取 planning-with-files 技能；session-catchup 脚本已知不存在，本步骤不重复调用。
- 已恢复 D4-2.1～D4-2.4 未提交成果和已知 ProfileAgent prompt 阻塞基线。
- 正在核查阶段3 Orchestrator、内部工具、API/MCP、Schema、错误 envelope、mock 与 demo 模式。
- 已确认冻结阶段4动作名及其“尚未平台注册”状态；训练生成/评分必须共用 `generate_and_score_training`。
- 已读取阶段3 transport-neutral tool service 与两套 Schema；内部阶段4接口应沿用 run_stage + State + 严格 envelope，但不应进入 MCP server 或 platform ledger。
- 已确认 mock_tools 与真实 API/MCP 无调用关系；正式内部路径可新增独立服务而无需删除 mock，也无需修改 MCP server/platform router。
- 已冻结实现方向：扩展现有 transport-neutral tool service 的未注册阶段4方法；Orchestrator 临时输入注入后恢复；资源动作直接使用冻结 ResourceService，不新增 ResourceAgent。
- 已新增未注册的严格内部工具 Schema：训练生成/评分、资源推荐、成长反馈请求与统一结果 envelope。
- CareerOrchestrator.run_stage 已支持 Training/Feedback 的临时 stage_input，Agent 完成后恢复原 student_input 再持久化。
- CareerMCPToolService 已加入三个冻结名称对应的内部方法（训练方法含 generate/score 两模式），复用 session/identity/trace/幂等/超时/安全失败；MCP server 未改。
- 已新增 14 项内部工具链测试（含 trace 幂等回放）；首轮 13 项已通过，正在复跑完整新测试。
- 内部工具测试最终 `14 passed`；阶段3 MCP/HTTP tool/E2E `21 passed`。
- 完整回归 `236 passed / 96 subtests，5 failed`，5 项仍是既有 Profile prompt 缺失；适用全量 `231 passed / 96 subtests`。
- 三个冻结 Service 独立回归 `61 passed / 14 subtests`。
- compileall、diff check 和禁止范围审计通过；Service、API、platform、MCP server、mock_tools、migration 无差异。
- 已新增 `开发日志/D4-Orchestrator与内部工具链完成报告.md`。
- D4-2.5 完成，未执行百宝箱注册、MCP tools/list 扩展、HTTP 平台路由、ngrok、VM、域名或部署。

---

# D4-2.4 CareerState 统一接入执行日志

## 2026-08-24

- 已读取 planning-with-files 技能并恢复上一步上下文；已知 session-catchup 脚本缺失，本轮不重试。
- 已确认本步骤只统一阶段4状态，不修改三个冻结 Service，不做百宝箱注册。
- 首次规划文件组合补丁因实际措辞不同未应用；已读取精确内容并改用小范围补丁。
- 正在核查 CareerState、持久化、Profile / Match / Path 和阶段4 Agent 的状态读写。
- 核查确认数据库持久化完整 State JSON；三个阶段4顶层容器已存在，无需数据库迁移或新增同义字段。
- 已决定以 CareerState 深拷贝访问器统一最近任务/评分/gap/成长快照读取；completed 计数和反馈 priority 不建立重复状态。
- 已实现阶段4状态入模/Agent 写入隔离，并让 TrainingAgent、FeedbackAgent 改用统一状态读取接口。
- 已新增 CareerState 阶段4测试，覆盖旧状态、原字段写法、三类结果、最近训练语义和跨 session 隔离。
- 首轮状态 + Training/Feedback Agent 定向执行中，阶段4相关项全部通过；附带的旧 Mock 全链 2 项因既有 Profile prompt 缺失失败，未发现状态改动新增失败。
- 补充旧状态 latest_score 悬空时回退到最后可用任务的兼容语义，并增加 SQLite 持久化恢复测试。
- 首次持久化测试因系统临时目录不在 workspace 可写范围而失败；已改用项目忽略的 `backend/.runtime` 临时目录，不修改业务实现。
- `.runtime` 内的 `TemporaryDirectory` 仍受 Windows ACL 影响；已改为与 stage3 测试相同的 `.runtime/tests` UUID 文件及 finally 清理方式。
- CareerState 新增 10 项测试最终全绿；阶段4与 Match/Path/stage3 E2E 定向回归 `80 passed / 11 subtests`。
- 完整回归 `222 passed / 96 subtests，5 failed`；失败仍全部来自既有 ProfileAgent prompt 缺失。
- 排除既有 ProfileAgent 阻塞文件的适用全量回归 `217 passed / 96 subtests`。
- 三个冻结 Service 回归 `61 passed / 14 subtests`，compileall 与 diff check 通过。
- 已新增 `开发日志/D4-CareerState接入完成报告.md`；冻结 Service、CareerOrchestrator、platform 均无差异。
- D4-2.4 完成，未执行 Git commit、百宝箱注册或部署。
- 首次失败测试遗留的已忽略 `.runtime/tmpt1cv4y8_` 受 Windows ACL 保护无法删除；未申请扩大权限，不影响 Git 差异或验证结果。

---

# D4-2.3 FeedbackAgent 真实化执行日志

## 2026-08-24

- 已读取 planning-with-files 技能；已知 session-catchup 脚本缺失，按规则不重复失败。
- 已读取 D4-2.2 规划、发现、进度和当前 Git 状态，确认前序未提交成果需保留。
- 正在核查 FeedbackService、FeedbackAgent、上下文来源、Schema/Prompt 和冻结契约。
- 第一轮核查确认 FeedbackAgent 仍为硬编码占位，FeedbackService 已完整负责校验、存储、调权和成长快照。
- 已确认 CareerState 现有字段足以做最小投影；completed 统计没有专用可靠字段，需继续按契约核对是否固定使用 0。
- 契约核对确认 completed 两项在缺少可靠统计时应传 0；不把计划阶段或单个 latest_score 推断成累计完成数。
- 已决定 Service 成功后才做可选一句 LLM 说明，失败则模板回退；Service 五个字段不修改，平台工具不注册。
- 已冻结参数来源：match_result skill_gaps/overall_score、最近已评分 TrainingTask target_abilities、student_profile abilities；两项 completed 统计安全默认 0。
- 已确定输入兼容 `student_input.feedback` 与旧 `ratings`，state session/user 不允许请求覆盖；comments 隐私最终交给 Service。
- 已新增 feedback_schema 与 feedback explanation prompt。
- 已将 FeedbackAgent mock 整体替换为真实 FeedbackService 调用、上下文投影、严格结果验证、可选一句解释和空 fallback。
- 已新增 19 项完全离线 FeedbackAgent 测试；与 FeedbackService 原 20 项联合运行 `39 passed`。
- 完整回归首轮 `211 passed, 5 failed`；5 项仍是既有 ProfileAgent prompt 缺失，本步骤不处理。
- 已追加缺失 session_id 的隔离覆盖：正常 CareerState 会先拒绝该状态，测试仅绕过模型构造以验证 Agent 不吞 FeedbackService error。
- 最终定向测试 `40 passed`；排除既有 ProfileAgent 阻塞项的适用回归 `207 passed`。
- 补测后的完整回归 `212 passed, 5 failed`；5 项仍为既有 ProfileAgent prompt 缺失。compileall 通过。
- 已新增 `开发日志/D4-FeedbackAgent实现完成报告.md`，记录 mock 移除、每个参数来源、职责边界、测试和已知边界。
- 最终 `git diff --check` 无 whitespace error（仅 LF/CRLF 提示），冻结 Service/Orchestrator/platform 无差异。
- D4-2.3 全部阶段完成，未执行 Git commit、平台工具注册或部署。

---

# 历史：D4-2.2 ResourceService 业务接入执行日志

## 2026-08-24

- 已读取 planning-with-files 技能并启用文件化计划。
- 技能声明的 session-catchup 脚本不存在；已记录错误，改用 Git 状态与现有规划文件恢复上下文。
- 已确认 D4-2.1 工作区成果仍未提交；本步骤将只做增量修改，不回退已有变更。
- 正在核查 ResourceAgent、真实 match_result/target_job 所在层、skill_gaps 顺序与推荐结果存放方式。
- 第一轮核查确认仓库无 ResourceAgent；ResourceService 已包含完整推荐与标签处理逻辑。
- `PathAgent` 已消费 match_result/job_profile 并写入 learning_plan，且现有 resource/certificate 字段为空占位，当前是最小接入候选。
- 继续核对冻结契约后，确认 `05_AGENT_CONTRACTS.md` 与 README §13.4 明确由 TrainingAgent 调用 ResourceService；最终消费位置因此确定为 TrainingAgent，而不是 PathAgent。
- CareerState 已有 `resource_result`，Orchestrator 也会将其放入 final_report；无需本轮改 State 或 Orchestrator。
- MatchService 已按 priority 计算结果排序并赋序号；接入层只按列表顺序取 dimension。
- 已读取当前 TrainingAgent：generate/score 分支明确，score 成功后可最小增加 ResourceService 调用和 `resource_result` 输出。
- 已确认 API 状态流要求 resource_result 在用户完成训练后出现，因此不在训练题生成阶段提前推荐。
- 已实现 TrainingAgent score 成功后调用 ResourceService，并把四字段裸 dict 写入 state.resource_result。
- 已新增 ResourceService 依赖注入和最低限度结果完整性检查；未导入或复制 AbilityTagNormalizer。
- 已在 TrainingAgent 离线测试中增加真实 MatchService 结果来源、顺序、空 gaps、各类 flag、内部字段不暴露、无额外 LLM 调用和 normalizer 不复制覆盖。
- 定向回归 `33 passed`：冻结 ResourceService 12 项、TrainingAgent 21 项全部通过。
- 完整回归为 `192 passed, 5 failed`；新增 6 项全部通过，5 项仍是既有 ProfileAgent prompt 文件缺失，未越界修复。
- 排除既有 ProfileAgent 阻塞项后的适用回归 `187 passed`；`compileall app tests` 通过。
- 一次组合静态检查因从 backend 目录错误引用相对 docs 路径而最终退出 1；从仓库根正确复核后无 ResourceAgent 匹配，测试和编译子命令本身均成功。
- 冻结 Service、Orchestrator 和 platform 目录无 diff。
- 已新增 `开发日志/D4-ResourceService业务接入完成报告.md`，记录消费层选择、输入来源、输出透传、测试与边界。
- 最终定向复跑仍为 `33 passed`；`git diff --check` 无 whitespace error（仅现有 LF/CRLF 提示），冻结目录无差异。
- D4-2.2 全部阶段完成，未执行 Git commit、百宝箱注册或部署。

---

# 历史：标准 MCP Server 执行日志

## 2026-08-24 Hermes 提交前最小收尾

- 已读取 planning-with-files 技能；catchup 脚本缺失，改由计划文件和 Git 状态恢复上下文并记录失败。
- 已复现仓库根运行 `test_tbox_stage3_tools.py` 时 `No module named 'app'`；backend 目录原本 5/5 通过，但其跨测试导入依赖启动目录的命名空间包行为。
- 已新增 backend 级 pytest 配置、测试包标记和共享 `stage3_fixtures.py`，两个阶段3测试改为包内相对导入。
- 已核对 `mcp==2.0.0` 本地包 METADATA：正式依赖 `httpx2>=2.5.0`；隔离安装版本为 2.12.0，因此不新增重复客户端或额外直接 pin。
- 已更新 MCP 工具目录：当前标准 MCP 只注册四个工具，七个旧名称逐项标为历史/规划且尚未注册。
- 修复后仓库根 `test_tbox_stage3_tools.py` 5/5 通过；backend 目录 5/5 通过。后续将用禁用 pytest cache provider 的固定配置重跑最终验证，避免受受限缓存目录警告干扰。
- 最终验证：MCP 定向 6/6、阶段3 E2E 10/10、HTTP Tool API 5/5、`backend/tests` 86/86（另 71 个 subtests）全部通过；`pip check` 无断裂依赖。
- `compileall app tests scripts` 通过，`git diff --check` 退出码 0；MatchService、PathService、`tbox_adapter.py` 无 diff。本轮未修改 MatchAgent/PathAgent，工作区中这两个文件仍有前序任务留下的既有小 diff。
- Token 扫描确认 `.env.example` 的 `MCP_API_TOKEN` 为空，文档仅含 `example-local-token(-change-me)`/占位符，测试仅含 `test-only-mcp-token`；暂存区为空且无 Token 匹配，测试输出未打印 Token，生产仍从环境变量读取。
- 未执行 Git commit、部署、健康端点、deprecated 目录或全仓库 `.gitattributes` 变更。

## 2026-08-21（当前任务）

- 已完整读取 `planning-with-files` 技能并启用文件化计划。
- 技能说明引用的 session catchup 脚本不存在；已记录错误，并通过 Git 状态与既有规划文件恢复上下文。
- 已确认工作区存在前序阶段3与 HTTP Tool API 的大量未提交成果；本任务不会回退或提交这些改动。
- 已建立本次 MCP Server 的分阶段计划、约束和待确认清单。
- 已读取 AGENTS、Python/依赖、后端目录、主应用工厂、CareerState 和 CareerOrchestrator。
- 已确认 Python 3.11.15、依赖文件未锁 MCP SDK、状态持久化和分阶段真实 Agent 调用入口可复用。
- 已审计 Base/Profile/Job/Match/Path Agent 及正式 HTTP 平台 Schema/测试符号，确认工具命名存在历史映射，但真实业务入口和确定性输出模型均可复用。
- 已审计本地分步 API、正式 HTTP 工具实现和持久化账本，决定 MCP 复用 Orchestrator/Agent 与现有平台调用日志，而不通过内部 HTTP 回环或修改 AgentLog 公共字段。
- 已核对官方 MCP Python SDK/PyPI/ASGI/客户端文档，选择稳定固定版 `mcp==2.0.0`，传输只实现 Streamable HTTP，不无依据增加 SSE。
- 已确认宿主预装 MCP 1.26.0；将使用项目隔离运行时验证 2.0.0，不直接升级共享环境。
- 已隔离安装并实查 MCP 2.0.0 源码/API，确认可使用官方 `MCPServer`、原生 TokenVerifier、Streamable HTTP ASGI 与官方 Client。
- 阶段1审计完成；已冻结四工具名称映射、共享 MCP tool service、trace/log 复用、状态/fallback、官方鉴权和 `/mcp` 精确挂载方案。
- 已新增 MCP 严格输入/结果 Schema、传输无关真实工具服务、官方 MCPServer 四工具注册和静态 Bearer ASGI 保护。
- 已将可选 MCP Server 集成到现有 FastAPI lifespan，默认关闭，启用时精确提供 `/mcp`；编译和初始化烟测通过。
- 已补充 MCP 开关、Token、host/port/path 与 DNS-rebinding allowlist 环境变量样例。
- 已确定用官方 Client legacy 模式验证 initialize，并通过 httpx2 ASGITransport 走完整 Streamable HTTP Bearer 线路。
- MCP 首轮测试 4/5 通过；唯一失败是 SDK 动态根参数模型未宣告 extra-forbid，已收紧运行时模型并增加未知 score 字段拒绝覆盖。
- 修正后 MCP 测试 5/5 通过：官方 initialize/list/call、四工具串联、Schema、HTTP 结果一致性、前置错误、未知字段拒绝、Bearer 和真实远程 ASGI 传输均已验证。
- 已审计 API 契约、架构、旧 MCP 工具目录、HTTP 接入指南和百宝箱需求状态，明确采用加法文档更新并保留平台现场未验证项。
- 完整 `backend/tests` 回归 85/85 通过；compileall 与 `git diff --check` 通过。首次 app discovery 命令 top-level 错误，已记录并将用正确包根重跑。
- 最终新增配置测试后 MCP 为 6/6；MCP + 正式 HTTP 定向联合测试 11/11 通过。
- 最终 `backend/tests` 全量回归 86/86 通过；compileall、迁移/静态数据 `--check`、隐私检查和 `git diff --check` 全部通过。
- 正确包根运行 `backend/app`：34 通过、2 个历史 Mock 基线失败，失败内容与本任务开始记录一致且不涉及 MCP/正式 HTTP。
- 已同步架构、API_CONTRACTS、MCP_TOOL_CATALOG、TBOX_REQUIREMENTS，并新增完整 MCP 启动/鉴权/工具/样例/测试/公网/百宝箱填写说明。
- 已确认 MatchService/PathService 无 diff、没有 SSE 实现、没有真实凭据、没有 Git commit。

---

## 历史任务执行日志（百宝箱最小 HTTP 接入）

## 2026-08-21

- 已完整读取 `planning-with-files` 技能说明并启用文件化计划。
- session catchup 脚本缺失，命令失败；已记录在 `task_plan.md`，不再重复。
- 已读取上一阶段规划/发现/进度，恢复阶段3验收基线。
- 已将三份规划文件切换为本次百宝箱最小接入任务。
- 已检查 Git 状态/diff、后端与文档文件清单、平台/日志/鉴权/超时相关符号。
- 确认上一阶段大量改动仍未提交；本次将只做增量适配，不修改或回退其核心计算实现。
- 已完整读取阶段3 API、CareerState/AgentLog、StateRepository、CareerOrchestrator、应用工厂与现有配置。
- 初步决定新增独立薄适配层和平台调用记录，而不是把现有内部 `CareerState` 接口直接当作冻结工具契约。
- 已读取匹配/路径/阶段2严格 Schema、Agent 调用日志实现、阶段3 E2E 固定数据、V003 和迁移脚本。
- 确认新增 V004 平台工具调用表是最小且边界清晰的持久化方案。
- 已读取百宝箱需求、智能体配置、Prompt、旧工具目录、旧 TBox Mock 适配器、主路由和环境样例。
- 已识别旧冻结文档与本次最小工具命名/范围不一致；将保留旧历史文档，新增阶段3正式接入说明并同步 API 契约。
- 尝试通过官方语雀域名核对平台工具字段；公开搜索无结果、项目内具体链接无法打开，已停止重试并记录不可验证边界。
- 已对照 Agent 执行/日志实现、严格业务输出 Schema、公共 API 契约和数据字典，确定平台层 envelope、错误码与 AgentRunLog 关联方式。
- 已新增冻结平台 Schema、Bearer 鉴权、两个阶段3工具、状态/结果查询、超时与幂等逻辑、平台调用持久化表及 V004。
- 已将平台路由挂入主应用，并加入平台专用验证错误 envelope 和环境配置。
- 编译检查通过；阶段3 E2E 回归 `10/10` 通过。
- 新增平台接口测试，首轮 `4/4` 通过；覆盖匹配/路径、状态/结果、重放/冲突、鉴权、Schema、超时、日志隐私、持久化和 OpenAPI。
- 已同步 API 契约、架构、V004 数据字典并新增百宝箱阶段3配置说明。
- 已生成一套完整匿名 `analyze_job_match` Mock 请求/响应，并新增 Schema 校验测试。
- 平台接口测试增强后 `5/5` 通过，完整 Mock 文件也通过冻结 Pydantic Schema 校验。
- V001-V004 与静态数据检查通过；未配置生产 PostgreSQL，因此只运行 `--check`，未执行 `--apply`。
- `backend/tests` 全量回归：80/80 通过。
- `backend/app` 回归：34 通过、2 个上一阶段已存在的旧全链 TBox Mock 失败；失败项与基线完全一致（full chain partial、旧 Mock code=-4），本次正式阶段3工具测试均不受影响。
- 一组组合检查误从仓库根运行 backend 相对命令，compile/migration 子命令未实际执行；已记录并准备从正确目录重跑。`git diff --check` 未报告 whitespace error。
- 已从正确 `backend/` 目录重跑 compileall 和 V001-V004 `--check`，均通过；`git diff --check` 通过。
- 最终代码复核修正“前置失败却写入不存在 AgentRunLog 关联”的边界，并收紧 schema_version/tool_call_id；平台测试仍为 5/5 通过。
- 隐私复核将平台调用表的完整结果改为 CareerState 字段指针；结果查询仍从鉴权后的 CareerState 返回，平台+阶段3联合测试 15/15 通过。
- 最终 `backend/tests` 全量回归 80/80 通过；compileall、V001-V004 静态检查和 `git diff --check` 均通过。

## 最终接入结论

- CareerPulse 侧 `stage3-tool-v1` 已具备两个正式工具、状态/结果查询、固定 Schema、Bearer、超时、稳定错误码、持久幂等、隐私安全调用日志和 AgentRunLog 关联。
- OpenAPI 由主应用 `/openapi.json` 提供，只需在百宝箱选择 4 个阶段3 operation；完整配置字段、Mock 和未验证平台项已写入 `docs/a02/15_TBOX_STAGE3_MINIMAL_INTEGRATION.md`。
- 未接入任何阶段4工具，未修改 MatchService、PathService、MatchAgent 或 PathAgent 的计算逻辑，未提交 Git。
