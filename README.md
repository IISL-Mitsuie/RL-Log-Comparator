# RL-Log-Comparator (強化学習実験ログ対比・比較分析ツール)

強化学習（RL）や転移学習（SAP）シミュレーションで得られた2つの実験出力ログフォルダ（`output_YYYYMMDD_HHMMSS`）を指定し、ハイパーパラメータの差分抽出、画像同期比較、学習曲線の重ね合わせプロットを行うスタンドアロン GUI アプリケーション（PySide6 / Qt / Matplotlib）です。

---

## 1. 主な機能

1. **実験ログ一覧・探索 (Log Explorer)**
   * 指定した親フォルダ配下の実験ログ（`output_YYYYMMDD_HHMMSS` 等）および設定ファイル（`config_used_*.yaml`）を自動走査。再帰的スキャンに対応。
   * モード、Shield有無（有効/無効バッジ）、フォルダ名、および YAML の設定パラメータ（ドット記法フラット化）を表形式で一覧表示。ヘッダークリックによるソートに対応。
   * **多機能フィルタリング & 列カスタマイズ**: 全列横断インクリメンタル検索（クイックフィルタ）、列ヘッダー右クリックや詳細ダイアログによる「列フィルター」、ヘッダー右クリックからの即時非表示、「⚙️ カラム表示設定」ダイアログによる表示項目の自由な調整に対応。
   * **Shift ＋ マウスホイール横スクロール**: 多数のパラメータ列が並ぶ場合でも、Shiftキー＋ホイール操作でピクセル単位で滑らかに水平スクロール可能。
   * **右サイドバー 画像ログ動的プレビュー**: フォルダ内の画像群（PNG, JPG等）のファイル名プレフィックスを動的検出し、アルファベット順にタブ化してプレビュー表示。同一プレフィックスの画像が複数存在する場合は最新の1枚を自動選定。行選択を変更しても選択中のプレフィックスを維持。「🖼️ プレビュー非表示 ❯」でサイドバーの開閉も可能。
   * **ダブルクリック & 右クリック連携**: 行ダブルクリック、または右クリックメニューから「フォルダAに設定」「フォルダBに設定」「エクスプローラーで開く」を即座に実行可能。
   * **セッション自動復元 & 探索履歴**: アプリ終了時の探索ルートパスやフォルダA/Bを次回起動時に自動復元。直近5件の探索ルート履歴ドロップダウンを搭載。
2. **ハイパーパラメータ差分比較 (YAML)**
   * 2つの実験フォルダ内の設定ファイル（`config_used_*.yaml`）を自動検出し、ツリー構造で並列比較。
   * 差分があるパラメータを自動ハイライト表示。「差分があるパラメータのみ表示」フィルタで変更点を即座に抽出可能。
   * 「すべて展開」「すべて折りたたむ」ボタンによるワンクリックツリー操作。
3. **同種画像目視比較**
   * 同種画像（`trajectory_*.png`, `learning_rewards_*.png`, `learning_steps_*.png` 等）を自動マッチングまたは個別クロス選択して比較。
   * **4つの表示モード**:
     * **並列**: 左右に並べて同期パン＆ズーム表示。
     * **オーバーレイ**: 実験Bを実験Aの上に重ね、不透明度スライダー（0〜100%）で透過度を調整。
     * **スワイプ**: ドラッグ可能な縦境界線により、左側に実験A、右側に実験Bを分割表示。
     * **差分**: 画素ごとの差の絶対値 `|A - B|` を可視化（差分画素の割合表示、×1〜×10 の増幅率調整に対応）。
   * **異なる画像サイズの自動補正**: サイズが異なる画像同士でも A のサイズに合わせて縦横比を保って自動リサイズし、重ね合わせ表示が可能（リサイズ注記を表示）。
   * **同期パン＆ズーム**: マウスホイールでズーム（0.1〜40.0倍）、ドラッグでパン移動。「ズーム・位置リセット」ボタンで初期表示状態に即時復帰。
