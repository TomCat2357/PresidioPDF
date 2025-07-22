# PyMuPDF 活用パターン・最適化ガイド

## 概要
PresidioPDF プロジェクトにおける PyMuPDF ライブラリの効率的な活用方法、最適化技法、高度な PDF 処理パターンを定義する。テキスト抽出、座標計算、レンダリング、メモリ管理の各領域で最適化されたパターンを提供する。

## PyMuPDF アーキテクチャ理解

### 主要コンポーネント
```python
# PyMuPDF 主要クラス構造
"""
Document (fitz.Document)
├── Pages (fitz.Page) 
│   ├── Text Extraction
│   ├── Coordinate Systems
│   ├── Drawing/Rendering
│   └── Annotations
├── Metadata
├── Links & Bookmarks
└── Security/Encryption
"""

# 基本オブジェクト階層
import fitz  # PyMuPDF

class PyMuPDFHandler:
    """PyMuPDF 基本ハンドリングクラス"""
    
    def __init__(self):
        self.document = None
        self.current_page = None
        
    def open_document(self, file_path: str) -> fitz.Document:
        """ドキュメント開放"""
        try:
            self.document = fitz.open(file_path)
            return self.document
        except Exception as e:
            raise PDFHandlingError(f"Failed to open PDF: {e}")
    
    def get_document_info(self) -> Dict[str, Any]:
        """ドキュメント情報取得"""
        if not self.document:
            raise ValueError("Document not loaded")
            
        return {
            "page_count": self.document.page_count,
            "metadata": self.document.metadata,
            "is_encrypted": self.document.needs_pass,
            "is_pdf": self.document.is_pdf,
            "file_size": len(self.document.tobytes()) if hasattr(self.document, 'tobytes') else None,
            "permissions": self._get_permissions()
        }
    
    def _get_permissions(self) -> Dict[str, bool]:
        """PDF権限情報取得"""
        if not self.document:
            return {}
            
        try:
            perms = self.document.permissions
            return {
                "print": bool(perms & fitz.PDF_PERM_PRINT),
                "modify": bool(perms & fitz.PDF_PERM_MODIFY),
                "copy": bool(perms & fitz.PDF_PERM_COPY),
                "annotate": bool(perms & fitz.PDF_PERM_ANNOTATE)
            }
        except:
            return {"error": "Could not determine permissions"}
```

## 高速テキスト抽出パターン

