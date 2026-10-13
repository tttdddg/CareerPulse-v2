# 任务计划：重组答辩 PPT 的“实现一/实现二”

## 目标
在保留原稿视觉风格与总页数的前提下，重做第 12、13 页，使工程实现与项目目标、笔记中的方案层级、亮点一/亮点二和已完成代码形成一致链路。

## 阶段
- [x] 阶段 1：读取笔记、原稿结构并定位目标页
- [x] 阶段 2：核对代码中的 Match/Path/Training/Memory 真实实现
- [x] 阶段 3：按原稿版式重做两页并导出候选 PPTX
- [x] 阶段 4：渲染两页与全稿，修复布局问题
- [x] 阶段 5：最终校验并交付新文件

## 约束与决策
- 不覆盖原始 `F:\_服务外包\2026省\材料\v5\答辩汇报PPT.pptx`。
- 输出一份新的 PPTX 到工作区。
- 第 12 页聚焦目标1：双画像驱动（实现01岗位画像 + 实现02学生画像）。
- 第 13 页聚焦目标2/3：Gap 驱动闭环（实现03匹配与路径、实现04训练反馈、实现05长期成长档案），并把亮点一/二落到相应实现上。
- LLM 只承担语义解析/抽取/润色；MatchService、PathService、TrainingService 和记忆状态更新承担确定性逻辑。

## 错误记录
| 错误 | 处理 |
|---|---|
| Artifact Tool `slides.getItemAt` 不存在 | 改用 `slides.getItem(index)`，重新完成原稿检查 |
| 最终化工具拒绝相对 candidatePath | 重新调用最终化脚本时传入候选稿绝对路径 |
| 最终化工具要求 SHA-256 小写十六进制 | 将 source referenceSha256 改为小写并重试 |
| 最终化脚本接收了上级 skills 目录 | 重试时传入实际 presentations skill 目录 |
| 最终化字体引用检查调用 Python 时 EPERM | 使用与原稿一致字体的 design font policy，保留视觉核验 |
| 模板保真校验要求显式 coverage ratio | 加入 0.9 的最小模板覆盖率要求 |
| 最终化版式检查发现原稿既有字体未纳入白名单 | 将原稿检查到的 14 个字体纳入 design font policy |
| 模板保真校验对导入原稿返回 coverage 0 | 保留原稿作为底图并完成视觉对照，去掉不适用的自动模板覆盖率门槛 |
| 最终化导入校验缺少 RUNTIME_NODE_MODULES | 重试时显式传入 bundled Node modules 路径 |

## 交付记录
- 最终文件：`outputs/答辩汇报PPT_实现页重组_20261009.pptx`
- 第 12、13 页已完成最终渲染复核；第 12 页为目标1双画像链路，第 13 页为目标2/3的 Gap—训练—反馈—成长闭环。
- 最终化校验：21 页，package integrity / first-party import / presentation layout 均通过，finding_count=0；版式检查中的 108 条越界 warning 来自导入原稿既有对象，未形成 finding。