4. **数値ログ比較グラフ (CSV)**
   * 学習ログ（`learning_log_*.csv`）から `TotalReward`, `Steps`, `UnsafeActions`, `GoalSuccessRate`（`Result` 列から自動算定）の推移を同一グラフ上に重ね合わせ描画。
   * **移動平均スライダー**: 1〜50エピソードの移動平均ウィンドウ幅をリアルタイム調整可能。
   * **生データ背景表示**: 生データを薄色で背景表示し、全体のばらつきと傾向を同時に把握。
   * **グラフテキスト・フォント設定**: グラフタイトル、X軸・Y軸ラベル、凡例、および各フォントサイズ（軸ラベル、軸目盛り数値、タイトル、凡例）をGUI上でリアルタイム微調整可能。設定はセッション間で自動保存。
   * **Matplotlib ナビゲーションバー & 高精細保存 (300 DPI)**: グラフの拡大・移動、および印刷・論文投稿品質（300 DPI）での高解像度画像保存に対応。
   * **文字化け・表示崩れ防止**: オープンソース日本語フォント（IPAexゴシック）をアプリ内に同梱し、環境やOSテーマ（ダークモード含む）に依存しない安定したグラフ描画を実現。
5. **ログデータ仕様ガイド・エクスポート**
   * アプリケーション内で対応ログフォーマット仕様書（[DATA_FORMAT.md](DATA_FORMAT.md)）を直接 Markdown 閲覧可能。
   * 右上のダウンロードボタンから仕様書 Markdown をローカルへ保存可能。
6. **自動アップデート機能**
   * 起動時またはヘルプメニューから GitHub Releases の最新リリースを自動確認。
   * ワンクリックでアップデータをバックグラウンド取得し、最新バージョンへシームレスに更新可能。

```mermaid
flowchart TD
    subgraph Experiments ["比較対象実験フォルダ (2つ選択)"]
        ExpA["フォルダ A (基準)<br>output_20260801_235449"]
        ExpB["フォルダ B (比較対象)<br>output_20260801_181036"]
    end

    subgraph Tool ["RL-Log-Comparator (PySide6 GUI)"]
        Tab1["1. 実験ログ一覧・探索<br>(走査・プレビュー・A/Bセット)"]
        Tab2["2. ハイパーパラメータ差分<br>(YAMLツリー比較)"]
        Tab3["3. 画像目視比較<br>(同期パン＆ズーム)"]
        Tab4["4. 数値ログ比較グラフ<br>(CSV重ね合わせプロット)"]
        Tab5["5. 仕様ガイド & エクスポート<br>(DATA_FORMAT.md)"]
    end

    Tab1 -.->|ダブルクリック / 右クリックでA/Bセット| ExpA
    Tab1 -.->|ダブルクリック / 右クリックでA/Bセット| ExpB
    ExpA --> Tool
    ExpB --> Tool
```

---

## 2. ディレクトリ構成

GitHub リポジトリで追跡・管理されているファイル構成および各ファイルへのリンクは以下の通りです：

