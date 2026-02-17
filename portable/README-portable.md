# PresidioPDF Portable (Windows)

このドキュメントは、`PresidioPDF` をスタンドアローンZIPとして作成・検証する手順です。

## 仕様
- 対象OS: Windows x64
- Python: embeddable package `3.11.9`
- 同梱対象: `src/` のみ
- 実行形態: GUIのみ
- オフライン運用: 配布先は完全オフライン前提
- 同梱モデル: `ja_core_news_sm`, `ja_core_news_md`, `ja_core_news_lg`, `ja_core_news_trf`
- 除外モデル: `ja_ginza_electra`

## 前提条件（ビルドPC）
- `uv` が使えること
- Python 3.11 の `python.exe` があること
  - 既定: `%APPDATA%\uv\python\cpython-3.11-windows-x86_64-none\python.exe`
  - 別パスを使う場合は `-BuildPython` を指定

## 作成コマンド
```powershell
powershell -ExecutionPolicy Bypass -File tools\build_portable.ps1
```

`python.exe` の場所を明示する場合:
```powershell
powershell -ExecutionPolicy Bypass -File tools\build_portable.ps1 -BuildPython "C:\path\to\python.exe"
```

## 検証コマンド
```powershell
powershell -ExecutionPolicy Bypass -File tools\verify_portable.ps1 -PortableRoot ".\.tmp_portable\PresidioPDF-0.1.0-win64-portable"
```

## 出力物
- ZIP: `dist\PresidioPDF-0.1.0-win64-portable.zip`
- 展開用作業ディレクトリ: `.tmp_portable\PresidioPDF-0.1.0-win64-portable`

## 既知事項
- ターゲット環境によっては Visual C++ Runtime が必要です。
- 本配布は `src/` のみ同梱です。`config/` や `README.md` は含みません。
