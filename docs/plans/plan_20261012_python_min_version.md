## 目的

最低サポート Python を 3.10 から **3.12** に引き上げ、3.12 未満で `main.py` を実行した利用者に、`SyntaxError` ではなく**必要なバージョンを伝えるメッセージ**を出して終了させる。

## 背景・前提

- README の動作要件は「Python 3.10 以上」だが、`src/core/parsers/safe_yaml.py` の 47 行目（`return f'"{inner.replace("\\", "/")}"'`）は、f-string の式の中にバックスラッシュがあり、**3.12 未満では `SyntaxError`** になる（PEP 701）。`safe_yaml` は起動時に import されるため、3.10/3.11 ではアプリが起動しない。
- ユーザーの決定: 最低バージョンは **3.12** とする（3.10 は 2026 年 10 月でサポート終了。配布版は Python を同梱しているため、影響を受けるのはソースから実行する開発者だけ）。
- そのため、`safe_yaml.py` の f-string は 3.12 以降では正しい構文であり、**書き換えない**。
- `main.py` は、先頭付近で `from src.core.env import ...` などを import する。`src` 配下の import の途中で 3.12 未満の `SyntaxError` が出るため、**バージョン確認は、`src` や `PySide6` の import より前に行う必要がある**。
- そのため、確認処理は、`src` パッケージの外にある小さなモジュール `src_bootstrap.py`（リポジトリ直下）に置く。このモジュールは、**3.6 などの古い Python でも構文エラーにならない書き方**にする（`X | Y` の型表記、`match` 文、ジェネリック型のビルトイン表記 `list[str]` などを使わない）。
- 詳細な元の提案: `reference/improvement_proposals_20261012/ISSUE-01_python_min_version.md`（Git 管理外のため、このリポジトリには含まれない。本計画書だけで作業できるように書いてある）。

## 変更対象（ファイル/フォルダ）

- 新規: `src_bootstrap.py`
- 変更: `main.py`
- 変更: `README.md`
- 変更: `packaging/RL-Log-Comparator.spec`
- 新規: `tests/test_python_version_guard.py`
- 新規: `docs/plans/plan_20261012_python_min_version.md`（本計画書。作成済み）

## 手順

1. `src_bootstrap.py` を新規作成する。内容は次の仕様どおりにする。
   - 定数 `MIN_PYTHON = (3, 12)`
   - 関数 `ensure_supported_python(version_info=None)`
     - `version_info` が `None` のときは `sys.version_info` を使う。
     - `(version_info[0], version_info[1]) >= MIN_PYTHON` なら `None` を返す。
     - 満たさないときは、次の 2 行のメッセージ（文字列）を返す。
       - 1 行目: `RL-Log-Comparator には Python 3.12 以上が必要です。`（数字は `MIN_PYTHON` から作る）
       - 2 行目: `現在の Python: <major>.<minor>.<micro>`（`version_info[:3]` から作る）
   - 関数 `exit_if_unsupported_python(version_info=None, show_dialog=True)`
     - `ensure_supported_python(version_info)` の結果が `None` なら何もしない。
     - メッセージがあるときは、次を行って `sys.exit(1)` する。
       - 環境変数 `RL_LOG_COMPARATOR_NO_DIALOG` が空でなければ、ダイアログを出さず、メッセージを標準エラー出力に書く（確認用）。
       - そうでなく `show_dialog` が真で、`sys.platform == "win32"` なら、`ctypes.windll.user32.MessageBoxW(None, メッセージ, "RL-Log-Comparator", 0x10)` を呼ぶ。
       - 上の呼び出しが例外になった場合、またはそれ以外の環境では、メッセージを標準エラー出力に書く（`sys.stderr` が `None` の場合は何もしない）。
   - 標準ライブラリ（`sys`、`os`）だけを import する。`typing` の `Optional` は、古い Python でも使えるので使ってよい。
2. `main.py` を変更する。
   - docstring の直後、**ほかのどの import よりも前**に、次の 2 行を追加する。

     ```python
     from src_bootstrap import exit_if_unsupported_python
     exit_if_unsupported_python()
     ```

   - 既存の import（`sys`、`os`、`PySide6`、`src.*`）は、そのまま残す。
   - 後続の import が「ファイル先頭ではない」ことによる警告が出る場合に備え、`main.py` の変更箇所に、1 行のコメント（なぜここで確認するか: `src` の import より前に Python のバージョンを確認する必要がある）を添える。