```text
RL-Log-Comparator/
├── .gitignore                          # Git除外設定ファイル
├── README.md                           # 本ドキュメント (操作マニュアル・ビルド手順・仕様)
├── DATA_FORMAT.md                      # 実験ログ・YAML設定ファイルのフォーマット仕様書
├── requirements.txt                    # 依存パッケージ一覧 (PySide6, matplotlib, pandas, etc.)
├── requirements-dev.txt                # 開発用依存パッケージ一覧 (pytest, pytest-qt)
├── pyproject.toml                      # 開発ツール設定 (pytest)
├── main.py                             # アプリケーション本体 (エントリーポイント / PySide6 GUI)
├── build_all.bat                       # ワンクリック全自動クリーンビルドバッチ (Windows用)
├── src/                                # アプリケーションソースコード
│   ├── config.py                       # バージョン・定数・アプリ設定
│   ├── core/                           # コアロジック (パーサー・履歴・アップデートエンジン)
│   └── ui/                             # UIコンポーネント (メインウィンドウ・ウィジェット・ダイアログ)
├── tests/                              # pytest による自動テストスイート (テストデータは tests/fixtures/)
└── packaging/                          # 配布・パッケージング設定フォルダ
    ├── app_icon.ico                    # マルチサイズアプリアイコン (16〜256px)
    ├── build.py                        # クリーン仮想環境構築・PyInstaller・Inno Setup連動ビルドエンジン
    ├── installer.iss                   # Inno Setup インストーラー定義スクリプト
    ├── version_info.txt                # Windows実行ファイル用メタデータ (バージョン・著作権情報)
    ├── RL-Log-Comparator.spec          # アイコン・フォント・メタデータ連動 PyInstaller 定義ファイル
    └── fonts/                          # 同梱日本語フォントフォルダ
        ├── ipaexg.ttf                  # IPAexゴシックフォント (グラフ用日本語TrueTypeフォント)
        ├── IPA_Font_License_Agreement_v1.0.txt # IPAフォント使用許諾契約書
        └── Readme_IPAexfont00401.txt   # IPAexフォント Readme
```

### 管理対象ファイル一覧（クイックアクセス）

| ファイル / フォルダ | 説明 |
| :--- | :--- |
| [`.gitignore`](.gitignore) | Git 管理対象外設定ファイル |
| [`README.md`](README.md) | 本ドキュメント（操作マニュアル・ビルド手順・プロジェクト概要） |
| [`DATA_FORMAT.md`](DATA_FORMAT.md) | 実験ログ・YAML設定ファイルの入出力フォーマット仕様書 |
| [`requirements.txt`](requirements.txt) | 最小限の Python 依存パッケージ定義一覧 |
| [`requirements-dev.txt`](requirements-dev.txt) | 開発・テスト用の依存パッケージ定義一覧 |
| [`pyproject.toml`](pyproject.toml) | 開発ツール設定 (pytest) |
| [`main.py`](main.py) | アプリケーションのエントリーポイント (PySide6 GUI 本体) |
| [`src/`](src/) | アプリケーションソースコードパッケージ |
| ├─ [`src/config.py`](src/config.py) | 定数・パス・バージョン・設定定義 |
| ├─ [`src/core/`](src/core/) | データパース・セッション履歴・自動更新コア |
| └─ [`src/ui/`](src/ui/) | メインウィンドウ・比較ウィジェット・各種ダイアログ |
| [`tests/`](tests/) | 単体・UI自動テストスイート（pytest） |
| [`build_all.bat`](build_all.bat) | ワンクリック全自動クリーンビルドバッチ (Windows用) |
| [`packaging/`](packaging/) | 配布パッケージ・インストーラー作成関連フォルダ |
| ├─ [`packaging/app_icon.ico`](packaging/app_icon.ico) | アプリケーションアイコン (マルチ解像度) |
| ├─ [`packaging/build.py`](packaging/build.py) | 全自動クリーンビルド＆インストーラー作成スクリプト |
| ├─ [`packaging/installer.iss`](packaging/installer.iss) | Inno Setup インストーラー定義スクリプト |
| ├─ [`packaging/version_info.txt`](packaging/version_info.txt) | Windows 実行ファイル用バージョン・著作権情報定義 |
| ├─ [`packaging/RL-Log-Comparator.spec`](packaging/RL-Log-Comparator.spec) | PyInstaller パッケージング定義ファイル |
| └─ [`packaging/fonts/`](packaging/fonts/) | 同梱日本語フォントフォルダ |
| 　　├─ [`packaging/fonts/ipaexg.ttf`](packaging/fonts/ipaexg.ttf) | IPAexゴシックフォント (日本語TrueTypeフォント) |
| 　　├─ [`packaging/fonts/IPA_Font_License_Agreement_v1.0.txt`](packaging/fonts/IPA_Font_License_Agreement_v1.0.txt) | IPAフォント使用許諾契約書 v1.0 |
| 　　└─ [`packaging/fonts/Readme_IPAexfont00401.txt`](packaging/fonts/Readme_IPAexfont00401.txt) | IPAexフォント Readme (Ver.004.01) |

