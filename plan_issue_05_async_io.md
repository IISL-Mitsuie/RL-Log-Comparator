# 計画書: [ISSUE-05] 重い I/O の非同期化と、自動読み込みのデバウンス

| 項目 | 内容 |
| :--- | :--- |
| 優先度 | **P1**（Google ドライブ等のネットワーク上のログで UI が固まる） |
| 種別 | perf |
| 規模 | M〜L |
| 依存 | ISSUE-07（ワーカー内の例外をログに残すため、先に実施することを推奨） |
| 対象ファイル | （新規）`src/ui/workers.py`, `src/ui/main_window.py`, `src/ui/widgets/experiment_explorer_widget.py`, `src/core/parsers/experiment_scanner.py`, 関連テスト |
| ブランチ名 | `agy/issue-05-async-io` |

---

## 1. 背景・現状

本アプリの主な利用環境は、ログが **Google ドライブなどのネットワークドライブ上**にある Windows である。ネットワーク越しのファイル I/O は 1 回あたり数十〜数百ミリ秒かかることがある。しかし、重い I/O はすべて **UI スレッドで同期的に**実行されている。

| # | 処理 | 該当箇所 | 内容 |
| :--- | :--- | :--- | :--- |
| 1 | 探索ルートの走査 | `experiment_explorer_widget.py` → `experiment_scanner.py` | `os.walk`、各フォルダの `listdir`、YAML の解析、CSV のヘッダー読み込み、継続学習時は CSV 全行の読み込み（`_count_tasks_from_csv`）を同期で行う。直前の「フォルダを探索中…」という表示も、イベントループが回らないため**画面に出ない** |
| 2 | 行の選択時のプレビュー | `experiment_explorer_widget.py` | 選択した実験の**全画像**を、原寸の `QPixmap` として同期でデコードする（継続学習では 1 フォルダ 20 枚以上） |
| 3 | A/B の読み込み | `main_window.py` | YAML、画像の一覧、CSV を 3 タブ分まとめて同期で読み込む |
| 4 | 自動読み込みの発火条件 | `main_window.py` | フォルダ欄の `textChanged`（**1 文字入力するごと**）で `_check_auto_load` が呼ばれる。もう一方の欄が有効なとき、入力途中のパスが実在するディレクトリだと、そのたびに `load_all` が走る |

## 2. 目的

- 走査・読み込み・画像デコードの間も、UI が操作を受け付ける（ウィンドウの移動、タブの切り替え、キャンセル）。
- 進捗とキャンセルが利用者に見える。
- パスの入力途中で読み込みが走らない。

## 3. 採用するベストプラクティス

- Qt では、UI 部品の操作はメインスレッドに限り、I/O と解析はワーカースレッドで行う。結果は **Signal（キュー接続）** で受け取る。
- ワーカーには `QThreadPool` + `QRunnable` を使う（スレッドの生成と破棄を Qt に任せられる）。`QRunnable` は Signal を持てないため、Signal 用の `QObject` を別に持たせる。
- 古い要求の結果が新しい結果を上書きしないよう、**世代番号（generation counter）** で結果を破棄する。
- 入力欄の自動処理は `QTimer.singleShot` による**デバウンス**（最後の入力から一定時間後に 1 回だけ実行）にする。
- 画像のプレビューは、表示サイズに縮小してデコードする（`QImageReader.setScaledSize`）。`QPixmap` は UI スレッドでしか扱えないため、ワーカーでは `QImage` を作り、UI スレッドで `QPixmap.fromImage` する。

## 4. 作業手順

### 4.1 共通ワーカー
- [x] `src/ui/workers.py` を新規作成する。
  - `WorkerSignals(QObject)`: `finished = Signal(int, object)`, `failed = Signal(int, str)`, `progress = Signal(int, int, str)` (世代番号, 進捗/結果)
  - `FunctionWorker(QRunnable)`: 対象関数、引数、generation、cancel_event (threading.Event) を保持。対象関数が cancel_event 引数を受け取る場合は渡す。
  - 例外発生時は `logger.exception("Worker failed")` でログ出力した上で `failed` シグナルを送出。

### 4.2 探索ルートの走査
- [x] `src/core/parsers/experiment_scanner.py`:
  - `scan_experiments_directory` に `progress_callback: Optional[Callable[[int, str], None]] = None`, `cancel_event: Optional[threading.Event] = None` を追加。
  - 各ディレクトリ走査のループで `cancel_event.is_set()` をチェックし、セットされていれば中断してそれまでの結果を返す。進捗があれば `progress_callback(count, current_folder_name)` を呼ぶ。
  - **重要**: `src/core/parsers/` には Qt 依存を持ち込まない（Python 標準ライブラリのみ使用）。