3. `README.md` を変更する。`grep -n "3\.10" README.md` で見つかる 3 か所（122 行目付近、135 行目付近、183 行目付近）の `3.10` を、すべて `3.12` に変更する。文言は、数字以外は変えない。
4. `packaging/RL-Log-Comparator.spec` の `hiddenimports` の一覧（`'src',` の直前）に、`'src_bootstrap',` を追加する。
5. `tests/test_python_version_guard.py` を新規作成する（pytest 形式。Qt は使わない）。
   - リポジトリ直下を `sys.path` に追加する必要はない（`tests/conftest.py` と既存テストが `src` を import できているのと同じ方法で、`src_bootstrap` も import できる）。import できなかった場合は、`tests/__init__.py` と既存テストの import の方法に合わせる。
   - 次のテストを書く。
     - `ensure_supported_python((3, 12, 0))` と `(3, 13, 3)` は `None` を返す。
     - `ensure_supported_python((3, 11, 9))` と `(3, 10, 0)` は文字列を返し、その中に `3.12` と、渡したバージョン（例: `3.11.9`）が含まれる。
     - `exit_if_unsupported_python((3, 11, 9), show_dialog=False)` は `SystemExit` を送出し、`code == 1`。メッセージが標準エラー出力に出る（`capsys` を使う）。
     - `exit_if_unsupported_python((3, 12, 0), show_dialog=False)` は何も起こさない（例外なし）。
     - 環境変数 `RL_LOG_COMPARATOR_NO_DIALOG=1`（`monkeypatch.setenv`）を設定し、`show_dialog=True` で呼んでも、`ctypes.windll.user32.MessageBoxW` が呼ばれず（`monkeypatch` でダミーに差し替えて、呼ばれたら失敗させる）、メッセージが標準エラー出力に出る。
6. 手元で確認する。
   - `python -m pytest tests/test_python_version_guard.py -q`
   - `python -m pytest -q`（既存テストも含む全件。`qtbot` が見つからないことによる 18 件の error は、本計画書の範囲外であり、変更前から存在するため、件数が増えていないことだけを確認する）
   - 3.12 未満での動作確認: `py -3.10`（なければ `py -3.6` など、3.12 未満の任意の版）で、次を実行する。

     ```text
     set RL_LOG_COMPARATOR_NO_DIALOG=1
     py -3.10 main.py
     ```

     標準エラー出力に、`Python 3.12 以上が必要です` と現在のバージョンが表示され、終了コードが 1 であること（`echo %ERRORLEVEL%`）。

## やらないこと（触らない範囲）

- `src/core/parsers/safe_yaml.py` を含む、`src/` 配下のコードの変更（3.12 では正しい構文のため、書き換えない）
- 3.10/3.11 で動かすための互換対応
- `pyproject.toml`、`requirements*.txt`、`.github/` の作成・変更（ruff の設定などは別の Issue で行う）
- `README.md` の、バージョン番号以外の変更
- `APP_VERSION`（アプリのバージョン）やインストーラーの設定の変更
- CI（GitHub Actions など）の構築
- 既存テストの変更
- `main` ブランチへの直接のコミット

## 完了条件

- [x] `src_bootstrap.py` が追加され、`ensure_supported_python` と `exit_if_unsupported_python` が仕様どおりに動く
- [x] `main.py` で、ほかのどの import よりも前にバージョン確認が呼ばれている
- [x] 3.12 未満の Python で `main.py` を実行すると、`SyntaxError` ではなく、必要なバージョンと現在のバージョンを伝えるメッセージが出て、終了コード 1 で終わる（実行した Python のバージョンと出力を報告する）
- [x] 3.12 以上（開発機の 3.13）では、従来どおり起動できる（`python main.py` を数秒起動して終了させる、または `QT_QPA_PLATFORM=offscreen` で `import main` が通ることを確認する）
- [x] `README.md` に `3.10` が残っていない（`grep -n "3\.10" README.md` が 0 件）
- [x] `packaging/RL-Log-Comparator.spec` の `hiddenimports` に `src_bootstrap` が含まれている
- [x] `tests/test_python_version_guard.py` が追加され、すべて通る
- [x] `python -m pytest -q` の結果が、変更前（94 passed / 18 errors）から悪化していない（error 件数が 18 のままで、passed が増えている）
- [x] この計画書の「完了条件」のチェックリストが更新されている

## 検証方法

- 上記「手順」の 6 のコマンドを、すべて実行して結果を報告する。
- 変更したファイルの一覧（`git diff --stat main...HEAD`）を報告する。
- 最終のテスト結果（`python -m pytest -q` の最終行）を報告する。

## 質問（実装側が詰まったら記入）

- （なし）
