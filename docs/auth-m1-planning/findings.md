# M1 实现发现

- 根目录规划文件属于 PPT 任务，本次使用独立目录避免覆盖。
- 当前工作树存在用户未提交内容，认证实现仅修改明确在 M1 范围内的文件。
- 现有数据库基础设施提供 PostgreSQL 16 连接池与显式事务，适合认证 Repository 复用。
- `create_app` 已有可注入服务的测试风格；认证服务将采用相同模式，避免单元测试连接数据库。
- 前端当前初始化同步读取 localStorage，路由守卫也直接解析 localStorage；M1 需改为启动时 `/me` 恢复和异步守卫。
- Axios 1.x 可用 `withCredentials + xsrfCookieName/xsrfHeaderName` 实现同源双提交 CSRF。
- 后端 M1 已实现为独立 `app.auth` 模块；默认构造不连接数据库，只有认证请求触发 Repository，因而不会影响现有 Core 启动。
- `V008` 只新增 `identity` schema、用户、Session、画像绑定和失败登录表，未修改现有业务表。
- 前端正式认证已改为 Cookie Session；`career-pulse:auth` localStorage、固定管理员和模拟短信逻辑已无引用。
- Demo 仍通过内存 profile 启动，不调用认证 API；生产环境显式写入 `VITE_DEMO_MODE=false`。

