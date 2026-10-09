# 安装与升级

## 1. 获取发布文件

打开 [最新版本](https://github.com/ptiris/zotero-babeldoc/releases/latest)，下载 `.xpi` 和 `-source.zip`。`Source code (zip)` 是 GitHub 自动生成的源码快照；带项目版本的 `-source.zip` 是发布脚本生成的源码及引擎安装包。两者均不内置 Python、模型或虚拟环境。

`SHA256SUMS.txt` 可用于核对下载文件。macOS/Linux 使用 `shasum -a 256 文件名`；Windows PowerShell 使用 `Get-FileHash 文件名 -Algorithm SHA256`，将结果与校验文件比较。

## 2. 安装 Zotero 插件

Zotero → 工具 → 插件（部分版本叫“附加组件”）→ 齿轮 → 从文件安装插件，选择 XPI。安装后工具菜单应出现“BabelDOC 翻译 PDF…”，设置中出现 BabelDOC。只把 XPI 安装到 Zotero；不需要解压 XPI。

## 3. 安装本地引擎

解压 `-source.zip`，保持 `addon/`、`scripts/`、`requirements.txt` 的目录关系。推荐先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)。安装器优先通过 uv 创建 Python 3.12 环境；不用 uv 时，需使用 Python 3.10–3.13 运行脚本。

| 系统 | 操作 | Python 路径形式 |
| --- | --- | --- |
| macOS | 双击 `install-macos.command` 或运行 `python3 scripts/install-engine.py` | `/完整目录/engine/bin/python` |
| Windows | 双击 `install-windows.cmd` | `C:\完整目录\engine\Scripts\python.exe` |
| Linux | `python3 scripts/install-engine.py` | `/完整目录/engine/bin/python` |

脚本创建本项目的 `engine/` 虚拟环境与 `.engine-install-cache/` 下载缓存，不修改系统 Python。Python、依赖、模型和字体下载需要网络与磁盘空间。若 `.command` 不能直接打开，可在终端进入解压目录执行 Python 命令。

需要把引擎放在固定位置时：

```bash
python3 scripts/install-engine.py --directory /完整路径/babeldoc-engine
```

Windows 同样支持 `--directory`。安装结束复制打印的 Python 可执行文件完整路径到插件。不要填写 `babeldoc` 命令或目录路径。已有 BabelDOC 0.6.4 环境可直接复用。

## 4. 第一次翻译

选中有 PDF 的文献或 PDF 附件，右键启动翻译。填入 Python 路径并检查环境，再填写 API 地址、模型和密钥。先用 1 页验证供应商兼容性。完成后译文与双语 PDF 保存到文献下，默认打开双语结果。

第一次翻译会下载模型和字体，因此初始化可能较慢。[配置说明](configuration.md) 解释各字段。[故障排查](troubleshooting.md) 提供具体错误处理。

## 升级与卸载

- **旧本地 0.1.1 → GitHub 0.1.2：** 手动安装一次新 XPI。插件 ID 保留，设置可继续使用；无需重装 BabelDOC 0.6.4。
- **后续公共版本：** Zotero 可以检查更新；也可随时手动安装 Release XPI。XPI 更新不自动升级 Python 引擎。
- **引擎：** 发布说明要求升级时，重新运行新版本的安装器。不要在插件仍要求 0.6.4 时直接升级到其他 BabelDOC 版本。
- **移动引擎目录：** Python 虚拟环境通常不可直接搬移；请在新目录重新安装并更新插件路径。
- **卸载：** 在 Zotero 插件管理器卸载插件。已导入附件不会自动删除；引擎、模型/译文缓存、设置及记住的密钥也不会自动清除。清理位置见 [数据与隐私](privacy.md)，操作前退出 Zotero并确认数据无需保留。