---

## 3. インストール・起動方法

### 動作要件
- **OS**: Windows 10 / 11 (x64)
- **Python**: 3.12 以上 (Pythonスクリプトとして実行する場合)

---

### 3.1. インストーラーを使用する場合 (推奨)
1. 配布ファイル（GitHub Releases の Assets）から `RL_Log_Comparator_Setup_v<バージョン>.exe` をダウンロードして実行します。
2. 画面の指示に従ってインストールします（管理者権限不要、ユーザー個別領域 `{localappdata}\Programs\RL-Log-Comparator` に安全に配置されます）。
3. デスクトップまたはスタートメニューの「RL-Log-Comparator」ショートカットから起動します。
4. ※ インストーラを使用しない場合は、ポータブル版 ZIP（`RL_Log_Comparator_v<バージョン>_portable.zip`）を解凍して `RL-Log-Comparator.exe` を直接起動することも可能です。

---

### 3.2. Python 環境から直接起動する場合
Python 3.12 以上がインストールされた環境で以下を実行します：

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# アプリケーションの起動
python main.py

# コマンドライン引数で比較対象フォルダを直接指定して起動することも可能
python main.py path/to/output_A path/to/output_B
```

* 依存パッケージ定義: [`requirements.txt`](requirements.txt)
* 起動スクリプト: [`main.py`](main.py)

---

### 3.3. 開発者向け: テストの実行
開発用の依存パッケージ（pytest, pytest-qt, ruff）をインストールしてからテストを実行します：

```bash
# 開発用依存パッケージのインストール (requirements.txt も併せてインストールされます)
pip install -r requirements-dev.txt

