PDF内個人情報テキストの精密座標特定モジュール：実装指示書
1. 目的
Presidio Analyzerによって検出された個人情報（PII）文字列について、PDF文書内での正確な位置（矩形座標）を特定する。本モジュールは、PIIが複数行にまたがる場合や、PDF内部の単語分割が不規則な場合でも、高精度な座標特定を実現することを目的とする。

2. 実装方針
既存のPDFPresidioProcessorクラスとは独立した、座標特定ロジック専門のPDFTextLocatorクラスを新規に作成する。これにより、関心を分離し、コードの保守性と再利用性を向上させる。

3. クラス設計 (PDFTextLocator)

Python

import fitz # PyMuPDF

class PDFTextLocator:
    """
    PDF文書内の特定テキストの精密な座標を特定するためのクラス。
    """
    def __init__(self, pdf_doc: fitz.Document):
        """
        コンストラクタ。処理済みのfitz.Documentオブジェクトを受け取り、
        座標特定に必要な全テキスト行の情報を準備する。

        Args:
            pdf_doc (fitz.Document): 座標を特定する対象のPDFドキュメントオブジェクト。
        """
        self.doc = pdf_doc
        # 【要件①, ③】ラインデータリストを作成
        self.line_data = self._prepare_line_data()

    def _prepare_line_data(self) -> list[dict]:
        """
        PDF内の全ページから全てのテキスト行を抽出し、
        ページ番号、座標、テキストを含む辞書のリストを作成する。
        """
        # ... 実装詳細は下記 ...

    def locate_pii(self, pii_text: str) -> list[fitz.Rect]:
        """
        単一のPII文字列を受け取り、そのテキストが存在する全ての精密な矩形座標の
        リストを返す。複数行にまたがる場合は、各行の矩形をすべて返す。

        Args:
            pii_text (str): 探すべき個人情報文字列（改行`\n`を含む場合もある）。

        Returns:
            list[fitz.Rect]: 見つかった部分に対応するfitz.Rectオブジェクトのリスト。
                             見つからない場合は空リストを返す。
        """
        # ... 実装詳細は下記 ...
4. 各メソッドの実装詳細

4.1. _prepare_line_data メソッド (要件 ①, ③)
目的: PDF内の全テキスト行の情報を「ページ番号、座標、テキスト」の形式でリスト化する。
手順:
空のリスト all_lines = [] を用意する。
self.doc の全ページをループする (for page in self.doc:).
各ページで page.get_text('dict') を呼び出し、構造化データを取得する。
ブロック、ラインの階層でループし、各ラインの bbox（矩形座標）と、スパンを結合した text を取得する。
all_lines リストに {'page_num': page.number, 'rect': fitz.Rect(line['bbox']), 'text': line_text} の形式で辞書を追加する。
完成した all_lines リストを返す。
4.2. locate_pii メソッド (要件 ②, ④, ⑤, ⑥)
目的: PII文字列を受け取り、検証を経て、最終的な精密座標リストを返す主幹メソッド。
手順:
PIIパーツ分割 (要件②の一部):

pii_parts = pii_text.split('\n') のように、入力されたPIIテキストを改行でパーツに分割する。
候補ラインの検索 (要件④):

self.line_data を走査し、各 pii_parts の各パーツが、どのライン（インデックス）のテキストに含まれるかを検索する。
結果を {'パーツ1': [候補インデックス1, ...], 'パーツ2': [候補インデックス2, ...]} のような辞書にまとめる。
候補ラインの検証 (要件⑤):

pii_parts の数だけ連続するインデックスの組み合わせを候補から探す。
(例: pii_parts が2つの場合、idx がパーツ1の候補にあり、かつ idx + 1 がパーツ2の候補にある組み合わせを探す)
見つかった連続インデックスの組み合わせ ([idx, idx+1, ...]) について、対応するラインのテキストを \n で連結し、その中に元の pii_text が完全に含まれるかを確認する。
検証に成功した最初の連続インデックスリスト validated_indices を採用する。候補がなければ空リストを返す。
精密座標の特定 (要件⑥):

検証済みの validated_indices を使って、精密な座標を特定する。
空のリスト precise_rects = [] を用意する。
validated_indices の各インデックス (line_idx) についてループする: a. line_info = self.line_data[line_idx] から、ページ番号 page_num と行全体の矩形 line_rect を取得する。 b. page = self.doc[page_num] でページオブジェクトを取得する。 c. page.search_for(pii_text, clip=line_rect) を実行する。 - これにより、検索範囲が line_rect（特定の1行）に限定され、その行に含まれる pii_text の部分だけの正確な矩形が返される。 d. 返された fitz.Rect のリストを precise_rects に追加（extend）する。
最終的に precise_rects リストを返す。

5. 既存コード (PDFPresidioProcessor) との連携

PDFPresidioProcessor の analyze_pdf メソッド内、またはそれに類する場所で PDFTextLocator をインスタンス化する。
Python

# pdf_data = self.extract_pdf_text(pdf_path) の後
locator = PDFTextLocator(pdf_data['document'])
PresidioがPIIを検出した後、既存の _calculate_text_coordinates の代わりに、新しいロケーターを呼び出す。
Python

# for result in results: ループの中
pii_text = result['text']
# 既存の座標計算を置き換える
# result['coordinates'] = self._calculate_text_coordinates(...)
result['line_rects'] = locator.locate_pii(pii_text)

# マスキング処理では result['line_rects'] を使うように修正
# (例: 最初の矩形を代表座標とする、または全矩形をハイライトする)
if result['line_rects']:
    # 代表座標として最初の矩形を使用
    main_rect = result['line_rects'][0]
    result['coordinates'] = {'x0': main_rect.x0, 'y0': main_rect.y0, 'x1': main_rect.x1, 'y1': main_rect.y1}
6. 期待される成果

locator.locate_pii("改行\nされたテキスト") の呼び出しにより、[<1行目の矩形>, <2行目の矩形>] のような fitz.Rect のリストが返却される。
これにより、複数行にまたがるエンティティの各行を正確にハイライト表示することが可能になる。
既存のロジックが、より堅牢で高精度な座標特定機能に置き換えられる。