### 最適化テキスト抽出
```python
class OptimizedTextExtractor:
    """最適化テキスト抽出クラス"""
    
    def __init__(self, document: fitz.Document):
        self.document = document
        self.text_cache = {}
        
    def extract_text_with_coordinates(
        self, 
        page_num: int,
        method: str = "dict",
        include_images: bool = False
    ) -> Dict[str, Any]:
        """座標付きテキスト抽出"""
        
        # キャッシュチェック
        cache_key = f"{page_num}_{method}_{include_images}"
        if cache_key in self.text_cache:
            return self.text_cache[cache_key]
        
        page = self.document[page_num]
        
        # 抽出方法による分岐
        if method == "dict":
            result = self._extract_with_dict_method(page, include_images)
        elif method == "blocks":
            result = self._extract_with_blocks_method(page)
        elif method == "words":
            result = self._extract_with_words_method(page)
        else:
            raise ValueError(f"Unknown extraction method: {method}")
        
        # 結果をキャッシュ
        self.text_cache[cache_key] = result
        return result
    
    def _extract_with_dict_method(
        self, 
        page: fitz.Page, 
        include_images: bool = False
    ) -> Dict[str, Any]:
        """辞書形式での詳細抽出"""
        
        # PyMuPDF の get_text("dict") は最も詳細な情報を提供
        text_dict = page.get_text("dict")
        
        extracted_text = ""
        text_elements = []
        
        for block in text_dict["blocks"]:
            if block.get("type") == 0:  # テキストブロック
                for line in block.get("lines", []):
                    line_text = ""
                    line_elements = []
                    
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        if span_text.strip():
                            
                            # テキストエレメント情報
                            element = {
                                "text": span_text,
                                "bbox": span.get("bbox"),  # (x0, y0, x1, y1)
                                "font": span.get("font", ""),
                                "size": span.get("size", 0),
                                "flags": span.get("flags", 0),  # bold, italic etc
                                "color": span.get("color", 0),
                                "ascender": span.get("ascender", 0),
                                "descender": span.get("descender", 0)
                            }
                            
                            line_text += span_text
                            line_elements.append(element)
                    
                    if line_text.strip():
                        extracted_text += line_text + "\n"
                        text_elements.extend(line_elements)
            
            elif include_images and block.get("type") == 1:  # 画像ブロック
                # 画像情報も含める
                image_info = {
                    "type": "image",
                    "bbox": block.get("bbox"),
                    "width": block.get("width", 0),
                    "height": block.get("height", 0),
                    "ext": block.get("ext", ""),
                    "size": block.get("size", 0)
                }
                text_elements.append(image_info)
        
        return {
            "text": extracted_text.strip(),
            "elements": text_elements,
            "page_num": page.number,
            "page_size": page.rect,
            "extraction_method": "dict"
        }
    
    def _extract_with_blocks_method(self, page: fitz.Page) -> Dict[str, Any]:
        """ブロック単位での高速抽出"""
        
        blocks = page.get_text("blocks")
        
        text_content = ""
        block_info = []
        
        for block_num, block in enumerate(blocks):
            if len(block) >= 5:  # テキストブロック
                block_text = block[4]  # テキスト内容
                block_bbox = block[:4]  # 座標
                
                text_content += block_text + "\n"
                
                block_info.append({
                    "block_num": block_num,
                    "text": block_text.strip(),
                    "bbox": block_bbox,
                    "type": "text"
                })
        
        return {
            "text": text_content.strip(),
            "blocks": block_info,
            "page_num": page.number,
            "extraction_method": "blocks"
        }
    
    def _extract_with_words_method(self, page: fitz.Page) -> Dict[str, Any]:
        """単語単位での精密抽出"""
        
        words = page.get_text("words")
        
        text_content = ""
        word_info = []
        
        current_line_y = None
        
        for word in words:
            if len(word) >= 5:
                x0, y0, x1, y1, word_text, block_num, line_num, word_num = word
                
                # 改行判定
                if current_line_y is not None and abs(y0 - current_line_y) > 5:
                    text_content += "\n"
                
                text_content += word_text + " "
                current_line_y = y0
                
                word_info.append({
                    "text": word_text,
                    "bbox": (x0, y0, x1, y1),
                    "block_num": block_num,
                    "line_num": line_num,
                    "word_num": word_num
                })
        
        return {
            "text": text_content.strip(),
            "words": word_info,
            "page_num": page.number,
            "extraction_method": "words"
        }
    
    def extract_text_by_region(
        self, 
        page_num: int, 
        region_bbox: Tuple[float, float, float, float]
    ) -> Dict[str, Any]:
        """指定領域のテキスト抽出"""
        
        page = self.document[page_num]
        clip_rect = fitz.Rect(region_bbox)
        
        # 領域でクリップしてテキスト抽出
        text_dict = page.get_text("dict", clip=clip_rect)
        
        region_text = ""
        region_elements = []
        
        for block in text_dict["blocks"]:
            if block.get("type") == 0:  # テキストブロック
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        span_bbox = span.get("bbox")
                        
                        # 領域内判定
                        if (span_bbox and 
                            clip_rect.intersects(fitz.Rect(span_bbox))):
                            
                            region_text += span_text
                            region_elements.append({
                                "text": span_text,
                                "bbox": span_bbox,
                                "font": span.get("font", ""),
                                "size": span.get("size", 0)
                            })
        
        return {
            "text": region_text.strip(),
            "elements": region_elements,
            "region": region_bbox,
            "page_num": page_num
        }
```

## 座標系・レイアウト解析