# 全テストの実行
python -m pytest
```

* Windows では [`tests/run_tests.bat`](tests/run_tests.bat) からも実行できます。
* テスト実行中のアプリ設定（フォルダ履歴・フォントサイズ等）は一時 INI ファイルに保存され、通常利用時の設定（レジストリ）は読み書きされません。
* 開発用依存パッケージ定義: [`requirements-dev.txt`](requirements-dev.txt)、pytest・ruff 設定: [`pyproject.toml`](pyproject.toml)

#### 品質チェック（`check.bat`）
変更をプッシュする前に、リポジトリ直下の [`check.bat`](check.bat) で静的解析とテストをまとめて実行します：

```bat
.\check.bat
```

1. **ruff**（`python -m ruff check src main.py src_bootstrap.py packaging tests`）: 未使用の import・未定義の名前・構文エラーを検出します（有効な規則は `F` と `E9`）。
2. **pytest**（`python -m pytest -q`）: 全テストを実行します。`QT_QPA_PLATFORM=offscreen` を設定するため、テスト中にウィンドウは表示されません。

すべて成功すると終了コード 0（`[OK] all checks passed`）、いずれかが失敗すると終了コード 1（`[NG] checks failed`）で終了します。

#### 任意: push 前の自動チェック（pre-push フック）
次のコマンドを一度実行すると、`git push` の前に `check.bat` が自動で実行され、失敗した場合は push が中止されます（有効化は任意です。設定しなくても通常どおり commit・push できます）：

```bash
git config core.hooksPath .githooks
```

* フックは Windows の Git（Git for Windows）から `cmd.exe` 経由で `check.bat` を実行します。WSL・macOS・Linux の git では動作しないため、有効にしないでください。
* 検査するのは push するコミットではなく、作業ツリーのファイルです。コミットしていない変更がある状態では、結果が push 内容と一致しないことがあります。
* 一時的にスキップする場合: `git push --no-verify`
* 無効に戻す場合: `git config --unset core.hooksPath`
* 本リポジトリは **CI（GitHub Actions などの外部サービス）を使わない方針**です。検査は上記のとおり手元で実行します。

---

## 4. 操作手順・使用方法

1. **「1. 実験ログ一覧・探索 (Log Explorer)」タブ**:
   * 「探索ルートフォルダ」に実験結果の親フォルダ（`runs/` や `logs/` など）を指定し、「再読込」をクリックします。
   * 表一覧に配下の実験ログとパラメータが自動展開されます。クイックフィルタや列フィルターで目的の実験を絞り込みます。
   * 行を選択すると右サイドバーに画像ログのプレビューが表示されます（プレビュー不要時は「🖼️ プレビュー非表示 ❯」で折りたたみ可能）。
   * 比較したい実験ログを**ダブルクリック**するか、**右クリックメニューから「フォルダAにセット」「フォルダBにセット」**を選択します。
2. **上部フォルダ選択バー**:
   * 上部の「フォルダ A (基準)」および「フォルダ B (比較)」の「参照...」ボタンから直接フォルダを選択することも可能です。
   * 前回セッションで開いていたパスは次回起動時に自動復元されます。
3. **「2. ハイパーパラメータ差分 (YAML)」タブ**:
   * 差分があるパラメータがハイライト表示されます。「差分があるパラメータのみ表示」のチェックを外すと全設定項目を確認できます。
   * 「すべて展開」「すべて折りたたむ」でツリー全体の開閉を一括切り替えできます。
4. **「3. 画像目視比較」タブ**:
   * 左側のリストから比較したい画像（`trajectory`, `learning_rewards`, `learning_steps` 等）を選択します。「左右自由選択モード」にチェックを入れると、左右で異なる種類の画像を個別に選んで対比することも可能です。
   * **表示モード切替**:
     * **並列**: 従来の左右並列ビューです。ホイールでズーム、ドラッグでパン移動すると、左右の画像が完全同期して動作します。
     * **オーバーレイ**: B を A の上に重ねて表示します。「不透明度 (B)」スライダー（0〜100%）で前景画像の透過度を滑らかに調整できます。
     * **スワイプ**: 縦の境界線をドラッグして、左側に A、右側に B を分割表示します。微細な位置ずれや走行軌跡の差異を直接比較できます。
     * **差分**: 画素ごとの差の絶対値 `|A - B|` を計算して表示します。差分がない部分は黒となり、変更点のみが浮き彫りになります。「差分増幅率」（×1〜×10）で微小な差を強調でき、「差分画素: X.X%」で差異の割合を数値で確認できます。
   * サイズが異なる画像同士を重ねる場合、自動的に A のサイズに合わせて縦横比を保ったままリサイズされ、画面上に注記（例: 「※B を 1600×1200 → 800×600 に縮小して重ねています」）が表示されます。片側の画像しかない場合は重ねるモードは自動的に無効化されます。
   * 「ズーム・位置リセット」ボタンで元の全体表示に戻せます。
5. **「4. 数値ログ比較グラフ (CSV)」タブ**:
   * 左側リストから表示したい指標（`TotalReward`, `Steps`, `UnsafeActions`, `GoalSuccessRate`）を選択します。
   * 「移動平均ウィンドウ」スライダーで平滑化ウィンドウ幅（1〜50エピソード）をリアルタイム調整できます。
   * 「生データを背景表示」チェックボックスで生データの重畳表示を切り替えられます。
   * 「グラフテキスト・フォント設定」にて、タイトル・軸ラベル・凡例の文言編集に加え、フォントサイズ（軸ラベル、軸数値、タイトル、凡例）を 6〜28 pt の範囲でリアルタイム微調整できます。「🔄 すべてデフォルトに戻す」で初期値に復帰可能です。
   * ナビゲーションバーの「保存」ボタンから、設定したフォントサイズを反映した高解像度グラフ（300 DPI）を保存できます。
6. **「5. ログ仕様ガイド・エクスポート」タブ**:
   * 対応するログデータの仕様書（[`DATA_FORMAT.md`](DATA_FORMAT.md)）をアプリ内で確認できます。右上のボタンからローカルにダウンロード保存も可能です。

---

## 5. インストーラー・バイナリのビルド手順

本リポジトリには、PyInstaller による高速起動バイナリ作成と Inno Setup によるインストーラーおよびポータブル版 ZIP 作成を全自動で行うスクリプトが用意されています。
バージョン番号は [`src/config.py`](src/config.py) の `APP_VERSION` で一元管理されており、ビルド時に自動で exe のプロパティ、インストーラー、ZIP ファイル名へ反映されます。

### 前提条件
- Python 3.12 以上
- [Inno Setup 6](https://jrsoftware.org/isdl.php)（Windows セットアップインストーラーを作成する場合。未インストールの場合はバイナリとポータブル ZIP のみ生成されます）

### ビルド実行
リポジトリルートにある [`build_all.bat`](build_all.bat) を実行（またはコマンドラインから引数を指定して実行）します：

```bash
build_all.bat
# または
python packaging/build.py
```

#### オプション引数
- `--use-current-env`: `%TEMP%` 内のクリーン仮想環境の作成をスキップし、現在実行中の Python 環境（`sys.executable`）をそのまま使ってビルドします（オフライン環境等向け）。
- `--skip-tests`: ビルド開始前の pytest スイート（`pytest -q`）の実行をスキップします。

```bash
# 例: テストをスキップして現在の環境で高速ビルド
python packaging/build.py --use-current-env --skip-tests
# bat 経由でも引数をそのまま渡せます
build_all.bat --use-current-env --skip-tests
```

### ビルドフローの詳細
1. **事前テスト実行**: 現在の Python 環境で `pytest -q` を実行し、既存テスト全件の通過を確認（失敗時はビルドを自動中止、`--skip-tests` で省略可能）。
2. **クリーン一時仮想環境の作成**: ローカルの `%TEMP%` 内に一時的な独立仮想環境を作成（Google Drive などのクラウド同期ロックや権限問題を完全回避）。
3. **再現性のある依存インストール**: [`requirements-build.txt`](requirements-build.txt) および [`constraints.txt`](constraints.txt)（バージョン固定制約）を用いて、ビルドに必要な最小限の依存関係のみをインストール。
4. **バージョン情報の動的生成**: [`src/config.py`](src/config.py) の `APP_VERSION` を読み取り、[`packaging/version_info.template.txt`](packaging/version_info.template.txt) から一時的な Windows バージョンリソース情報（`version_info.txt`）を生成。
5. **バイナリビルド**: PyInstaller（[`packaging/RL-Log-Comparator.spec`](packaging/RL-Log-Comparator.spec)）により `--onedir` 形式で高速起動可能な単体実行ファイル群（`dist/RL-Log-Comparator/`）をビルド。
6. **ポータブル版 ZIP の生成**: 配布用のポータブルアーカイブ（`dist_installer/RL_Log_Comparator_v<バージョン>_portable.zip`）を自動生成。
7. **セットアップインストーラー生成**: Inno Setup 6 (`ISCC.exe`) を自動検知し、`/DMyAppVersion=<バージョン>` を注入して [`packaging/installer.iss`](packaging/installer.iss) からセットアップインストーラー（`dist_installer/RL_Log_Comparator_Setup_v<バージョン>.exe`）を生成。
8. **成果物の配置とクリーンアップ**: 生成物をプロジェクトルートの `dist/` および `dist_installer/` にコピーし、一時仮想環境や作業ディレクトリを自動削除。

---

## 6. 関連ドキュメント・フォントライセンス

* **[DATA_FORMAT.md](DATA_FORMAT.md)**: ログデータ出力フォーマット仕様書
* **IPAexゴシック (Ver.004.01)**:
  * 配布元: [独立行政法人情報処理推進機構 (IPA)](https://moji.or.jp/ipafont/)
  * フォントファイル: [`packaging/fonts/ipaexg.ttf`](packaging/fonts/ipaexg.ttf)
  * ライセンス: [IPAフォント使用許諾契約書 v1.0](packaging/fonts/IPA_Font_License_Agreement_v1.0.txt)
  * Readme: [`packaging/fonts/Readme_IPAexfont00401.txt`](packaging/fonts/Readme_IPAexfont00401.txt)



