PDF内個人情報テキストの精密座標特定モジュール (文字情報版)：実装指示書
1. 目的
rawdictから得られる文字ごとの精密な座標情報を基盤とし、Presidioが検出した個人情報（PII）文字列の、PDF文書内における正確な矩形座標を算出する。本モジュールは、PII検出用のプレーンテキストとPDFの文字構造を完全に同期させることで、検索処理を介さずに直接座標を特定する。

2. 実装方針
座標特定ロジックをカプセル化したPDFTextLocatorクラスを新規に作成する。このクラスは初期化時にPDFの全文字情報を解析・保持し、PIIの文字オフセットから直接座標を計算する責務を持つ。

3. クラス設計 (PDFTextLocator)

Python

import fitz # PyMuPDF

class PDFTextLocator:
    """
    PDF文書の文字レベル情報と、PII検出用のプレーンテキストを同期させ、
    テキストオフセットから直接、精密な座標を算出するクラス。
    """
    def __init__(self, pdf_doc: fitz.Document):
        """
        コンストラクタ。fitz.Documentオブジェクトを受け取り、
        PII検出用の「フルテキスト」と、文字ごとの「キャラクターデータリスト」を準備する。

        Args:
            pdf_doc (fitz.Document): 対象のPDFドキュメントオブジェクト。
        """
        self.doc = pdf_doc
        # 【要件①, ③改】フルテキストと文字データリストを生成・同期
        self.full_text, self.char_data = self._prepare_synced_data()

    def _prepare_synced_data(self) -> tuple[str, list[dict]]:
        """
        `page.get_text("rawdict")`を使い、PDFの全文字情報を抽出。
        PII検出用テキストと文字情報リストを完全に同期させた状態で生成する。
        """
        # ... 実装詳細は下記 ...

    def locate_pii_by_offset(self, start: int, end: int) -> list[fitz.Rect]:
        """
        【要件④, ⑤, ⑥改】フルテキストにおける文字の開始・終了オフセットを受け取り、
        対応するキャラクターデータの矩形を結合して、最終的な座標リストを返す。

        Args:
            start (int): フルテキストにおけるPIIの開始文字インデックス。
            end (int): フルテキストにおけるPIIの終了文字インデックス。

        Returns:
            list[fitz.Rect]: PIIの各行を囲むfitz.Rectオブジェクトのリスト。
        """
        # ... 実装詳細は下記 ...
4. 各メソッドの実装詳細

4.1. _prepare_synced_data メソッド (要件①, ③改)
目的: 後のオフセットによる直接マッピングを可能にするため、full_textとchar_dataの二つのデータを一文字もずれることなく完璧に同期させる。
手順:
空のリスト char_data = [] と text_parts = [] を用意する。
self.doc の全ページをループし、各ページで page.get_text("rawdict") を呼び出す。
ブロック、ライン、スパン、**chars**の階層で深くループする。
各**char**辞書について： a. text_parts.append(char['c']) のように文字をリストに追加する。 b. char_data リストに、この文字の詳細情報辞書を追加する。
Python

{
    'char': char['c'],
    'rect': fitz.Rect(char['bbox']),
    'page_num': page.number,
    'line_num': line_num, # 識別のための行番号
    'block_num': block_num # 識別のためのブロック番号
}
【重要】空白（スペース）の処理: rawdictは明示的なスペース文字を含まない。単語間のスペースをfull_textに再現し、char_dataとの同期を保つ必要がある。
推奨案: スパンとスパンの間、または単語と単語の間に一定の水平距離があれば、text_partsにスペース' 'を追加し、char_dataにも対応する「空白情報」の辞書（矩形は推定値）を追加する。この処理の精度が、システム全体の成否を分ける。
ページ間やブロック間にも必要に応じて改行 \n を text_parts に挿入し、char_data にも対応する情報を追加する。
最終的に full_text = "".join(text_parts) でフルテキストを生成し、full_text と char_data をタプルで返す。
4.2. locate_pii_by_offset メソッド (要件④, ⑤, ⑥改)
目的: 検索処理を一切行わず、文字オフセットを用いて座標を直接計算する。
手順:
対象キャラクターの切り出し:

target_chars = self.char_data[start:end]
引数のstart, endオフセットを使って、char_dataリストから対象となる文字情報のスライスを直接取得する。full_textとchar_dataが同期しているため、これが可能になる。
行ごとの矩形結合:

空の辞書 lines = {} を用意する。
target_chars リストをループし、各文字のpage_numとline_numをキーとして、その文字の矩形rectを辞書にグルーピングしていく。
(例: lines[(char['page_num'], char['line_num'])].append(char['rect']))
最終的な矩形リストの生成:

空のリスト final_rects = [] を用意する。
lines 辞書の各値（＝同じ行にある矩形のリスト）をループする。
各リスト内の全矩形を + 演算子で結合し、その行のPII部分を囲む一つの fitz.Rect を作成する。
作成した矩形を final_rects に追加する。
final_rects を返す。これには、複数行にまたがるPIIの各行部分に対応する、精密な矩形オブジェクトが格納されている。

5. 既存コード (PDFPresidioProcessor) との連携

PDFPresidioProcessor の初期化時に PDFTextLocator をインスタンス化する。 self.locator = PDFTextLocator(self.doc_object)
Presidioに渡すテキストは、必ず self.locator.full_text を使用する。
Presidioの解析結果 results をループ処理する際：
Python

# for result in results: ループの中
# result には start と end のオフセットが含まれている
start_offset = result.start
end_offset = result.end

# 新しいメソッドを呼び出し、オフセットから直接座標リストを取得
precise_rects = self.locator.locate_pii_by_offset(start_offset, end_offset)

# 取得した座標リストを後続のマスキング処理で使用する
result['line_rects'] = precise_rects 
6. 期待される成果

search_forに依存しない、純粋な座標計算による極めて精密なハイライトが実現される。
処理のボトルネックであった「PIIとPDFテキストのマッピング」問題が、_prepare_synced_dataメソッドにおける「同期データ作成」という初期投資に集約される。
この初期処理さえ正確に実装できれば、座標特定は非常に高速かつ正確になる。