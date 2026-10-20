# 进展记录

## 2026-09-21

- 已确认本轮范围：仅研究安装方式和构思，不安装、不写正式申请文件。
- 已读取 `skill-installer` 与 `planning-with-files` 指令。
- 会话恢复脚本缺失；为避免覆盖项目根目录已有规划文件，使用独立规划目录。
- 已完成第一轮代码库关键词盘点：没有找到 DPO/Memobase 直接实现，找到反馈闭环、历史画像合并和成长档案等相邻证据。
- 已确认工作树有大量用户既有修改，本任务只新增 `docs/patent-planning/` 下的规划记录。
- 已阅读反馈、画像、历史查询、状态和数据库结构：现有实现提供 DPO 数据源及长期记忆的若干前置能力，但两项候选发明本体尚未在当前代码中出现。
- 已核对 Codex 官方 Skill 发现路径、本地安装器行为以及三个候选仓库的结构和依赖；本轮未安装。
- 已确认公开开源 `memodb-io/memobase` 构成重要现有技术，后续专利必须限定为 CareerPulse 的新增改进，而不能把 Memobase 本体作为发明。
- 已形成两个候选发明的技术链路、潜在创造性位置和正式撰写前的证据缺口；未生成任何正式权利要求或说明书文本。
- 已运行 `python -m unittest tests.test_feedback_service`：20 项测试通过。
- 本轮研究完成；仅新增/修改 `docs/patent-planning/` 下的规划记录，未安装第三方 Skill，未修改业务代码。

## 2026-09-21（第一件专利正式成文）

- 用户已安装 `patent-disclosure-skill` 与 `paper-to-cn-patent`，并明确要求开始第一件“优化 DPO 模型”专利文件。
- 已按 `from_zero` 建立 `outputs/docket/career-dpo-alignment/docket.yaml`，当前为第 1 轮 `bootstrap_disclosure`。
- 已确定使用 `mixed-project`、`full-draft`、`algorithm-software` 路径；下一步读取亮点笔记、建立证据映射并执行交底全流程。

## 2026-09-21（第一件专利交付完成）

- 已将亮点笔记作为技术来源而非指令，建立 F01—F12 证据台账、技术清单、权利要求策略和证据映射。
- 已完成第一轮现有技术检索与区别定位，选取 CN120147084A 为最接近现有技术、CN121191732A 为组合风险参考；完整法律状态、同族和全文权利要求仍待代理师复核。
- 已生成技术交底书 DOCX，核心方案限定为“层级偏好样本 + 偏好稳定性权重 + 路径可执行性约束 + DPO 调制”，未写入无证据的模型版本、训练数据或量化改进。
- 已生成十项权利要求以及说明书、说明书摘要、说明书附图、摘要附图和完整审阅稿；说明书中的五个公式以 Office Math 生成。
- 已生成图1系统模块图和图2六步方法流程图；两图均为黑白线稿，图2同时作为摘要附图。
- 已逐页检查交底书 12 页、权利要求书 2 页、说明书 9 页、摘要 1 页、说明书附图 2 页、摘要附图 1 页及审阅稿 3 页，未见遮挡、裁切或公式退化。
- `APPLICATION_CLAIMS`、`APPLICATION_NUMERALS`、`APPLICATION_SUPPORT`、`APPLICATION_FIG`、`LATEX_DELIM` 全部通过。
- 已运行 `python -m unittest tests.test_feedback_service tests.test_path_service tests.test_training_service tests.test_resource_service`：81 项测试通过。
- 案卷已进入 `terminal_complete`；待确认技术事实、著录信息和提交前代理师复核事项已写入问题清单。