### 精密座標計算
```python
class PDFCoordinateSystem:
    """PDF座標系処理クラス"""
    
    def __init__(self, document: fitz.Document):
        self.document = document
        
    def find_text_coordinates(
        self, 
        page_num: int, 
        search_text: str,
        case_sensitive: bool = False
    ) -> List[Dict[str, Any]]:
        """テキスト座標検索"""
        
        page = self.document[page_num]
        
        # テキスト検索実行
        search_flags = 0 if case_sensitive else fitz.TEXT_DEHYPHENATE | fitz.TEXT_PRESERVE_WHITESPACE
        
        text_instances = page.search_for(search_text, flags=search_flags)
        
        results = []
        for i, rect in enumerate(text_instances):
            
            # より詳細な情報取得
            detailed_info = self._get_text_details_at_position(page, rect)
            
            results.append({
                "instance": i,
                "text": search_text,
                "bbox": tuple(rect),
                "center": ((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2),
                "width": rect.width,
                "height": rect.height,
                "details": detailed_info
            })
        
        return results
    
    def _get_text_details_at_position(
        self, 
        page: fitz.Page, 
        rect: fitz.Rect
    ) -> Dict[str, Any]:
        """指定位置のテキスト詳細情報取得"""
        
        # 位置周辺のテキスト情報を取得
        expanded_rect = rect + (-2, -2, 2, 2)  # わずかに拡張
        text_dict = page.get_text("dict", clip=expanded_rect)
        
        details = {
            "font_info": [],
            "color_info": [],
            "size_info": []
        }
        
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # テキストブロック
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_rect = fitz.Rect(span.get("bbox", [0, 0, 0, 0]))
                        
                        # 重複判定
                        if rect.intersects(span_rect):
                            details["font_info"].append(span.get("font", ""))
                            details["color_info"].append(span.get("color", 0))
                            details["size_info"].append(span.get("size", 0))
        
        # 最頻値を取得
        if details["font_info"]:
            details["primary_font"] = max(set(details["font_info"]), key=details["font_info"].count)
        if details["color_info"]:
            details["primary_color"] = max(set(details["color_info"]), key=details["color_info"].count)
        if details["size_info"]:
            details["primary_size"] = max(set(details["size_info"]), key=details["size_info"].count)
        
        return details
    
    def analyze_page_layout(self, page_num: int) -> Dict[str, Any]:
        """ページレイアウト解析"""
        
        page = self.document[page_num]
        text_dict = page.get_text("dict")
        
        # レイアウト情報初期化
        layout = {
            "page_size": tuple(page.rect),
            "columns": [],
            "text_blocks": [],
            "font_analysis": {},
            "spacing_analysis": {}
        }
        
        text_blocks = []
        
        # ブロック情報収集
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # テキストブロック
                block_bbox = block.get("bbox")
                block_text = ""
                
                fonts_in_block = []
                sizes_in_block = []
                
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        block_text += span.get("text", "")
                        fonts_in_block.append(span.get("font", ""))
                        sizes_in_block.append(span.get("size", 0))
                
                if block_text.strip():
                    text_blocks.append({
                        "bbox": block_bbox,
                        "text": block_text.strip(),
                        "char_count": len(block_text.strip()),
                        "fonts": fonts_in_block,
                        "sizes": sizes_in_block,
                        "avg_size": sum(sizes_in_block) / len(sizes_in_block) if sizes_in_block else 0
                    })
        
        # カラム検出
        layout["columns"] = self._detect_columns(text_blocks)
        
        # フォント解析
        layout["font_analysis"] = self._analyze_fonts(text_blocks)
        
        # 間隔解析
        layout["spacing_analysis"] = self._analyze_spacing(text_blocks)
        
        layout["text_blocks"] = text_blocks
        
        return layout
    
    def _detect_columns(self, text_blocks: List[Dict]) -> List[Dict]:
        """カラム検出"""
        
        if not text_blocks:
            return []
        
        # X座標でブロックをグループ化
        x_positions = [(block["bbox"][0], block["bbox"][2]) for block in text_blocks]
        x_positions.sort()
        
        columns = []
        current_column = {"x_start": x_positions[0][0], "x_end": x_positions[0][1], "blocks": []}
        
        tolerance = 10  # ピクセル許容範囲
        
        for i, (x_start, x_end) in enumerate(x_positions):
            if abs(x_start - current_column["x_start"]) <= tolerance:
                # 同じカラム
                current_column["x_end"] = max(current_column["x_end"], x_end)
                current_column["blocks"].append(i)
            else:
                # 新しいカラム
                if current_column["blocks"]:
                    columns.append(current_column)
                current_column = {"x_start": x_start, "x_end": x_end, "blocks": [i]}
        
        # 最後のカラム
        if current_column["blocks"]:
            columns.append(current_column)
        
        return columns
    
    def _analyze_fonts(self, text_blocks: List[Dict]) -> Dict[str, Any]:
        """フォント解析"""
        
        all_fonts = []
        all_sizes = []
        
        for block in text_blocks:
            all_fonts.extend(block["fonts"])
            all_sizes.extend(block["sizes"])
        
        # フォント頻度分析
        font_counts = {}
        for font in all_fonts:
            font_counts[font] = font_counts.get(font, 0) + 1
        
        # サイズ頻度分析
        size_counts = {}
        for size in all_sizes:
            rounded_size = round(size, 1)
            size_counts[rounded_size] = size_counts.get(rounded_size, 0) + 1
        
        return {
            "font_distribution": font_counts,
            "size_distribution": size_counts,
            "primary_font": max(font_counts.items(), key=lambda x: x[1])[0] if font_counts else None,
            "primary_size": max(size_counts.items(), key=lambda x: x[1])[0] if size_counts else None,
            "unique_fonts": len(font_counts),
            "unique_sizes": len(size_counts)
        }
    
    def _analyze_spacing(self, text_blocks: List[Dict]) -> Dict[str, Any]:
        """間隔解析"""
        
        if len(text_blocks) < 2:
            return {"error": "Insufficient blocks for spacing analysis"}
        
        vertical_gaps = []
        horizontal_gaps = []
        
        # ブロック間距離計算
        for i, block1 in enumerate(text_blocks):
            for j, block2 in enumerate(text_blocks[i+1:], i+1):
                bbox1 = block1["bbox"]
                bbox2 = block2["bbox"]
                
                # 垂直方向の間隔
                if bbox1[3] <= bbox2[1]:  # block1がblock2の上にある
                    vertical_gaps.append(bbox2[1] - bbox1[3])
                elif bbox2[3] <= bbox1[1]:  # block2がblock1の上にある
                    vertical_gaps.append(bbox1[1] - bbox2[3])
                
                # 水平方向の間隔
                if bbox1[2] <= bbox2[0]:  # block1がblock2の左にある
                    horizontal_gaps.append(bbox2[0] - bbox1[2])
                elif bbox2[2] <= bbox1[0]:  # block2がblock1の左にある
                    horizontal_gaps.append(bbox1[0] - bbox2[2])
        
        return {
            "vertical_gaps": {
                "min": min(vertical_gaps) if vertical_gaps else 0,
                "max": max(vertical_gaps) if vertical_gaps else 0,
                "avg": sum(vertical_gaps) / len(vertical_gaps) if vertical_gaps else 0,
                "count": len(vertical_gaps)
            },
            "horizontal_gaps": {
                "min": min(horizontal_gaps) if horizontal_gaps else 0,
                "max": max(horizontal_gaps) if horizontal_gaps else 0,
                "avg": sum(horizontal_gaps) / len(horizontal_gaps) if horizontal_gaps else 0,
                "count": len(horizontal_gaps)
            }
        }
```

