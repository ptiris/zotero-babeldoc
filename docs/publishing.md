# 发布与自动更新

## 用 gh CLI 创建和管理仓库

先在终端安装 [GitHub CLI](https://cli.github.com/)，自行完成认证，再检查账号：

```bash
gh auth status
gh api user --jq .login
```

认证信息不写入本仓库。使用 Token 时通过标准输入传给 `gh auth login --with-token`，不要把 Token 放在命令行参数、README 或 Issue 中。不要让自动化代替你完成网页认证。

在本地仓库已有第一次提交后，创建公开远程仓库并推送：

```bash
gh repo create ptiris/zotero-babeldoc --public --source=. --remote=origin --push --description "Translate PDFs with BabelDOC inside Zotero"
gh repo edit ptiris/zotero-babeldoc --add-topic zotero --add-topic babeldoc --add-topic pdf-translation --add-topic zotero-plugin
```

如果仓库已存在，先 `gh repo view ptiris/zotero-babeldoc` 检查，添加正确的 origin 后普通推送；不要盲目覆盖现有文件或历史。Git HTTPS 认证可使用 `gh auth setup-git` 配置凭据助手；也可在单次 Git 命令中配置 gh 助手，无需改全局 Git 设置。

常用管理命令：

```bash
gh run list --repo ptiris/zotero-babeldoc
gh run view RUN_ID --repo ptiris/zotero-babeldoc --log-failed
gh release list --repo ptiris/zotero-babeldoc
gh release download v0.1.2 --repo ptiris/zotero-babeldoc --dir downloads
gh issue list --repo ptiris/zotero-babeldoc
gh workflow run engine-smoke.yml --repo ptiris/zotero-babeldoc
```

## 第一次发布

本仓库默认位置 `ptiris/zotero-babeldoc`。GitHub Actions 使用仓库自带 `GITHUB_TOKEN`，仅发布 job 申请 `contents: write`，无需配置个人 API Key。确认仓库 Actions 已启用。README 的下载链接在第一次成功发布前没有安装文件。

检查以下步骤后推送版本标签：

```bash
node --test tests/test_controller.cjs
python3 -m unittest discover -s tests -p 'test_build.py' -v
# 安装引擎后
engine/bin/python -m unittest discover -s tests -v
git add .
python3 scripts/build.py --repository ptiris/zotero-babeldoc --tag v0.1.2
git commit -m "Prepare 0.1.2 release"
git push origin main
git tag v0.1.2
git push origin v0.1.2
```

本指南中的首次提交步骤视仓库已有提交情况执行，不应为每次发布重复初始化 Git。

## 后续版本

```bash
python3 scripts/set-version.py 0.1.3
```

该脚本只同步 `addon/manifest.json` 和 `package.json`，不自动提交或推送。补充 `CHANGELOG.md` 对应段落、验证结果与必要的 README 版本/兼容信息，运行测试、提交、推送，再创建并推送 `v0.1.3`。固定更新 Release 需要允许更新资产；仓库级 immutable releases 与此固定 Release 方案不兼容。若计划启用该功能，先将更新清单迁移到 GitHub Pages 等可更新的固定端点，同时发布指向新地址的 XPI。

当前仅支持稳定 `x.y.z` 版本，预发布版本会被拒绝。

## Release 产物

| 文件 | 用途 |
| --- | --- |
| `zotero-babeldoc-x.y.z.xpi` | Zotero 插件，内含 Python 桥接脚本，不含引擎依赖 |
| `zotero-babeldoc-x.y.z-source.zip` | Git 跟踪的源码、文档及引擎安装入口 |
| `SHA256SUMS.txt` | XPI、源码包及本次更新清单校验值 |
| `updates.json` | 含版本、兼容范围、XPI URL 与 SHA-256 的更新清单 |

`dist/` 不进入 Git。打包采用排序、固定 ZIP 时间和权限，不包含虚拟环境、模型、缓存、PDF 或 API Key。源码包只收 Git 跟踪文件，因此新文件应先 `git add`。在相同源码与 Python/压缩环境中构建结果可重复。

## 更新地址

版本 XPI 位于：

```text
https://github.com/ptiris/zotero-babeldoc/releases/download/v0.1.2/zotero-babeldoc-0.1.2.xpi
```

插件清单指向固定地址：

```text
https://github.com/ptiris/zotero-babeldoc/releases/download/release/updates.json
```

`release` 是专门存放更新元数据的标签/Release，标记为 prerelease 且不作为 latest；它服务的是稳定版更新清单。用户安装编号版本的 XPI。更新条目采用 [Zotero 官方格式](https://www.zotero.org/support/dev/zotero_7_for_developers#updaterdf_updatesjson)，包含 `applications.zotero` 兼容范围和 `sha256:` 哈希。

发布脚本先上传版本附件并公开版本 Release，再创建或刷新固定清单。不同版本发布串行执行；它拒绝降低稳定更新版本，也拒绝用不同文件覆盖已经公开的同一版本。失败后可在 Actions 重新运行；若构建源码/产物改变，提升版本发布。

早期本地 0.1.1 的 `.invalid` 更新地址无法发现新仓库；用户需要手动升级一次。保留 `babeldoc@local.zotero` ID 是为了升级已安装实例，公开仓库中不要随意修改 ID。

## 故障与回退

- 标签与 manifest/package 版本不符：测试/构建失败，修正版本后使用新的正确标签。
- 无 CHANGELOG 段落：Release 失败，添加该版本段落后发布新版本。
- 依赖安装或桥接测试失败：不发布；查看 Actions 日志，确认上游兼容性。
- 版本已发布、更新清单上传失败：修复网络/权限后重跑；已有相同产物会校验后继续。
- 错误版本已公开：发布更高版本修复。不能通过降低清单版本强制 Zotero 降级；必要时用户手动安装旧版 XPI。不要删除用户正在使用的 Release 附件。

## Fork 或迁移

Release 工作流用 `GITHUB_REPOSITORY` 自动注入当前仓库的下载/更新 URL。正式迁移时还要同步源 manifest 的 homepage/update_url、README 和文档链接。独立 Fork 应使用自己的 addon ID、偏好前缀和 chrome 命名空间；保留原 ID 会替换已安装原插件。发布工作流默认只允许 `ptiris/zotero-babeldoc`，Fork 需审阅并修改该限制后才能启用自己的发布。
