src/cli/cli.pyについて、argumentについて、整理できるかまずは検討せよ

思考時間: 45s


ChatGPT:
結論: 整理できる。現状は1コマンドに「マスク」「読み取り」「復元」「エクスポート」のモード系オプションが混在し、衝突と学習コストが高い。主な引数は以下の通り。path と共通系（--config/-c, --verbose/-v, --output-dir/-o）に加え、モード系（--read-mode, --restore-mode, --export-mode）、マスキング系（--masking-method, --masking-text-mode, --operation-mode）、NLP（--spacy-model）、重複除去（--deduplication-mode, --deduplication-overlap-mode）、エクスポート付随（--json-out, --pretty, --text-variant, --include-text）、検出ルール（--exclude-re, --add）。








--export-modeの意味は3択（1=highlight_pdf, 2=pdf_pii_coords, 3=text_pii_offsets）。

提案（最小変更で明確化）

サブコマンド化: mask, read, restore, export coords, export offsets。--export-modeは非推奨にし各サブコマンドへ移行。

共通オプションは共通親に集約: --config, --verbose, --output-dir, --spacy-model。


mask専用: --masking-method, --masking-text-mode, --operation-mode。

read専用: --read-report。--read-modeはサブコマンド化で不要。

restore専用: --report-file。--restore-modeはサブコマンド化で不要。

export coords専用: --json-out, --pretty。

export offsets専用: さらに--text-variant, --include-textも有効。


重複除去系はmaskとexport offsetsのみに露出。

相互排他の明示: 旧フラグ併用（例: --read-modeと--restore-mode）はエラーにする。現在は混在可能な形。

設定反映の一貫性: CLI→ConfigManagerのマージは既存ロジックを踏襲。YAML優先度や引数→設定マップは現状維持。


移行計画

1リリースは旧オプションを警告付きで受理。その後削除。

ドキュメントはサブコマンド別に再構成。--export-modeの使用例は置換。

次のステップ

上記方針でCLIシグネチャ案とclick.Groupパッチを提示可能。


情報源







あなた:
サブコマンドってわからない。もう少しわかりやすく教えて


ChatGPT:
要点: サブコマンドは「プログラム名の直後に置く動詞」。用途ごとに入口を分ける仕組み。
書式: prog <subcommand> [そのサブコマンド専用のオプション] [引数]

なぜ使うか

目的が明確になる。例: mask と restore を同時に指定できない。

ヘルプが分割される。各モードの引数が混ざらない。

シェル補完とエラーメッセージが素直になる。

イメージ（Before → After）

Before: cli.py --read-mode --report-file report.json --output-dir out

After: cli.py read --report-file report.json --output-dir out

Before: cli.py --export-mode coords --json-out

After: cli.py export coords --json-out

Before: cli.py --masking-method box --deduplication-mode line

After: cli.py mask --method box --deduplication line

最小コード例（Python, click）

python
コピーする
編集する
import click

@click.group()
def cli():
    pass

@cli.command(help="PIIをマスクする")
@click.argument("path")
@click.option("--method", type=click.Choice(["box","blur"]))
@click.option("--deduplication", type=click.Choice(["none","line","page"]))
def mask(path, method, deduplication):
    ...

@cli.command(help="検出結果を読む")
@click.option("--report-file", type=click.Path(exists=True), required=True)
def read(report_file):
    ...

@cli.command(help="マスク前を復元する")
@click.option("--report-file", type=click.Path(exists=True), required=True)
def restore(report_file):
    ...

@cli.group(help="エクスポートする")
def export():
    pass

