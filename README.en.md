# BabelDOC for Zotero

This plugin connects BabelDOC to Zotero. Select a PDF, translate it from Zotero, and save the translated and bilingual versions as attachments. You can open the results in Zotero's built-in reader. The original PDF stays in place, and generated documents preserve its layout.

[简体中文](README.md) · [Download](https://github.com/ptiris/zotero-babeldoc/releases/latest) · [Installation](docs/installation.md) · [Issues](https://github.com/ptiris/zotero-babeldoc/issues)

Start from the item menu, Tools menu, or the reader's "译" button. The translation window lets you set the model, languages, page range, OCR, rate limit, and output layout. You can follow progress or cancel a job. When you select several PDFs, the plugin translates them one at a time.

The plugin runs a separately installed BabelDOC 0.6.4 Python engine. It does not need a persistent bridge server. You provide an OpenAI-compatible Chat Completions endpoint and API credentials; the plugin has no translation account or quota. PDF text goes to your chosen endpoint. See [data handling](docs/privacy.md).

## Install

1. Download the `.xpi` and `-source.zip` from [Releases](https://github.com/ptiris/zotero-babeldoc/releases/latest).
2. In Zotero's plugin manager, open the gear menu and choose "Install Plugin From File".
3. Extract the source archive and run `install-macos.command` on macOS, `install-windows.cmd` on Windows, or `python3 scripts/install-engine.py` on Linux. Installing [uv](https://docs.astral.sh/uv/getting-started/installation/) first is recommended.
4. Select a PDF in Zotero and open "BabelDOC 翻译 PDF…". Enter the full Python executable path printed by the installer, then check the engine.
5. Enter the endpoint URL, model, and API key, then start translating. Include `/v1` in the URL if your service requires it. The default language pair is English to Chinese.

The first translation downloads layout models and fonts. The interface and detailed guides are currently in Simplified Chinese; an English interface is not implemented.

## Tested environment

The manifest allows Zotero 7.0 through 10.0.*. Desktop tests used Zotero 10.0.6 on Apple Silicon macOS, Python 3.12.14, and BabelDOC 0.6.4. They ran the real engine against a deterministic local model fixture. These tests check the workflow, not translation quality.

Zotero 7 through 9 and Windows/Linux desktop integration have not been tested. The [validation notes](docs/validation.md) describe what was checked.

## Updates

The repository version is 0.1.2. It uses the runtime code tested in 0.1.1 and adds build, release, update, and repository tooling.

If you installed the earlier local 0.1.1 build, install 0.1.2 manually once. The old build uses a reserved `.invalid` update URL. Subsequent GitHub releases support Zotero update checks. Python engine updates are separate.

## Development

Build with `python3 scripts/build.py --repository ptiris/zotero-babeldoc`. Files go to `dist/`. XPI builds use only Python's standard library. Controller tests use Node.js, with no npm dependencies. Source archives contain Git-tracked files.

- [Development and tests](docs/development.md)
- [Architecture and JSONL protocol](docs/architecture.md)
- [Release and update workflow](docs/publishing.md)
- [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

The plugin is licensed under [AGPL-3.0-or-later](LICENSE). This community project is not affiliated with Zotero or BabelDOC. Dependency details are in [third-party notices](THIRD_PARTY_NOTICES.md).
