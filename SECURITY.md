# 安全报告

## 支持范围

目前仅最新稳定版接收安全修复；旧本地版本应升级。此项目尚处于早期阶段，维护者不承诺固定响应时限。

## 报告方式

若仓库启用了 GitHub 私密漏洞报告，请进入 **Security → Report a vulnerability**，提供影响版本、复现步骤、潜在影响及无真实密钥的演示。

若该入口不可用，可先开一个仅含“需要私密安全报告渠道”的 Issue，让维护者提供私密联系方式。不要公开漏洞细节、可利用载荷、真实 API Key、私人 PDF 或数据库。维护者应在仓库 Settings → Security 中启用 Private vulnerability reporting。

## 报告边界

插件拥有 Zotero 插件正常的本地文件及平台权限，执行用户指定的 Python 引擎。API Key 的传递、输出路径校验、更新产物完整性、附件写入和子进程管理是重点。供应商自身数据策略及上游 BabelDOC 漏洞可同时向相应上游报告。[数据与隐私](docs/privacy.md) 说明当前实现。
