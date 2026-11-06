---
name: quiet-quota
description: 查看 Codex 的真实剩余额度及重置时间，启动、设置或退出“余量”桌面悬浮组件。仅适用于余量组件，不代表 ChatGPT 模型消息额度。
---
使用插件的 quiet_quota 工具：
- 查看额度：quota_read。数据来源是本机 Codex CLI 当前登录账户，按服务返回的 5h / 7d 窗口展示；缺失窗口显示暂不可用。
- 打开组件：widget_start。
- 设置界面：widget_settings。
- 刷新：widget_refresh。
- 退出：widget_stop。
组件会跟随 Codex / ChatGPT 桌面窗口，但两处显示的都是 Codex 额度。不要把它说成 ChatGPT 各模型消息配额。失败或未更新时保留错误与更新时间，不能推断为 0% 或 100%。
插件本地 MCP 服务启动时会唤起辅助程序。辅助程序静默等待目标窗口，不占任务栏；退出组件后可通过插件重新打开。
