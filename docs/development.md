# 开发与测试

## 准备

```bash
git clone https://github.com/ptiris/zotero-babeldoc.git
cd zotero-babeldoc
python3 scripts/install-engine.py
```

推荐 Python 3.12、Node.js 24（22+ 可运行控制器测试）。不需要 npm install，仓库没有 npm 依赖。BabelDOC 依赖固定在 `requirements.txt`；`TESTED-DEPENDENCIES.txt` 是原 macOS 环境的版本快照，**不是跨平台锁文件**。

## 验证层次

```bash
npm run check
node --test tests/test_controller.cjs
python3 -m unittest discover -s tests -p 'test_build.py' -v
engine/bin/python -m unittest discover -s tests -v
```

Windows 最后一条使用 `engine\Scripts\python.exe`。快速测试检验队列、选择与导入逻辑以及发布文件；桥接测试额外确认真实 BabelDOC 0.6.4 配置签名，不调用收费模型。

可选完整引擎测试：

```bash
engine/bin/python tests/smoke_engine.py --response-mode recover --debug
engine/bin/python tests/smoke_engine.py --response-mode empty
engine/bin/python tests/smoke_engine.py --response-mode truncated
```

这些命令创建自制英文 PDF、仅绑定回环地址的随机端口模拟模型，运行真实 BabelDOC。恢复场景检查重试后生成含中文的两份 PDF、正常退出、调试文件保留和原文未改变；空响应与截断场景检查明确失败、无成功事件。首次运行会联网下载模型和字体；不需要真实 API Key。报告默认在 `test-results/engine-smoke/report-场景.json`；失败时保留 stderr 用于本机诊断，不要直接公开未经审阅的日志。

## Zotero 桌面验证

遵循先写完与测试代码，再进入 Zotero 验证的顺序。使用独立测试 profile **及独立 data directory**，避免污染真实资料库。参考 [Zotero 官方独立 profile 指引](https://www.zotero.org/support/kb/multiple_profiles)。先 `git add` 新文件，再构建 XPI：

```bash
python3 scripts/build.py --repository ptiris/zotero-babeldoc
```

在测试 Zotero 手动安装 `dist/` 下的 XPI，创建一份自制 PDF，检查：菜单和设置入口、Python 检查、翻译进度、取消、译文/双语子附件、内置阅读器、原文哈希不变、禁用/重启清理和失败恢复。可通过 `python3 tests/mock_model.py --port 18987` 提供本地模型接口，填 `http://127.0.0.1:18987/v1` 和非空占位密钥；测试完成停止服务。此服务只供测试。

检查 0.1.3 的思考模式、输出上限和缓存选项能否保存，开启调试后成功任务是否保留目录。另启动 `python3 tests/mock_model.py --port 18988 --response-mode empty`，切换 API 地址到该端口，确认持续空响应显示失败且没有新增附件。

## Actions

- `CI`：每次 main 推送/PR，验证 JS、打包测试、语法、文档链接和打包结构；Ubuntu 上安装 BabelDOC 运行桥接测试。
- `Engine smoke`：手动触发的 macOS/Linux/Windows 真引擎测试，可能需要下载资源。它不启动 Zotero，不证明桌面兼容性。
- `Release`：版本标签触发；先执行测试，再发布附件和固定更新清单。详见 [发布](publishing.md)。

修改 Python 引擎版本、Subprocess、附件写入或取消机制时，应增加对应回归测试并再次执行桌面验证。纯文档更改检查链接即可。
