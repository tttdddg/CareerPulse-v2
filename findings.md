# Findings

## 现状
- 尚未检查项目现有结构与依赖（待任务执行时补充）。

## 假设
- 需要从当前项目根目录生成规划文件。
- 富文本编辑器尚未指定具体库。

## 待确认
- 是否已有现有页面或设计稿。
- 富文本编辑器偏好（如 `@wangeditor/editor`、`quill`、`tiptap`）。

## 逐页检查发现（2026-03-09）
- 路由当前实际使用页面为：
  - `/` -> `views/home/HomeLanding.vue`
  - `/login`、`/register` -> `views/login/Login.vue`
  - `/app/*` -> `views/input|analysis|path|plan|profile`
- 关键缺口：
  - 登录页未根据 `/register` 路由自动切换到注册模式。
  - 首页 CTA 固定跳转登录，未按登录态直达业务页。
  - 应用启动未主动 hydrate 用户 store，刷新后显示名/档案信息不稳定。
  - 图谱页在未完成分析时仅提示错误，不引导回输入页。
  - 个人中心加载历史时会覆盖本地刚生成的报告，存在数据回退风险。
