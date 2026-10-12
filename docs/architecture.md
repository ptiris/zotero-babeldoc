# 架构与协议

## 模块

| 路径 | 职责 |
| --- | --- |
| `addon/bootstrap.js` | Zotero 生命周期、chrome 资源注册、启动与清理 |
| `addon/content/core.js` | 菜单、阅读器按钮、设置、PDF 选择、队列、子进程、附件导入 |
| `addon/content/console.*` | 翻译表单、进度与操作 |
| `addon/content/preferences.*` | Zotero 设置入口 |
| `addon/bridge/runner.py` | 固定 BabelDOC API 接入、输入/输出校验、翻译事件与 CPU 模式 |
| `scripts/` | 引擎安装、确定性打包、版本修改和发布 |
| `tests/` | 控制器、桥接、发布包及可选引擎冒烟测试 |

Zotero 通过 Mozilla Subprocess 启动选定的 Python，不经 shell 拼接命令。stdout 是 JSONL 协议，stderr 用于第三方输出并并发读取，避免管道阻塞。每个 PDF 单独创建任务目录，队列顺序执行；取消会终止子进程。

## 请求

stdin 接收一行 JSON，例如：

```json
{
  "action": "translate",
  "input_file": "/absolute/path/paper.pdf",
  "output_dir": "/absolute/path/job-unique",
  "base_url": "http://127.0.0.1:8000/v1",
  "api_key": "example-placeholder",
  "model": "your-model",
  "lang_in": "en",
  "lang_out": "zh",
  "pages": "1,3-5",
  "qps": 2,
  "output_mode": "both",
  "dual_layout": "side-by-side",
  "ocr": false,
  "thinking": "disabled",
  "max_output_tokens": 8192,
  "ignore_cache": false,
  "debug": false
}
```

环境检查使用 `{"action":"probe"}`。以实际 runner 和表单代码为准，不把这个含占位密钥的示例写成用户任务配置文件。

## 响应

stdout 每行一个 JSON 对象，类型为 `probe`、`stage`、`progress`、`finish` 或 `error`。成功事件包括实际输出路径与 `mono` / `dual` 类型。接收到 `finish` 后 runner 停止读取引擎事件并正常退出；控制器同时要求成功事件与退出码 0。

输出仅接受任务目录内的真实 PDF。控制器导入为源文献子附件，独立附件则继承资料库与分类。成功导入后清理任务目录，开启调试则保留；失败时保留任务目录。默认打开双语，否则打开译文。

桥接层包装当前进程的模型请求，设置输出预算，拒绝空响应和截断响应，最多重试两次。无效响应不会写入缓存；空缓存被视为未命中。段落后处理也拒绝空译文，避免覆盖原文。即使 BabelDOC 内部吞掉异常，任务结束前仍检查失败记录，禁止发出成功事件。该机制不等同于完整的 PDF 内容覆盖检测。

## 兼容策略

Zotero 新版本使用 MenuManager/Reader API；旧菜单路径提供回退。BabelDOC 使用固定 0.6.4 API 和 ONNX CPU provider，避免 macOS CoreML 在子进程结束时崩溃。初始化 BabelDOC 常量时临时替换 `Path.home`，将该引擎缓存定位到桥接目录，导入后恢复。升级引擎前必须检查 API、模型资源、原生依赖及真实输出，不能仅调整版本字符串。