## アノテーション・マスキング処理

### 高度なアノテーション操作
```python
class AdvancedAnnotationHandler:
    """高度なアノテーション処理クラス"""
    
    def __init__(self, document: fitz.Document):
        self.document = document
        
    def create_highlight_annotation(
        self, 
        page_num: int,
        bbox: Tuple[float, float, float, float],
        color: Tuple[float, float, float] = (1.0, 1.0, 0.0),  # 黄色
        opacity: float = 0.3,
        content: str = None
    ) -> fitz.Annot:
        """ハイライトアノテーション作成"""
        
        page = self.document[page_num]
        rect = fitz.Rect(bbox)
        
        # ハイライトアノテーション追加
        highlight = page.add_highlight_annot(rect)
        
        # 色設定
        highlight.set_colors(stroke=color)
        highlight.set_opacity(opacity)
        
        # 内容設定
        if content:
            highlight.set_content(content)
        
        # アノテーション更新
        highlight.update()
        
        return highlight
    
    def create_redaction_annotation(
        self, 
        page_num: int,
        bbox: Tuple[float, float, float, float],
        fill_color: Tuple[float, float, float] = (0.0, 0.0, 0.0),  # 黒色
        overlay_text: str = None
    ) -> fitz.Annot:
        """墨消しアノテーション作成"""
        
        page = self.document[page_num]
        rect = fitz.Rect(bbox)
        
        # 墨消しアノテーション追加
        redaction = page.add_redact_annot(rect, text=overlay_text)
        
        # 色設定
        redaction.set_colors(fill=fill_color)
        
        # アノテーション更新
        redaction.update()
        
        return redaction
    
    def apply_redactions(self, page_num: int = None) -> List[int]:
        """墨消し適用"""
        
        applied_pages = []
        
        if page_num is not None:
            # 特定ページのみ
            page = self.document[page_num]
            page.apply_redactions()
            applied_pages.append(page_num)
        else:
            # 全ページ
            for page_num in range(self.document.page_count):
                page = self.document[page_num]
                if page.redact_list:  # 墨消しアノテーションが存在する場合のみ
                    page.apply_redactions()
                    applied_pages.append(page_num)
        
        return applied_pages
    
    def create_masked_text_overlay(
        self, 
        page_num: int,
        bbox: Tuple[float, float, float, float],
        mask_pattern: str = "■■■■",
        font_size: float = None,
        font_name: str = "helv",
        color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    ) -> None:
        """マスクテキストオーバーレイ作成"""
        
        page = self.document[page_num]
        rect = fitz.Rect(bbox)
        
        # 元のテキストサイズを自動検出
        if font_size is None:
            font_size = self._detect_font_size_in_rect(page, rect)
        
        # 背景塗りつぶし（元テキスト隠蔽）
        white_rect = page.new_shape()
        white_rect.draw_rect(rect)
        white_rect.finish(fill=(1, 1, 1), color=(1, 1, 1))
        white_rect.commit()
        
        # マスクテキスト挿入
        text_rect = fitz.Rect(rect.x0 + 2, rect.y0 + 2, rect.x1 - 2, rect.y1 - 2)  # わずかに内側
        
        page.insert_text(
            text_rect.tl,  # 左上座標
            mask_pattern,
            fontsize=font_size,
            fontname=font_name,
            color=color
        )
    
    def _detect_font_size_in_rect(
        self, 
        page: fitz.Page, 
        rect: fitz.Rect
    ) -> float:
        """矩形内フォントサイズ自動検出"""
        
        text_dict = page.get_text("dict", clip=rect)
        font_sizes = []
        
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # テキストブロック
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size", 0)
                        if size > 0:
                            font_sizes.append(size)
        
        # 最頻値または平均値を返す
        if font_sizes:
            return sum(font_sizes) / len(font_sizes)
        else:
            return 12.0  # デフォルト
    
    def get_all_annotations(self, page_num: int = None) -> Dict[str, List]:
        """アノテーション一覧取得"""
        
        annotations = {
            "highlights": [],
            "redactions": [], 
            "text_annotations": [],
            "other": []
        }
        
        pages_to_check = [page_num] if page_num is not None else range(self.document.page_count)
        
        for pnum in pages_to_check:
            page = self.document[pnum]
            
            for annot in page.annots():
                annot_info = {
                    "page": pnum,
                    "type": annot.type[1],  # アノテーションタイプ名
                    "bbox": tuple(annot.rect),
                    "content": annot.content,
                    "author": annot.info.get("title", ""),
                    "creation_date": annot.info.get("creationDate", ""),
                    "colors": {
                        "stroke": annot.colors.get("stroke"),
                        "fill": annot.colors.get("fill")
                    },
                    "opacity": annot.opacity
                }
                
                # タイプ別分類
                if annot.type[1] == "Highlight":
                    annotations["highlights"].append(annot_info)
                elif annot.type[1] == "Redact":
                    annotations["redactions"].append(annot_info)
                elif annot.type[1] in ["Text", "FreeText"]:
                    annotations["text_annotations"].append(annot_info)
                else:
                    annotations["other"].append(annot_info)
        
        return annotations
    
    def remove_all_annotations(self, page_num: int = None, annotation_types: List[str] = None) -> int:
        """アノテーション削除"""
        
        removed_count = 0
        pages_to_process = [page_num] if page_num is not None else range(self.document.page_count)
        
        for pnum in pages_to_process:
            page = self.document[pnum]
            
            # 削除対象アノテーション収集（逆順）
            annotations_to_remove = []
            for annot in page.annots():
                if annotation_types is None or annot.type[1] in annotation_types:
                    annotations_to_remove.append(annot)
            
            # アノテーション削除
            for annot in reversed(annotations_to_remove):  # 逆順で削除
                page.delete_annot(annot)
                removed_count += 1
        
        return removed_count
```

