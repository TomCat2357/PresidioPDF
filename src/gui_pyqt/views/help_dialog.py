"""PresidioPDF PyQt - ヘルプダイアログとトピック定義"""

from typing import Dict

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
)


HELP_TOPICS: Dict[str, Dict[str, str]] = {
    "general": {
        "title": "使い方ガイド",
        "body": """
<h3>基本フロー</h3>
<ol>
  <li><b>開く</b> で PDF を読み込みます。</li>
  <li><b>対象検出</b> または <b>OCR</b> を必要に応じて実行します。</li>
  <li>結果表で <b>削除</b>、<b>無視対象</b>、<b>追加検出対象</b> を使って調整します。</li>
  <li><b>重複削除</b> で候補を整理します。</li>
  <li><b>保存</b> または <b>エクスポート</b> で出力します。</li>
</ol>
<h3>主要ショートカット</h3>
<table border="1" cellspacing="0" cellpadding="4">
  <tr><th align="left">キー</th><th align="left">動作</th></tr>
  <tr><td><code>F1</code></td><td>現在の操作に応じたヘルプを開く</td></tr>
  <tr><td><code>Esc</code></td><td>F1 の説明待ちを解除し、? カーソルを消す</td></tr>
  <tr><td><code>F5</code></td><td>全ページの対象検出を実行</td></tr>
  <tr><td><code>PgDown</code> / <code>PgUp</code></td><td>ページ移動</td></tr>
  <tr><td><code>Home</code> / <code>End</code></td><td>先頭 / 最後のページへ移動</td></tr>
  <tr><td><code>Delete</code></td><td>選択エンティティを削除</td></tr>
  <tr><td><code>Backspace</code></td><td>選択語を無視対象に登録</td></tr>
  <tr><td><code>Insert</code></td><td>選択語を追加検出対象に登録</td></tr>
  <tr><td><code>Ctrl+F</code></td><td>検索バーを表示 / 非表示</td></tr>
  <tr><td><code>Ctrl+A</code></td><td>1回目で表示ページ、2回目で現在表示中の候補を全選択</td></tr>
  <tr><td><code>Ctrl+O</code> / <code>Ctrl+S</code></td><td>PDF を開く / 保存する</td></tr>
</table>
<h3>独自用語</h3>
<ul>
  <li><b>検出元（手動/追加/自動）</b>: 候補がどこから来たかを表します。手動は画面上で追加、追加は登録した検出対象、自動は通常の検出結果です。</li>
  <li><b>無視対象</b>: 今後の検出から外したい語を登録する機能です。</li>
  <li><b>追加検出対象</b>: 通常検出で拾いにくい語を追加ルールとして登録する機能です。</li>
  <li><b>重複削除</b>: 重なった候補を優先順位で整理する処理です。</li>
  <li><b>サイドカーJSON</b>: PDF と一緒に保存される補助ファイルで、編集結果やマッピング情報を保持します。</li>
  <li><b>保存</b>: 作業中の PDF とサイドカーJSON を更新します。<b>エクスポート</b> は別形式・別用途の出力を作ります。</li>
</ul>
<p>迷ったら対象のボタンや表にカーソルを置くかフォーカスを合わせて <code>F1</code> を押してください。説明待ちをやめたいときは <code>Esc</code> で解除できます。</p>
""",
    },
    "file": {
        "title": "ファイル操作",
        "body": """
<h3>対象</h3>
<p><b>開く</b>、<b>閉じる</b> を使って現在の PDF を切り替えます。</p>
<h3>ポイント</h3>
<ul>
  <li><b>開く</b> ではマッピング情報があれば自動で読み込みます。</li>
  <li><b>閉じる</b> や別ファイル切り替え時は、未保存変更があると確認ダイアログが出ます。</li>
  <li>PDF はドラッグ＆ドロップでも開けます。</li>
</ul>
<p>設定の変更や保存は別機能です。詳しくはそれぞれのボタン上で <code>F1</code> を押してください。</p>
""",
    },
    "settings": {
        "title": "設定",
        "body": """
<h3>対象</h3>
<p><b>設定</b> では検出対象、重複削除条件、テキスト前処理、OCR 設定を調整します。</p>
<h3>ポイント</h3>
<ul>
  <li>設定変更は自動保存されます。</li>
  <li><b>改行無視</b>、<b>空白無視</b> は検出精度に直接影響します。</li>
  <li><b>重複削除</b> の判定条件を変えると残る候補が変わります。</li>
</ul>
<p>設定ダイアログ内で <code>F1</code> を押すと部品ごとの説明待ちになり、<code>Esc</code> で解除できます。</p>
""",
    },
    "search": {
        "title": "検索",
        "body": """
<h3>対象</h3>
<p><b>検索</b> ボタンまたは <code>Ctrl+F</code> で検索バーを表示します。もう一度押すと閉じます。</p>
<h3>できること</h3>
<ul>
  <li><b>検索</b>: 入力した文字列そのままで全文検索します。</li>
  <li><b>前候補</b> / <b>次候補</b>: 一致候補を順に移動し、該当ページへジャンプします。</li>
  <li><b>追加</b>: 現在候補を手動追加します。</li>
  <li><b>全件追加</b>: 一致候補をまとめて追加し、種別は1回だけ選びます。</li>
</ul>
<p>検索バーを閉じると入力語は残し、候補とハイライトだけをクリアします。</p>
""",
    },
    "save": {
        "title": "保存",
        "body": """
<h3>保存とエクスポートの違い</h3>
<ul>
  <li><b>保存</b> は現在の PDF とサイドカーJSON を更新し、作業状態を引き継げるようにします。</li>
  <li><b>エクスポート</b> は配布・確認用の別出力を作成します。</li>
</ul>
<p>作業の続きが必要なときはまず保存、成果物を出したいときはエクスポートを使います。</p>
""",
    },
    "detect": {
        "title": "対象検出",
        "body": """
<h3>対象</h3>
<p><b>対象検出</b> は PII 候補を抽出します。</p>
<h3>メニュー</h3>
<ul>
  <li><b>表示ページ</b>: 今見ているページだけを検出します。</li>
  <li><b>全ページ</b>: すべてのページを検出します。ショートカットは <code>F5</code> です。</li>
</ul>
<p>設定ダイアログの検出対象や前処理設定が結果に反映されます。</p>
""",
    },
    "ocr": {
        "title": "OCR",
        "body": """
<h3>対象</h3>
<p><b>OCR</b> は NDLOCR-Lite を使って画像化された文字をテキスト化します。</p>
<h3>メニュー</h3>
<ul>
  <li><b>OCR実行</b>: 表示ページまたは全ページに OCR テキストを埋め込みます。</li>
  <li><b>OCRテキスト削除</b>: 追加済み OCR テキストを除去します。</li>
</ul>
<p>画像 PDF や文字抽出が弱い PDF で先に使うと、対象検出の結果が改善することがあります。</p>
""",
    },
    "target_delete": {
        "title": "対象削除",
        "body": """
<h3>対象</h3>
<p><b>対象削除</b> は自動検出された候補だけをまとめて削除します。</p>
<h3>ポイント</h3>
<ul>
  <li>手動追加や追加検出対象から来た候補は削除対象にしません。</li>
  <li>表示ページだけ消すか、全ページで消すかを選べます。</li>
</ul>
<p>ノイズ候補を一旦掃除したいときに使います。</p>
""",
    },
    "duplicate": {
        "title": "重複削除優先順位",
        "body": """
<h3>優先順位</h3>
<p>重複するエンティティがある場合、以下の順で残す候補を決めます。</p>
<p><b>検出元 (origin)</b> &gt; <b>包含 (contain)</b> &gt; <b>長さ (length)</b> &gt; <b>エンティティ種別 (entity)</b> &gt; <b>位置 (position)</b></p>
<h3>基準</h3>
<ul>
  <li><b>検出元</b>: 手動 &gt; 追加 = 自動</li>
  <li><b>包含</b>: より広い範囲を持つ候補を優先</li>
  <li><b>長さ</b>: より長い文字列を優先</li>
  <li><b>エンティティ種別</b>: 設定された種別順位を優先</li>
  <li><b>位置</b>: 入力順が先のものを優先</li>
</ul>
<p>追加検出と自動検出が重なった場合は追加検出側を残します。</p>
""",
    },
    "export": {
        "title": "エクスポート",
        "body": """
<h3>対象</h3>
<p><b>エクスポート</b> は用途別の成果物を作成します。</p>
<h3>出力形式</h3>
<ul>
  <li><b>アノテーション付き</b>: 注釈付き PDF を出力</li>
  <li><b>マスク</b>: マスク済み PDF を出力</li>
  <li><b>マスク（画像として保存）</b>: 画像化したマスク結果を出力</li>
  <li><b>マーク（画像として保存）</b>: ハイライト状態を画像で出力</li>
  <li><b>検出結果一覧（CSV）</b>: 候補一覧を表形式で出力</li>
</ul>
<p>作業状態を保持する保存とは別機能です。</p>
""",
    },
    "result_table": {
        "title": "検出結果テーブル",
        "body": """
<h3>できること</h3>
<ul>
  <li>候補の一覧表示、ソート、正規表現フィルタ</li>
  <li>削除、無視対象登録、追加検出対象登録</li>
  <li>ダブルクリックで種別編集</li>
</ul>
<h3>重要な用語</h3>
<ul>
  <li><b>検出元（手動/追加/自動）</b>: 候補の発生源です。</li>
  <li><b>無視対象</b>: 今後の検出から外す登録です。</li>
  <li><b>追加検出対象</b>: 今後の検出に追加する登録です。</li>
</ul>
<h3>ショートカット</h3>
<table border="1" cellspacing="0" cellpadding="4">
  <tr><th align="left">キー</th><th align="left">動作</th></tr>
  <tr><td><code>Delete</code></td><td>選択行を削除</td></tr>
  <tr><td><code>Backspace</code></td><td>選択語を無視対象に登録</td></tr>
  <tr><td><code>Insert</code></td><td>選択語を追加検出対象に登録</td></tr>
  <tr><td><code>Ctrl+A</code></td><td>1回目で表示ページ、2回目で現在表示中の候補を全選択</td></tr>
</table>
""",
    },
    "preview": {
        "title": "PDFプレビュー",
        "body": """
<h3>できること</h3>
<ul>
  <li>ページ移動、ズーム、Fit 表示</li>
  <li>候補ハイライトの確認</li>
  <li>文字列ドラッグ、長方形ドラッグ、円ドラッグによる選択</li>
</ul>
<h3>操作</h3>
<ul>
  <li><code>PgDown</code> / <code>PgUp</code> でページ移動できます。</li>
  <li><code>Home</code> / <code>End</code> で先頭・末尾ページへ移動できます。</li>
  <li><b>文字列ドラッグ</b> はテキスト範囲選択、<b>長方形ドラッグ</b> と <b>円ドラッグ</b> は図形指定向けです。</li>
  <li><code>Ctrl+A</code> は1回目で表示ページ、2回目で現在表示中の候補を選択します。</li>
</ul>
<p>プレビュー上の候補をクリックすると、対応する結果表の行にフォーカスします。</p>
""",
    },
    "log_panel": {
        "title": "ログウインドウ",
        "body": """
<h3>役割</h3>
<p>下部のログウインドウには、実行した処理、保存先、進捗、警告、エラー内容が時系列で表示されます。</p>
<h3>見方</h3>
<ul>
  <li>処理が終わったかどうかは最新行を見ると確認しやすいです。</li>
  <li><code>[xx%]</code> の形式は実行中タスクの進捗です。</li>
  <li>保存先や失敗理由もここに残るので、問題切り分けの起点になります。</li>
</ul>
""",
    },
    "status_bar": {
        "title": "ステータスウインドウ",
        "body": """
<h3>役割</h3>
<p>画面最下部のステータスウインドウには、現在の状態を一行で表示します。</p>
<h3>表示例</h3>
<ul>
  <li>準備完了</li>
  <li>選択中のPDF名やページ数</li>
  <li>保存やエクスポート完了の通知</li>
</ul>
<p>ログウインドウが詳細履歴、ステータスウインドウが現在状態の要約です。</p>
""",
    },
    "settings_entities": {
        "title": "設定: 検出対象",
        "body": """
<h3>対象</h3>
<p>検出対象のチェックボックスと <b>全選択</b> ボタンです。</p>
<h3>ポイント</h3>
<ul>
  <li>チェックを入れた種別だけを検出します。</li>
  <li><b>全選択</b> は全種別のON/OFFをまとめて切り替えます。</li>
  <li>設定変更は自動保存され、次回の対象検出に反映されます。</li>
</ul>
""",
    },
    "settings_model": {
        "title": "設定: spaCyモデル",
        "body": """
<h3>対象</h3>
<p><b>使用モデル</b> のコンボボックスです。</p>
<h3>ポイント</h3>
<ul>
  <li>検出に使う spaCy 日本語モデルを切り替えます。</li>
  <li>未インストールのモデルは選べません。</li>
  <li>モデル変更も自動保存されます。</li>
</ul>
""",
    },
    "settings_duplicate_entity_overlap": {
        "title": "設定: 対象重複判定",
        "body": """
<h3>対象</h3>
<p><b>異なる対象でも同一扱い</b> と <b>同じ対象のみ</b> のラジオボタンです。</p>
<h3>違い</h3>
<ul>
  <li><b>異なる対象でも同一扱い</b>: 種別が違っても位置が重なれば重複候補として扱います。</li>
  <li><b>同じ対象のみ</b>: 同じ種別どうしだけを重複候補として扱います。</li>
</ul>
""",
    },
    "settings_duplicate_overlap": {
        "title": "設定: 重複判定",
        "body": """
<h3>対象</h3>
<p><b>包含関係のみ</b> と <b>一部重なりも含む</b> のラジオボタンです。</p>
<h3>違い</h3>
<ul>
  <li><b>包含関係のみ</b>: 片方が完全にもう片方を含む場合だけ重複とみなします。</li>
  <li><b>一部重なりも含む</b>: 範囲が一部でも重なれば重複候補に含めます。</li>
</ul>
""",
    },
    "settings_text_preprocess": {
        "title": "設定: テキスト前処理",
        "body": """
<h3>対象</h3>
<p><b>改行無視</b> と <b>空白無視</b> のチェックボックスです。</p>
<h3>ポイント</h3>
<ul>
  <li><b>改行無視</b> を切るとブロック境界やページ境界に改行を残します。</li>
  <li><b>空白無視</b> を入れると空白文字を除去して比較します。</li>
  <li>どちらも検出結果の一致条件に直接影響します。</li>
</ul>
""",
    },
    "settings_ocr": {
        "title": "設定: OCR",
        "body": """
<h3>対象</h3>
<p>OCR 色、透明度、オフセット、OCR関連チェックボックスです。</p>
<h3>ポイント</h3>
<ul>
  <li><b>色を選択...</b>: 埋め込み文字色を指定します。</li>
  <li><b>透明度</b>: 埋め込みテキストの見え方を調整します。</li>
  <li><b>X/Yオフセット</b>: 埋め込み位置を微調整します。</li>
  <li><b>個人情報検出時にOCRを先行実行する</b>: Detect前にOCRを入れます。</li>
  <li><b>テキスト色を画像から自動検出</b>: 画像の文字色に寄せて埋め込みます。</li>
</ul>
""",
    },
    "settings_config_file": {
        "title": "設定: config.json",
        "body": """
<h3>対象</h3>
<p><b>config.json</b> ボタンです。</p>
<h3>役割</h3>
<ul>
  <li>現在の設定を保存してから、設定ファイルを既定アプリで開きます。</li>
  <li>手動編集後はダイアログがファイル変更を検知して再読込します。</li>
</ul>
""",
    },
    "settings_import_export": {
        "title": "設定: インポート/エクスポート",
        "body": """
<h3>対象</h3>
<p><b>インポート</b> と <b>エクスポート</b> ボタンです。</p>
<h3>役割</h3>
<ul>
  <li><b>インポート</b>: 別の JSON 設定を現在の設定へ読み込みます。</li>
  <li><b>エクスポート</b>: 現在の設定を JSON として保存します。</li>
</ul>
""",
    },
    "settings_close": {
        "title": "設定: 閉じる",
        "body": """
<h3>対象</h3>
<p>設定ダイアログの <b>閉じる</b> ボタンです。</p>
<h3>ポイント</h3>
<ul>
  <li>設定は自動保存済みなので、閉じても内容は保持されます。</li>
  <li><code>F1</code> の説明待ち中は <code>Esc</code> で説明待ちだけを解除できます。</li>
</ul>
""",
    },
    "help": {
        "title": "ヘルプの使い方",
        "body": """
<h3>部品説明</h3>
<p><code>F1</code> を押すと説明待ちになります。次の左クリックで、クリックしたボタンや部品の説明を開きます。</p>
<p><code>Esc</code> を押すと説明待ちを中止し、<code>?</code> カーソルも解除します。</p>
<p>説明対象がない場所をクリックした場合は、何も表示せずに終了します。</p>
<h3>ヘルプメニュー</h3>
<ul>
  <li><b>部品をクリックして説明 (F1)</b>: 説明したい部品を左クリックで選びます</li>
  <li><b>重複削除優先順位</b>: 重複整理のルールだけ確認する</li>
</ul>
""",
    },
}


def get_help_topic(topic_id: str) -> Dict[str, str]:
    """指定トピックを返し、不明なIDはヘルプの使い方へフォールバックする"""
    return HELP_TOPICS.get(topic_id, HELP_TOPICS["help"])


class HelpDialog(QDialog):
    """スクロール可能なヘルプダイアログ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.resize(760, 560)

        layout = QVBoxLayout(self)

        self.title_label = QLabel(self)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(self.title_label)

        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def show_topic(self, topic_id: str):
        """トピックに応じてタイトルと本文を更新する"""
        topic = get_help_topic(topic_id)
        self.setWindowTitle(f"ヘルプ - {topic['title']}")
        self.title_label.setText(topic["title"])
        self.browser.setHtml(topic["body"])
        self.browser.verticalScrollBar().setValue(0)