@export.command(name="coords", help="PDF座標をJSONで出力")
@click.option("--json-out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def export_coords(json_out, pretty):
    ...

@export.command(name="offsets", help="テキストオフセットを出力")
@click.option("--text-variant", type=click.Choice(["orig","norm"]))
@click.option("--include-text", is_flag=True, default=False)
def export_offsets(text_variant, include_text):
    ...

if __name__ == "__main__":
    cli()
使い方の覚え方

まず cli.py --help でサブコマンドの一覧だけ見る。

次に cli.py <subcommand> --help でそのモードの引数だけ見る。

進め方

既存の「モード系」フラグをサブコマンドへ移す。

共通フラグ（例: --output-dir, --verbose）は @cli.group() に残す。

旧フラグは互換のため受け付けつつ警告を出す。








あなた:
以下の機能に再編しようと思う。自明なoptionは指定しなかったが、その辺はもとのを基本的に引き継ぐ方向で。そもそもコード自体を分割して、共通ロジックはそれはそれで切り出そう。
以下を見て、必要な修正や意見をください。問題なければcodex cli用の変更方針を作ってください

１　read　pdfを読み込んで、①ハイライトを読み込む、②テキスト（構造なし）を読み込む、③テキスト（構造あり）を読み込む。①②③はそれぞれONOFFできる。出力はJSON（{"hilight":{...},"plane_text":"......","structured_text": {...}})みたいなイメージ。指定がなければ標準出力、ファイル指定(argument)があればそれに書き出す。pretty argumentあり。①②③のONOFFはargument。JSONにはPDFファイルの概要を含むといいと思う。hashとかも
２　 detect　plane_text又は（及び）structured_textを含んだJSONを読み、マスク情報をJSONとして出力する。出力についてはPII検出情報であり、plane_textであれば、検出単語、エンティティ種類、オフセット、検出したモデル又は追加エンティティ又は手動追加の別、structured_textであれば、検出単語、エンティティ種類、座標（段が変わることを考えると[[x0,y0,x1,y1],[x0,y0,x1,y1],....]）、検出したモデル又は追加エンティティ又は手動追加の別。出力は指定がなければ標準出力、あればファイル。pretty argumentあり。JSONには１から引き継いだPDFファイルの概要を含むといいと思う。plane_text又は（及び）structured_textを含んだJSONに１のhighlight情報があれば、それに追加する形がいいと思う。
３　mask　pdfとPII検出情報を統合して、maskする。maskの方法はハイライトに注釈情報（エンティティの種類と検出単語と検出したモデル又は追加エンティティ又は手動追加の別）を行う。pdfのhash値とPII検出情報のhash値が違ったらエラーで追加できないものとするが、forceオプションがあれば別。出力はハイライト注釈情報が追加されたpdf
４　duplicate_process　PII検出情報を読んで、デフォルト及びargumentで指定した優先順位でPIIの重複を処理していく。基本は既存の重複処理を引き継ぐ


ChatGPT:

思考時間: 43s
「# h1」を使った箇条書きのヘッダーについて考えているけど、このスタイルではマークダウンセクションは避けるべきとのこと。なので、最小限のリストを使用してみる。タイムゾーンや重複処理の名前も見直しを提案。「hilight」ではなく「highlight」の表記が適切。提案される修正点は、「重複処理」を「dedupe」と命名することなど。

出力方法として、位置指定を許可する (--out) の導入を提案。PDF概要には "source" オブジェクトを含め、ファイル名やハッシュ値、ページ数などを記録。ページごとのSHA256ハッシュも選択肢として追加を検討。テキスト抽出方法は、既存のパイプラインを使い、PDFユーザー単位のポイント座標記録を提案。

ハイライト配列を持ち越し、「pii」のサブ配列追加を提案。オフセットはUTF-16で、デフォルトでは「codepoint」を指定。構造化された検出の際、複数の四角形バウンディングボックスを維持。検出ハッシュは標準化された入力JSONで計算し、PDFハッシュも含めます。

PDFへの注釈埋め込みは、ハイライトとして「ENTITY: value [source=model/manual/add]」などを記載しますが、コンプライアンス上必要な場合は値を漏らさないようにします。また、重複アノテーション処理を避け、データの統合を行います。旧オプションを受け入れるラッパーも用意し、CLI仕様も整理します。

完了
前提OK。再編は妥当。修正点と補足を提示し、その後にCLI変更方針を示す。

修正と意見

命名の統一: plane_text → plain_text。hilight → highlight。キーは全てsnake_case。

版管理: すべてのJSONに schema_version と generated_at を持たせる。

出自の明示: source を統一して持つ。{ filename, path, size, page_count, sha256, created_at, modified_at }

ハッシュの扱い: PDFは sha256(file_bytes)。read_json_sha256 も別途保存。detect のJSONは入力JSONとモデル設定を正規化して detect_json_sha256 を計算。mask は pdf.sha256 と detect.source.pdf.sha256 を検証。--force で無効化可。