- [x] `src/ui/widgets/experiment_explorer_widget.py`:
  - `scan_directory(self, *, blocking: bool = False)` および `set_root_directory(..., blocking: bool = False)` を実装。
  - `blocking=False`（既定）では `QThreadPool` + `FunctionWorker` で走査。
  - 走査中は「再読込」ボタンを「中止」に切り替え、ステータス欄に「探索中… N 件目: <フォルダ名>」を表示。
  - 世代番号（generation counter）で古い走査結果を破棄。
  - 既存テストで同期実行を前提としている箇所は `blocking=True` または `qtbot.waitUntil` を使うよう更新。

### 4.3 プレビュー画像
- [x] `ImagePreviewLabel.set_image`:
  - ファイルパスを受け取ったら非同期でデコードする経路を追加。
  - ワーカーで `QImageReader(path)` を作り、長辺上限 1600px・表示サイズに合わせて縮小デコード（ワーカーでは `QImage` を返し、UI スレッドで `QPixmap.fromImage`）。
  - 選択中のタブの画像を最優先でデコードし、他タブは `QTabWidget.currentChanged` で遅延読み込み。
  - デコード中は「読み込み中…」を表示。
  - `(path, mtime, 縮小サイズ)` をキーにした LRU キャッシュ（最大 64 枚）を導入。

### 4.4 A/B の読み込み
- [x] `src/ui/main_window.py`:
  - `ComparisonData` データクラスを定義。
  - ワーカー側: YAML 読み込み（`read_yaml_file` ×2）、画像ペア検出（`detect_image_pairs`、`get_folder_image_list` ×2）、CSV 読み込み（`read_log_csv` ×2、`scan_task_options` ×2）、`get_experiment_info` ×2 をまとめて実行。
  - UI 側: 各タブに `apply_data(...)` を追加して表示反映（`load_yamls`, `load_folders`, `load_csvs` は互換性のため維持）。
  - 読み込み中はフォルダ選択欄の右に不定表示の `QProgressBar(0, 0)` を表示。
  - 世代番号で古い結果を破棄。
  - CLI 起動（`python main.py <A> <B>`）やテストからの呼び出し互換性を維持。

### 4.5 自動読み込みのデバウンス
- [x] フォルダ入力欄の `textChanged` では 500ms の単発 `QTimer` を再始動するだけにし、満了時に `_check_auto_load` を呼ぶ。
- [x] `lineEdit().editingFinished`、履歴選択、参照ダイアログ、Explorer からの設定時はタイマーを止めて即座に読み込む。

### 4.6 テストの追加・更新
- [x] 単体テストの追加: デバウンス（500ms 以内の連続入力で 1 回のみ発火）、世代番号による古い結果の破棄、走査の中止動作。
- [x] 既存テストの更新（非同期化に伴う待機や `blocking=True` の指定）。

---

## 5. 完了条件

- [x] 100 個以上の実験フォルダを含むルートの走査中も、ウィンドウの移動とタブの切り替えができる
- [x] 走査中に「中止」を押すと、それまでに見つかった分が表に表示される
- [x] 走査中のステータス表示が実際に画面に出る
- [x] Explorer で行を素早く上下に移動しても UI が固まらず、最後に選んだ行のプレビューが表示される（途中の行の画像で上書きされない）
- [x] フォルダ A 欄にパスを 1 文字ずつ手入力しても、入力中に読み込みが走らない（`load_all` の呼び出し回数をログまたはテストで確認する）
- [x] CLI 起動（`python main.py <A> <B>`）で、従来どおり起動直後に比較が表示される
- [x] 既存テストがすべて通る（必要に応じて `blocking=True` や `qtbot.waitUntil` に書き換える。書き換えた箇所を報告する）
- [x] 新規テスト: デバウンス（`qtbot.wait` で 500ms 以内の連続入力では 1 回だけ読み込まれる）、世代番号による古い結果の破棄

## 6. やらないこと

- `QTableWidget` からモデル／ビュー（`QAbstractTableModel`）への移行（必要なら別 Issue）
- 走査結果のディスクキャッシュ（mtime ベースの永続キャッシュ）
- CSV グラフの再描画の最適化（ISSUE-06）
- `src/core/parsers/` への Qt 依存の持ち込み

## 7. 質問・未決事項

- **Q-05-1**: 自動読み込みのデバウンス時間は 500ms でよいか → 500ms（Issue 指定通り）。