## メモリ管理・最適化パターン

### メモリ効率的処理
```python
class MemoryOptimizedPDFProcessor:
    """メモリ最適化PDF処理クラス"""
    
    def __init__(self):
        self.current_document = None
        self.memory_threshold = 500 * 1024 * 1024  # 500MB
        
    def process_large_pdf_streaming(
        self, 
        file_path: str,
        processor_func: Callable[[fitz.Page, int], Any],
        chunk_size: int = 10
    ) -> List[Any]:
        """大容量PDF ストリーミング処理"""
        
        results = []
        
        try:
            document = fitz.open(file_path)
            total_pages = document.page_count
            
            # チャンク単位で処理
            for start_page in range(0, total_pages, chunk_size):
                end_page = min(start_page + chunk_size, total_pages)
                
                # チャンク処理
                chunk_results = []
                for page_num in range(start_page, end_page):
                    page = document.load_page(page_num)
                    
                    try:
                        result = processor_func(page, page_num)
                        chunk_results.append(result)
                    except Exception as e:
                        print(f"Error processing page {page_num}: {e}")
                        chunk_results.append(None)
                    finally:
                        # ページオブジェクト明示的削除
                        del page
                
                results.extend(chunk_results)
                
                # メモリクリーンアップ
                if start_page % (chunk_size * 5) == 0:  # 5チャンクごと
                    self._force_garbage_collection()
                    
                    # メモリ使用量チェック
                    if self._get_memory_usage() > self.memory_threshold:
                        print(f"Memory threshold reached, forcing cleanup...")
                        self._force_garbage_collection()
            
        finally:
            if document:
                document.close()
        
        return results
    
    def _force_garbage_collection(self):
        """強制ガベージコレクション"""
        import gc
        gc.collect()
        
        # PyMuPDF 固有のクリーンアップ
        try:
            fitz.tools.mupdf_display_errors(False)
        except:
            pass
    
    def _get_memory_usage(self) -> int:
        """現在のメモリ使用量取得"""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss
    
    def batch_process_with_memory_limit(
        self, 
        file_paths: List[str],
        processor_func: Callable[[fitz.Document], Any],
        memory_limit: int = None
    ) -> List[Any]:
        """メモリ制限付きバッチ処理"""
        
        if memory_limit is None:
            memory_limit = self.memory_threshold
        
        results = []
        processed_count = 0
        
        for file_path in file_paths:
            # メモリチェック
            current_memory = self._get_memory_usage()
            if current_memory > memory_limit:
                print(f"Memory limit reached ({current_memory / 1024 / 1024:.1f}MB), forcing cleanup...")
                self._force_garbage_collection()
                
                # まだ限界を超えている場合は警告
                current_memory = self._get_memory_usage()
                if current_memory > memory_limit:
                    print(f"Warning: Memory usage still high ({current_memory / 1024 / 1024:.1f}MB)")
            
            # ファイル処理
            try:
                document = fitz.open(file_path)
                result = processor_func(document)
                results.append(result)
                processed_count += 1
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                results.append(None)
            
            finally:
                if 'document' in locals():
                    document.close()
                    del document
                
                # 定期的なクリーンアップ
                if processed_count % 10 == 0:
                    self._force_garbage_collection()
        
        return results
    
    def create_optimized_copy(
        self, 
        source_path: str, 
        target_path: str,
        optimization_options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """最適化コピー作成"""
        
        default_options = {
            "compress_images": True,
            "image_quality": 85,
            "remove_unused_objects": True,
            "linearize": True,  # Web最適化
            "remove_metadata": False,
            "compress_fonts": True
        }
        
        if optimization_options:
            default_options.update(optimization_options)
        
        try:
            source_doc = fitz.open(source_path)
            
            # 最適化されたPDF作成
            target_doc = fitz.open()  # 新しいドキュメント
            
            for page_num in range(source_doc.page_count):
                source_page = source_doc.load_page(page_num)
                
                # ページを新しいドキュメントに挿入
                target_doc.insert_pdf(source_doc, from_page=page_num, to_page=page_num)
                
                # メモリクリーンアップ
                del source_page
                
                if page_num % 50 == 0:  # 50ページごと
                    self._force_garbage_collection()
            
            # 最適化オプション適用
            save_options = {}
            
            if default_options.get("remove_unused_objects"):
                save_options["garbage"] = 4  # 最高レベルのガベージ除去
                save_options["clean"] = True
            
            if default_options.get("linearize"):
                save_options["linear"] = True
            
            if default_options.get("compress_images"):
                save_options["deflate"] = True
            
            # 保存
            target_doc.save(target_path, **save_options)
            
            # ファイルサイズ比較
            import os
            original_size = os.path.getsize(source_path)
            optimized_size = os.path.getsize(target_path)
            
            optimization_result = {
                "original_size": original_size,
                "optimized_size": optimized_size,
                "compression_ratio": optimized_size / original_size,
                "size_reduction": original_size - optimized_size,
                "size_reduction_percent": ((original_size - optimized_size) / original_size) * 100,
                "options_used": default_options
            }
            
            return optimization_result
            
        finally:
            if 'source_doc' in locals():
                source_doc.close()
            if 'target_doc' in locals():
                target_doc.close()
```

