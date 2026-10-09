# 验证记录与边界

## 已完成的桌面集成验证

2026-10-08，使用独立 Zotero 测试 profile 和资料库，验证已修复的 **0.1.1** XPI：

| 组件 | 版本/环境 |
| --- | --- |
| 操作系统 | macOS，Apple Silicon |
| Zotero | 10.0.6 |
| Python | 3.12.14 |
| BabelDOC | 0.6.4 |
| 模型 | 回环地址的确定性模拟 OpenAI 兼容服务 |

实际通过翻译窗口提交 PDF，真实 BabelDOC 完成任务且退出码为 0；译文和双语 PDF 成为原文献子附件；原 PDF 内容未改变；输出含中文；内置阅读器实际显示左右双语结果，工具栏“译”按钮存在。控制器 11 项、桥接 10 项测试通过。原始证据：[文字记录](evidence/VALIDATION.txt)、[机器可读记录](evidence/验证记录.json)。

## 仓库版 0.1.2

运行代码（bootstrap、控制器、表单与 runner）延续 0.1.1，新增仓库工具、发布/更新元数据、文档与打包验证。兼容上限由 10.* 收窄到 10.0.*。本次仓库整理不重复操作用户的 Zotero 资料库。本次本机新增验证：11 项 JS 控制器测试和 19 项 Python 测试通过；真实 BabelDOC 冒烟测试调用模拟模型 3 次，生成两份含中文 PDF，退出码 0，原文哈希不变（[报告](evidence/engine-smoke-0.1.2.json)）。YAML、Python/JS 语法、文档链接和发布包完整性检查通过。

自动测试结果与发布状态以 [Actions](https://github.com/ptiris/zotero-babeldoc/actions) 为准。

## 未覆盖范围

- Zotero 7–9、Windows/Linux 的实际安装及桌面工作流。
- 真实商业模型账户、收费、模型权限和翻译质量。
- 所有扫描件、特殊字体、超大文件及复杂版面。
- GUI 生命周期、错误恢复与取消的所有平台差异。

`Engine smoke` Actions 会验证真实引擎与模拟模型，但不启动 Zotero。它通过不等于上述桌面环境已经验证。接受新的平台测试记录时须标明组件版本、使用的模型服务类型、测试步骤和结果。
