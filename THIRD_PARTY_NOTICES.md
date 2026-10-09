# 第三方项目

| 项目 | 用途 | 许可/说明 |
| --- | --- | --- |
| [BabelDOC](https://github.com/funstory-ai/BabelDOC) 0.6.4 | 独立安装的 PDF 翻译引擎 | AGPL-3.0；不把依赖/模型打进 XPI |
| [Zotero](https://github.com/zotero/zotero) | 宿主及平台 API | 宿主独立安装，其许可由 Zotero 项目提供 |
| BabelDOC 的 Python 依赖、版面模型和字体 | 由引擎安装/下载 | 以各自发行包及资源的许可为准；版本快照见 TESTED-DEPENDENCIES.txt |
| GitHub 官方 Actions | CI 环境准备与产物上传 | 以各 Action 仓库许可为准，仅在 Actions 环境执行 |

本仓库插件源码使用 AGPL-3.0-or-later，完整文本见 LICENSE。引擎安装器从包仓库下载依赖；发布包不重新分发虚拟环境、模型或字体。参考仓库列表见 docs/references.md；参考其配置与文档组织不表示复制其代码或使用其品牌。