## 高度な検索・パターンマッチング

### 正規表現検索
```python
class AdvancedPDFSearcher:
    """高度なPDF検索クラス"""
    
    def __init__(self, document: fitz.Document):
        self.document = document
        
    def regex_search(
        self, 
        pattern: str,
        page_range: Tuple[int, int] = None,
        flags: int = 0
    ) -> List[Dict[str, Any]]:
        """正規表現検索"""
        import re
        
        compiled_pattern = re.compile(pattern, flags)
        matches = []
        
        start_page = page_range[0] if page_range else 0
        end_page = page_range[1] if page_range else self.document.page_count
        
        for page_num in range(start_page, end_page):
            page = self.document[page_num]
            page_text = page.get_text()
            
            # 正規表現マッチング
            for match in compiled_pattern.finditer(page_text):
                match_text = match.group()
                start_pos = match.start()
                end_pos = match.end()
                
                # テキスト位置から座標を推定
                coordinates = self._estimate_text_coordinates(
                    page, page_text, start_pos, end_pos
                )
                
                matches.append({
                    "page": page_num,
                    "text": match_text,
                    "pattern": pattern,
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "coordinates": coordinates,
                    "groups": match.groups(),
                    "context": self._get_context(page_text, start_pos, end_pos)
                })
        
        return matches
    
    def _estimate_text_coordinates(
        self, 
        page: fitz.Page,
        full_text: str,
        start_pos: int,
        end_pos: int,
        context_chars: int = 10
    ) -> Dict[str, Any]:
        """テキスト位置から座標推定"""
        
        # 前後のコンテキストを含めた検索文字列作成
        context_start = max(0, start_pos - context_chars)
        context_end = min(len(full_text), end_pos + context_chars)
        search_context = full_text[context_start:context_end]
        
        # 実際のマッチ部分
        match_in_context = full_text[start_pos:end_pos]
        
        # ページ内で検索
        search_results = page.search_for(match_in_context)
        
        if search_results:
            # 最も適合する結果を選択（通常は最初の結果）
            best_match = search_results[0]
            return {
                "bbox": tuple(best_match),
                "center": ((best_match.x0 + best_match.x1) / 2, (best_match.y0 + best_match.y1) / 2),
                "confidence": "high" if len(search_results) == 1 else "medium"
            }
        else:
            # 座標が見つからない場合は推定
            return {
                "bbox": None,
                "center": None,
                "confidence": "low",
                "error": "Coordinates not found"
            }
    
    def _get_context(self, text: str, start: int, end: int, context_length: int = 50) -> Dict[str, str]:
        """前後のコンテキスト取得"""
        
        context_start = max(0, start - context_length)
        context_end = min(len(text), end + context_length)
        
        return {
            "before": text[context_start:start],
            "match": text[start:end],
            "after": text[end:context_end],
            "full_context": text[context_start:context_end]
        }
    
    def fuzzy_search(
        self, 
        target_text: str,
        similarity_threshold: float = 0.8,
        page_range: Tuple[int, int] = None
    ) -> List[Dict[str, Any]]:
        """あいまい検索"""
        from difflib import SequenceMatcher
        
        matches = []
        target_words = target_text.lower().split()
        
        start_page = page_range[0] if page_range else 0
        end_page = page_range[1] if page_range else self.document.page_count
        
        for page_num in range(start_page, end_page):
            page = self.document[page_num]
            
            # 単語単位で抽出
            words = page.get_text("words")
            
            # スライディングウィンドウで類似度計算
            for i in range(len(words) - len(target_words) + 1):
                window_words = [word[4].lower() for word in words[i:i + len(target_words)]]
                window_text = " ".join(window_words)
                
                # 類似度計算
                similarity = SequenceMatcher(None, target_text.lower(), window_text).ratio()
                
                if similarity >= similarity_threshold:
                    # 座標計算
                    first_word = words[i]
                    last_word = words[i + len(target_words) - 1]
                    
                    bbox = (
                        first_word[0],  # x0
                        min(first_word[1], last_word[1]),  # y0
                        last_word[2],   # x1
                        max(first_word[3], last_word[3])   # y1
                    )
                    
                    matches.append({
                        "page": page_num,
                        "target": target_text,
                        "found": window_text,
                        "similarity": similarity,
                        "bbox": bbox,
                        "word_indices": (i, i + len(target_words) - 1)
                    })
        
        # 類似度の高い順にソート
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches
    
    def semantic_search(
        self, 
        query_text: str,
        page_range: Tuple[int, int] = None,
        min_relevance_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """セマンティック検索（キーワードベース）"""
        
        # 簡易的なセマンティック検索（本格的にはsentence-transformersなど必要）
        query_keywords = set(query_text.lower().split())
        matches = []
        
        start_page = page_range[0] if page_range else 0
        end_page = page_range[1] if page_range else self.document.page_count
        
        for page_num in range(start_page, end_page):
            page = self.document[page_num]
            
            # ブロック単位でテキスト取得
            blocks = page.get_text("blocks")
            
            for block_num, block in enumerate(blocks):
                if len(block) >= 5:  # テキストブロック
                    block_text = block[4].lower()
                    block_words = set(block_text.split())
                    
                    # キーワード重複度計算
                    common_words = query_keywords.intersection(block_words)
                    relevance_score = len(common_words) / len(query_keywords) if query_keywords else 0
                    
                    if relevance_score >= min_relevance_score:
                        matches.append({
                            "page": page_num,
                            "block": block_num,
                            "text": block[4].strip()[:200] + "..." if len(block[4]) > 200 else block[4].strip(),
                            "bbox": block[:4],
                            "relevance_score": relevance_score,
                            "matching_keywords": list(common_words),
                            "keyword_density": len(common_words) / len(block_words) if block_words else 0
                        })
        
        # 関連度順でソート
        matches.sort(key=lambda x: x["relevance_score"], reverse=True)
        return matches
```

この PyMuPDF 活用パターン・最適化ガイドにより、PresidioPDF プロジェクトにおける PDF 処理の効率性、精度、パフォーマンスを大幅に向上させることができます。