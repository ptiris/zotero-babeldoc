# 仓库设计参考

查阅日期：2026-10-08。选择社区中广泛使用的 Zotero 项目及直接相关的翻译插件，参考其组织方法；星数随时间变化，未将其作为本项目质量证明。

| 参考 | 本仓库采用的组织思路 |
| --- | --- |
| [windingwind/zotero-plugin-template](https://github.com/windingwind/zotero-plugin-template) 与 [发布配置](https://github.com/windingwind/zotero-plugin-template/blob/main/.github/workflows/release.yml) | 版本标签触发 Release、编号安装包和独立固定更新清单、开发与发布指引 |
| [windingwind/zotero-better-notes](https://github.com/windingwind/zotero-better-notes) | README 提供下载安装、快速开始、功能与开发入口，区分面向用户和开发者的文档 |
| [guaguastandup/zotero-pdf2zh](https://github.com/guaguastandup/zotero-pdf2zh) | 将 Zotero 插件安装、Python 引擎配置、使用和故障排查分开，解释升级边界 |
| [funstory-ai/BabelDOC](https://github.com/funstory-ai/BabelDOC) | 上游引擎接口、版本约束、模型和字体下载、许可与依赖说明 |
| [Zotero 官方插件开发文档](https://www.zotero.org/support/dev/zotero_7_for_developers) | manifest 必需字段、bootstrap 生命周期、更新 JSON 格式与兼容范围 |
| [GitHub Actions](https://docs.github.com/en/actions) 与 [Release API](https://docs.github.com/en/rest/releases/releases) | 工作流权限、Release 资产与发布顺序 |

本项目继续使用已验证的原生 JavaScript + Python 桥接，没有为了目录外观迁移到 TypeScript/Scaffold。模板项目的自动发布模式适用于这里，但原翻译集成不需要驻留 HTTP 桥接服务。没有复制这些仓库的 README 正文、图标或截图。