出力先指定: すべて stdout 既定。--out FILE で上書き。引数でファイル名を取るより --out の方が一貫。

文字オフセット単位: plain_text の offsets は Unicode コードポイント基準に固定。unit:"codepoint" を明記。要件があれば --offset-unit byte|utf16|codepoint を許可。

座標系: structured_text と検出クアッドは PDF ユーザ単位（ポイント）に固定。page, rotation, mediabox, dpi を source.pages[] に保持。正規化座標にしたい場合は --norm-coords を追加。

ハイライトのI/O: 既存ハイライトは read で highlights[] として読み取り。detect は highlights を温存し highlights[i].pii[] を追加する形で拡張。mask は新規アノテーションを追加するが、同一 detection_id の重複追加は避ける。

検出結果の起源: origin:"model"|"added"|"manual" と model_id と confidence(任意) を各検出に付与。

衝突回避: duplicate_process の優先順位は既定で manual > added > model。次に span_length desc。最後に entity_priority（例: SSN > PHONE > PERSON のように設定可能）。--policy FILE で上書き可。

セキュリティ配慮: mask で注釈本文に生テキストを入れるかは --label-only で制御。既定は生テキストを含めない方が無難。

終了コード: 正常0。整合性不一致1。入力不備2。内部例外>10。

将来拡張余地: 実赤塗りは別サブコマンド redact として後日追加可能。

JSONスキーマ案（要点のみ）

read 出力

json
コピーする
編集する
{
  "schema_version":"1.0",
  "generated_at":"2025-08-11T00:00:00Z",
  "source":{
    "filename":"doc.pdf","path":"/abs/doc.pdf","size":12345,
    "page_count":10,"sha256":"…","created_at":"…","modified_at":"…"
  },
  "content":{
    "highlight":[{"page":1,"quads":[[x0,y0,x1,y1],…],"comment":null,"id":"h1"}],
    "plain_text":"…",
    "structured_text":{
      "pages":[
        {"page":1,"blocks":[{"lines":[{"spans":[{"text":"…","bbox":[x0,y0,x1,y1],"span_id":"s1"}]}]}]}
      ]
    }
  }
}
detect 出力

json
コピーする
編集する
{
  "schema_version":"1.0",
  "generated_at":"…",
  "source":{
    "pdf": {"sha256":"…"},
    "read_json_sha256":"…"
  },
  "detections":{
    "plain":[
      {"text":"John","entity":"PERSON","start":123,"end":127,"unit":"codepoint","origin":"model","model_id":"spacy_x","detection_id":"d1"}
    ],
    "structured":[
      {"text":"090…","entity":"PHONE","page":3,"quads":[[x0,y0,x1,y1]],"origin":"manual","detection_id":"d2"}
    ]
  },
  "highlights":[{"id":"h1","pii":["d2"]}]
}
サブコマンド仕様（codex CLI 変更方針）

共通: --out FILE --pretty --quiet --verbose --config FILE

read

使い方: cli read <PDF> [--with-highlights/--no-highlights] [--with-plain/--no-plain] [--with-structured/--no-structured] [--norm-coords]

既定: 全てON

出力: 上記read JSON

detect

使い方: cli detect [--from FILE|--from-stdin] [--use-plain] [--use-structured] [--model MODEL_ID ...] [--add-entities FILE]

既定: 両方あれば両方使う

出力: 上記detect JSON。--append-highlights 既定ON

mask

使い方: cli mask <PDF> --detect FILE [--force] [--label-only]

検証: PDF.sha256 == detect.source.pdf.sha256 不一致はエラー。--force で続行

出力: 注釈付きPDF

duplicate_process

使い方: cli duplicate-process --detect FILE [--policy FILE] [--entity-priority "SSN,PHONE,EMAIL"] [--keep origin|longest|highest-priority]

出力: 正規化後のdetect JSON（同一フォーマット）。detections.* を置換

データ整合ルール

detection_id は hash(entity, text, page/quads or offsets) で決定的に生成。重複判定と追跡に使用。

highlights[].pii[] は detection_id の配列。実体は detections にのみ保持。

旧CLIからの移行

旧モード系フラグは非推奨で受理。内部で新サブコマンドへディスパッチ。1リリース後に削除。

旧 --export-mode は read と detect の分離に伴い廃止。座標やオフセットは detect の結果として提供。

