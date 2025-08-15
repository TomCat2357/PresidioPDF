"""
PDFCoordinateMapper - PDFに座標⇔ページ、ブロック、オフセット情報のマップを埋め込む機能
"""
import fitz
import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class CoordinateMapping:
    """座標マッピング情報を格納するデータクラス"""
    page: int
    block_idx: int
    line_idx: int
    span_idx: int
    char_start: int
    char_end: int
    bbox: List[float]  # [x0, y0, x1, y1]
    text: str
    font: str = ""
    size: float = 0.0


@dataclass
class CoordinateMapMetadata:
    """座標マップのメタデータ"""
    version: str = "1.0"
    created_by: str = "PDFCoordinateMapper"
    total_mappings: int = 0
    page_count: int = 0
    encoding: str = "utf-8"


class PDFCoordinateMapper:
    """PDFに座標⇔ページ、ブロック、オフセット情報のマップを埋め込むクラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.embedded_filename = "coordinate_map.json"
        self.coordinate_mappings: List[CoordinateMapping] = []
        self.metadata: CoordinateMapMetadata = CoordinateMapMetadata()
    
    def load_or_create_coordinate_map(self, pdf_path: str) -> bool:
        """既存のPDFから座標マップを読み込み、なければ新規作成"""
        try:
            # まず既存のマップを読み込み試行
            if self._load_existing_coordinate_map(pdf_path):
                self.logger.info(f"既存の座標マップを読み込みました: {len(self.coordinate_mappings)}件")
                return True
            
            # 既存マップがない場合は新規作成
            self.logger.info("既存の座標マップが見つからないため、新規作成します")
            return self._create_new_coordinate_map(pdf_path)
            
        except Exception as e:
            self.logger.error(f"座標マップの読み込み/作成エラー: {e}")
            return False
    
    def _load_existing_coordinate_map(self, pdf_path: str) -> bool:
        """PDFから既存の座標マップを読み込み"""
        try:
            doc = fitz.open(pdf_path)
            
            # 埋め込みファイル一覧を確認
            embedded_files = doc.embfile_names()
            
            if self.embedded_filename in embedded_files:
                # 埋め込まれた座標マップを読み込み
                file_data = doc.embfile_get(self.embedded_filename)
                json_str = file_data.decode('utf-8')
                map_data = json.loads(json_str)
                
                # メタデータを復元
                if 'metadata' in map_data:
                    self.metadata = CoordinateMapMetadata(**map_data['metadata'])
                
                # 座標マッピングを復元
                if 'mappings' in map_data:
                    self.coordinate_mappings = [
                        CoordinateMapping(**mapping) 
                        for mapping in map_data['mappings']
                    ]
                
                doc.close()
                return True
            
            doc.close()
            return False
            
        except Exception as e:
            self.logger.error(f"既存座標マップ読み込みエラー: {e}")
            return False
    
    def _create_new_coordinate_map(self, pdf_path: str) -> bool:
        """PDFから新規座標マップを作成"""
        try:
            doc = fitz.open(pdf_path)
            self.coordinate_mappings = []
            
            # 各ページからテキストと座標情報を抽出
            for page_num in range(doc.page_count):
                page = doc[page_num]
                blocks = page.get_text("dict")["blocks"]
                
                for block_idx, block in enumerate(blocks):
                    if "lines" not in block:
                        continue
                    
                    for line_idx, line in enumerate(block["lines"]):
                        for span_idx, span in enumerate(line["spans"]):
                            # スパン内の文字情報を取得
                            span_text = span["text"]
                            span_bbox = span["bbox"]
                            span_font = span.get("font", "")
                            span_size = span.get("size", 0.0)
                            
                            # 文字レベルでのオフセット計算
                            char_start = 0
                            char_end = len(span_text)
                            
                            if span_text.strip():  # 空白のみでない場合
                                mapping = CoordinateMapping(
                                    page=page_num,
                                    block_idx=block_idx,
                                    line_idx=line_idx,
                                    span_idx=span_idx,
                                    char_start=char_start,
                                    char_end=char_end,
                                    bbox=list(span_bbox),
                                    text=span_text,
                                    font=span_font,
                                    size=span_size
                                )
                                self.coordinate_mappings.append(mapping)
            
            # メタデータを更新
            self.metadata.total_mappings = len(self.coordinate_mappings)
            self.metadata.page_count = doc.page_count
            
            doc.close()
            self.logger.info(f"新規座標マップを作成しました: {len(self.coordinate_mappings)}件")
            return True
            
        except Exception as e:
            self.logger.error(f"新規座標マップ作成エラー: {e}")
            return False
    
    def save_pdf_with_coordinate_map(self, input_pdf_path: str, output_pdf_path: str) -> bool:
        """座標マップを埋め込んだPDFを保存"""
        try:
            doc = fitz.open(input_pdf_path)
            
            # 座標マップデータを準備
            map_data = {
                "metadata": asdict(self.metadata),
                "mappings": [asdict(mapping) for mapping in self.coordinate_mappings]
            }
            
            # JSONデータをバイト列に変換
            json_data = json.dumps(map_data, ensure_ascii=False, indent=2).encode('utf-8')
            
            # 既存の座標マップファイルがあれば削除
            embedded_files = doc.embfile_names()
            if self.embedded_filename in embedded_files:
                doc.embfile_del(self.embedded_filename)
            
            # 新しい座標マップを埋め込み
            doc.embfile_add(self.embedded_filename, json_data, filename=self.embedded_filename)
            
            # PDFを保存
            doc.save(output_pdf_path, garbage=4, deflate=True)
            doc.close()
            
            self.logger.info(f"座標マップを埋め込んだPDFを保存しました: {output_pdf_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"座標マップ埋め込みPDF保存エラー: {e}")
            return False
    
    def find_coordinate_by_text(self, search_text: str, page: Optional[int] = None) -> List[CoordinateMapping]:
        """テキストから座標情報を検索"""
        results = []
        for mapping in self.coordinate_mappings:
            if page is not None and mapping.page != page:
                continue
            if search_text in mapping.text:
                results.append(mapping)
        return results
    
    def find_text_by_coordinate(self, x: float, y: float, page: int, tolerance: float = 5.0) -> List[CoordinateMapping]:
        """座標からテキスト情報を検索"""
        results = []
        for mapping in self.coordinate_mappings:
            if mapping.page != page:
                continue
            
            bbox = mapping.bbox
            if (bbox[0] - tolerance <= x <= bbox[2] + tolerance and 
                bbox[1] - tolerance <= y <= bbox[3] + tolerance):
                results.append(mapping)
        return results
    
    def get_block_info(self, page: int, block_idx: int) -> List[CoordinateMapping]:
        """指定されたページとブロックの全マッピング情報を取得"""
        return [
            mapping for mapping in self.coordinate_mappings
            if mapping.page == page and mapping.block_idx == block_idx
        ]
    
    def get_page_mappings(self, page: int) -> List[CoordinateMapping]:
        """指定されたページの全マッピング情報を取得"""
        return [
            mapping for mapping in self.coordinate_mappings
            if mapping.page == page
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """座標マップの統計情報を取得"""
        if not self.coordinate_mappings:
            return {"total_mappings": 0, "pages": 0}
        
        pages = set(mapping.page for mapping in self.coordinate_mappings)
        blocks_per_page = {}
        
        for page in pages:
            page_mappings = self.get_page_mappings(page)
            blocks = set(mapping.block_idx for mapping in page_mappings)
            blocks_per_page[page] = len(blocks)
        
        return {
            "total_mappings": len(self.coordinate_mappings),
            "pages": len(pages),
            "blocks_per_page": blocks_per_page,
            "metadata": asdict(self.metadata)
        }
    
    def export_coordinate_map(self, output_path: str) -> bool:
        """座標マップを外部JSONファイルとしてエクスポート"""
        try:
            map_data = {
                "metadata": asdict(self.metadata),
                "mappings": [asdict(mapping) for mapping in self.coordinate_mappings]
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(map_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"座標マップをエクスポートしました: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"座標マップエクスポートエラー: {e}")
            return False


# 使用例とテスト用のヘルパー関数
def create_coordinate_mapper_demo(pdf_path: str, output_path: str) -> bool:
    """座標マッパーのデモ実行"""
    mapper = PDFCoordinateMapper()
    
    # 座標マップの読み込みまたは作成
    if not mapper.load_or_create_coordinate_map(pdf_path):
        return False
    
    # 統計情報の表示
    stats = mapper.get_statistics()
    print(f"座標マッピング統計: {stats}")
    
    # 座標マップを埋め込んだPDFとして保存
    if mapper.save_pdf_with_coordinate_map(pdf_path, output_path):
        print(f"座標マップ埋め込みPDFを保存: {output_path}")
        return True
    
    return False


if __name__ == "__main__":
    # テスト実行
    import sys
    if len(sys.argv) >= 3:
        pdf_path = sys.argv[1]
        output_path = sys.argv[2]
        create_coordinate_mapper_demo(pdf_path, output_path)
    else:
        print("使用法: python pdf_coordinate_mapper.py <input_pdf> <output_pdf>")