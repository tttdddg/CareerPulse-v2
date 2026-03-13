# CareerPulse（吾 AI 职导）

CareerPulse 是一个面向职业规划与人岗匹配的智能分析系统前端项目，支持从用户资料/简历输入到匹配分析、路径图谱、成长计划与历史记录的完整业务流程。

## 系统简介

系统围绕「职业能力评估与成长建议」构建，核心功能包括：

- 用户登录/注册与鉴权
- 数据输入中心（简历上传、资料录入）
- 人岗匹配分析看板（匹配分、雷达图、优势与短板）
- 职业路径图谱可视化
- 个性化成长计划生成与编辑
- 个人中心与历史报告查看

## 技术栈

### 前端技术栈

- 框架：Vue 3
- 构建工具：Vite 6
- 语言：TypeScript
- 路由：Vue Router 4（Hash 路由）
- 状态管理：Pinia
- UI 组件库：Element Plus
- 网络请求：Axios
- 图表：ECharts
- 图谱可视化：@antv/x6
- 富文本编辑：@wangeditor/editor-for-vue
- 样式：SCSS + CSS
- 工程能力：unplugin-auto-import、unplugin-vue-components

### 后端技术栈和对接方式

待补充
前端通过 REST API 对接后端。

- API 基础地址来自环境变量：
  - `VITE_API_BASE_URL`
  - `VITE_API_PROXY_TARGET`
- 开发环境通过 Vite 代理将 `/api/*` 转发到后端服务
- 默认后端地址示例：`http://10.151.198.189:8000`（请按你的实际后端环境修改）

## 操作步骤

### 1. 环境准备

- Node.js 18+（建议 18/20 LTS）
- npm 9+

### 2. 安装依赖

```bash
npm install
```

### 3. 配置环境变量

项目根目录已有 `.env.development`，可按需修改：

```env
VITE_API_BASE_URL=http://你的后端地址:端口
VITE_API_PROXY_TARGET=http://你的后端地址:端口
```

说明：

- `npm run dev` 时，前端请求 `/api` 会被代理到 `VITE_API_PROXY_TARGET`
- 生产构建后，接口地址使用 `VITE_API_BASE_URL`

### 4. 启动开发环境

```bash
npm run dev
```

启动后访问终端输出的本地地址（通常是 `http://localhost:5173`）。

### 5. 类型检查

```bash
npm run typecheck
```

### 6. 生产构建与预览

```bash
npm run build
npm run preview
```

构建产物位于 `dist/` 目录。

## 目录结构（核心）

```text
src/
  api/          # 接口封装与业务 API 模块
  components/   # 业务组件（图表、图谱、上传、富文本等）
  layouts/      # 页面布局
  router/       # 路由与鉴权守卫
  services/     # Mock 服务
  stores/       # Pinia 状态管理
  styles/       # 全局样式与主题
  views/        # 页面视图（输入、分析、路径、计划、个人中心）
```