旧重複オプションは duplicate-process に移設。名称は短縮しても良いなら dedupe を別名として提供。

実装メモ

click 構成: @click.group() に共通オプション。read|detect|mask|duplicate_process をサブコマンド。detect は stdin サポート。

モジュール分割: pdfio/(読み書き) nlp/(検出) schema/(pydantic) ops/(dedupe, validate) cli/。

例外とメッセージ: 整合性不一致は具体的に何が不一致かを表示。--verbose でスタック出力。

テスト: ゴールデンJSONで schema_version とハッシュ計算の安定性をCI確認。

この方針で問題なければ、click ベースの雛形とスキーマのpydanticモデルを提示する。








あなた:
この方針で問題なし


ChatGPT:
承認了解。以下をそのまま実装方針に使える形で提示する。

変更方針（codex CLI）
サーフェス（最終仕様）
codex read <PDF> [--with-highlights/--no-highlights] [--with-plain/--no-plain] [--with-structured/--no-structured] [--norm-coords] [--out FILE] [--pretty]

codex detect [--from FILE|--from-stdin] [--use-plain] [--use-structured] [--model MODEL_ID ...] [--add-entities FILE] [--out FILE] [--pretty] [--append-highlights/--no-append-highlights]

codex mask <PDF> --detect FILE [--force] [--label-only] [--out FILE]

codex duplicate-process --detect FILE [--policy FILE] [--entity-priority "SSN,PHONE,EMAIL"] [--keep origin|longest|highest-priority] [--out FILE] [--pretty]

共通: --verbose/-v --quiet --config FILE

互換・非推奨
旧モード系フラグは受理して警告表示。内部で上記サブコマンドにディスパッチ。

旧 --export-mode は廃止予定。現行リリースでは detect の出力へ案内。

次期メジャーで削除。警告文言に削除予定を記載。

JSONスキーマ（要点）
共通ヘッダ:

json
コピーする
編集する
{ "schema_version":"1.0","generated_at":"<RFC3339>","source":{ "filename":"...", "path":"...", "size":0, "page_count":0, "sha256":"...", "created_at":"...", "modified_at":"..." } }
read 出力:

json
コピーする
編集する
{ "...": "...",
  "content":{
    "highlights":[{"id":"h1","page":1,"quads":[[x0,y0,x1,y1]],"comment":null}],
    "plain_text":"...",
    "structured_text":{"pages":[{"page":1,"blocks":[{"lines":[{"spans":[{"span_id":"s1","text":"...","bbox":[x0,y0,x1,y1]}]}]}]}]}
  }
}
detect 出力:

json
コピーする
編集する
{ "...":"...",
  "source":{"pdf":{"sha256":"..."}, "read_json_sha256":"...", "model_config_sha256":"..."},
  "detections":{
    "plain":[{"detection_id":"d1","text":"John","entity":"PERSON","start":123,"end":127,"unit":"codepoint","origin":"model","model_id":"spacy_x","confidence":0.93}],
    "structured":[{"detection_id":"d2","text":"090...","entity":"PHONE","page":3,"quads":[[x0,y0,x1,y1]],"origin":"manual"}]
  },
  "highlights":[{"id":"h1","pii":["d2"]}]
}
duplicate-process 後も detect と同一フォーマットで返却。

エラーと整合性
終了コード: OK=0, 整合性不一致=1, 入力不備=2, 例外=10+

mask: pdf.sha256 != detect.source.pdf.sha256 は1。--force で警告の上続行。

オフセット単位は既定 codepoint。detect 出力に unit 明記。

座標はPDFユーザ単位（pt）。正規化は --norm-coords。

実装分割（PR順）
基盤: パッケージ分割

graphql
コピーする
編集する
codex/
  cli/
    __init__.py
    main.py
  pdfio/     # PDF読取/注釈
  nlp/       # 検出パイプライン
  schema/    # pydanticモデル
  ops/       # 重複処理・整合性検証・ハッシュ
schema追加: pydantic

python
コピーする
編集する
# schema/models.py
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Tuple, Dict

Quad = Tuple[float,float,float,float]

class Source(BaseModel):
    filename:str; path:str; size:int; page_count:int
    sha256:str; created_at:str; modified_at:str

class ReadContent(BaseModel):
    highlights: List[Dict] = []
    plain_text: Optional[str] = None
    structured_text: Optional[Dict] = None

class ReadDoc(BaseModel):
    schema_version: str = "1.0"
    generated_at: str
    source: Source
    content: ReadContent

class DetectionPlain(BaseModel):
    detection_id:str; text:str; entity:str
    start:int; end:int; unit:Literal["codepoint","utf16","byte"]="codepoint"
    origin:Literal["model","added","manual"]; model_id: Optional[str]=None
    confidence: Optional[float]=None

class DetectionStructured(BaseModel):
    detection_id:str; text:str; entity:str
    page:int; quads: List[Quad]
    origin:Literal["model","added","manual"]; model_id: Optional[str]=None
    confidence: Optional[float]=None

class DetectDoc(BaseModel):
    schema_version:str="1.0"
    generated_at:str
    source: Dict
    detections: Dict[str, List]  # {"plain":[...], "structured":[...]}
    highlights: List[Dict] = []
CLI雛形: click

python
コピーする
編集する
# cli/main.py
import click

@click.group()
@click.option("--verbose", "-v", count=True)
@click.option("--quiet", is_flag=True, default=False)
@click.option("--config", type=click.Path(exists=True))
def cli(verbose, quiet, config): pass

@cli.command("read")
@click.argument("pdf", type=click.Path(exists=True))
@click.option("--with-highlights/--no-highlights", default=True)
@click.option("--with-plain/--no-plain", default=True)
@click.option("--with-structured/--no-structured", default=True)
@click.option("--norm-coords", is_flag=True, default=False)
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def read_cmd(**kw): ...  # pdfio.read → schema.ReadDoc → dump

@cli.command("detect")
@click.option("--from", "src", type=click.Path(), help="read JSON file; omit to use stdin")
@click.option("--from-stdin", is_flag=True, default=False)
@click.option("--use-plain", is_flag=True)
@click.option("--use-structured", is_flag=True)
@click.option("--model", multiple=True)
@click.option("--add-entities", type=click.Path(exists=True))
@click.option("--append-highlights/--no-append-highlights", default=True)
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def detect_cmd(**kw): ...  # nlp.pipeline → schema.DetectDoc

@cli.command("mask")
@click.argument("pdf", type=click.Path(exists=True))
@click.option("--detect", "detect_file", type=click.Path(exists=True), required=True)
@click.option("--force", is_flag=True, default=False)
@click.option("--label-only", is_flag=True, default=False)
@click.option("--out", type=click.Path())
def mask_cmd(**kw): ...  # ops.validate_hash → pdfio.annotate

@cli.command("duplicate-process")
@click.option("--detect", "detect_file", type=click.Path(exists=True), required=True)
@click.option("--policy", type=click.Path(exists=True))
@click.option("--entity-priority", type=str)
@click.option("--keep", type=click.Choice(["origin","longest","highest-priority"]), default="origin")
@click.option("--out", type=click.Path())
@click.option("--pretty", is_flag=True, default=False)
def dedupe_cmd(**kw): ...  # ops.dedupe
ハッシュ・整合性

python
コピーする
編集する
# ops/hash.py
import hashlib, json
def sha256_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha256_json(obj)->str: return sha256_bytes(json.dumps(obj, separators=(",",":"), ensure_ascii=False).encode("utf-8"))
重複処理ポリシ

既定: manual > added > model → 長いspan優先 → entity_priority。

--policy FILE で上書き（YAML/JSON）。キー: origin_order, entity_priority, tie_breaker.

互換層

旧フラグを受理するラッパを cli/compat.py に置く。使用時は DeprecationWarning とマッピング案内を標準エラーへ出力。

テスト

ゴールデンJSONでスナップショット。schema_version とハッシュ安定性を検証。

PDFダミーで read→detect→duplicate-process→mask の往復をCIで回す。

不一致ケースで終了コード1を確認。

例コマンド
読み込み:

codex read doc.pdf --out read.json --pretty

検出:

codex detect --from read.json --model spacy_xxl --out detect.json --pretty

重複処理:

codex duplicate-process --detect detect.json --entity-priority "SSN,PHONE,EMAIL" --out detect_dedup.json

マスク注釈:

codex mask doc.pdf --detect detect_dedup.json --out doc_annotated.pdf

この構成で着手可。必要なら最初のPRテンプレートも用意する。