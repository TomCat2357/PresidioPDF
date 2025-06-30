#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
b1.pdf PII検出・座標取得テストコード
PDFProcessorクラスを使用してPII検出と座標詳細をJSON形式で出力
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# srcディレクトリをパスに追加
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from config_manager import ConfigManager
from pdf_processor import PDFProcessor
from pdf_locator import PDFTextLocator
import fitz

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_b1_analysis.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class B1PIIAnalyzer:
    """b1.pdf専用PII解析クラス"""
    
    def __init__(self):
        self.project_root = project_root
        self.pdf_path = self.project_root / "test_pdfs" / "b1.pdf"
        self.output_dir = self.project_root / "outputs" / "reports"
        
        # 出力ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 設定管理
        self.config_manager = ConfigManager()
        
        # PDFProcessor初期化
        self.processor = PDFProcessor(self.config_manager)
        
        logger.info(f"B1PIIAnalyzer初期化完了: {self.pdf_path}")
    
    def analyze_b1_pdf(self):
        """b1.pdfの詳細PII解析"""
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDFファイルが見つかりません: {self.pdf_path}")
        
        logger.info(f"b1.pdf解析開始: {self.pdf_path}")
        
        # PDFProcessorで解析
        pii_results = self.processor.analyze_pdf(str(self.pdf_path))
        
        # 詳細解析結果構築
        detailed_analysis = {
            "analysis_info": {
                "pdf_file": str(self.pdf_path),
                "analysis_timestamp": datetime.now().isoformat(),
                "total_pii_found": len(pii_results),
                "enabled_entities": self.config_manager.get_enabled_entities(),
                "masking_method": self.config_manager.get_pdf_masking_method()
            },
            "pdf_document_info": self._get_pdf_document_info(),
            "pii_detections": []
        }
        
        # 各PII詳細情報追加
        for idx, pii in enumerate(pii_results):
            detailed_pii = self._create_detailed_pii_info(pii, idx)
            detailed_analysis["pii_detections"].append(detailed_pii)
        
        # 統計情報追加
        detailed_analysis["statistics"] = self._generate_statistics(pii_results)
        
        logger.info(f"b1.pdf解析完了: {len(pii_results)}件のPII検出")
        return detailed_analysis
    
    def _get_pdf_document_info(self):
        """PDF文書情報取得"""
        try:
            doc = fitz.open(str(self.pdf_path))
            locator = PDFTextLocator(doc)
            
            info = {
                "page_count": len(doc),
                "document_metadata": doc.metadata,
                "full_text_length": len(locator.full_text),
                "no_newlines_text_length": len(locator.full_text_no_newlines),
                "locator_stats": locator.get_stats(),
                "integrity_check": locator.validate_integrity()
            }
            
            doc.close()
            return info
            
        except Exception as e:
            logger.error(f"PDF文書情報取得エラー: {e}")
            return {"error": str(e)}
    
    def _create_detailed_pii_info(self, pii, index):
        """詳細PII情報作成"""
        try:
            detailed_pii = {
                "pii_index": index + 1,
                "entity_type": pii.get("entity_type", "UNKNOWN"),
                "text": pii.get("text", ""),
                "confidence_score": pii.get("score", 0.0),
                "start_offset": pii.get("start", -1),
                "end_offset": pii.get("end", -1),
                "coordinates": pii.get("coordinates", {}),
                "page_info": pii.get("page_info", {}),
                "line_rects": []
            }
            
            # line_rectsの詳細情報
            line_rects = pii.get("line_rects", [])
            for line_idx, line_rect_info in enumerate(line_rects):
                rect_data = line_rect_info.get("rect")
                page_num = line_rect_info.get("page_num", 0)
                
                line_detail = {
                    "line_index": line_idx + 1,
                    "page_number": page_num + 1,
                    "rect_coordinates": {
                        "x0": float(rect_data.x0) if rect_data else None,
                        "y0": float(rect_data.y0) if rect_data else None,
                        "x1": float(rect_data.x1) if rect_data else None,
                        "y1": float(rect_data.y1) if rect_data else None,
                        "width": float(rect_data.x1 - rect_data.x0) if rect_data else None,
                        "height": float(rect_data.y1 - rect_data.y0) if rect_data else None
                    }
                }
                
                detailed_pii["line_rects"].append(line_detail)
            
            # 文字レベル詳細座標を追加取得
            if pii.get("start") is not None and pii.get("end") is not None:
                detailed_pii["character_level_details"] = self._get_character_level_coordinates(
                    pii["start"], pii["end"]
                )
            
            return detailed_pii
            
        except Exception as e:
            logger.error(f"詳細PII情報作成エラー: {e}")
            return {"error": str(e), "original_pii": pii}
    
    def _get_character_level_coordinates(self, start, end):
        """文字レベル座標詳細取得"""
        try:
            doc = fitz.open(str(self.pdf_path))
            locator = PDFTextLocator(doc)
            
            # 文字詳細取得
            char_details = locator.get_character_details(start, end)
            
            doc.close()
            return char_details
            
        except Exception as e:
            logger.error(f"文字レベル座標取得エラー: {e}")
            return {"error": str(e)}
    
    def _generate_statistics(self, pii_results):
        """統計情報生成"""
        try:
            stats = {
                "total_pii_count": len(pii_results),
                "entity_type_distribution": {},
                "confidence_score_stats": {
                    "average": 0.0,
                    "min": 1.0,
                    "max": 0.0,
                    "scores": []
                },
                "page_distribution": {},
                "coordinate_coverage": {
                    "with_coordinates": 0,
                    "without_coordinates": 0
                }
            }
            
            scores = []
            for pii in pii_results:
                # エンティティタイプ分布
                entity_type = pii.get("entity_type", "UNKNOWN")
                stats["entity_type_distribution"][entity_type] = stats["entity_type_distribution"].get(entity_type, 0) + 1
                
                # 信頼度スコア
                score = pii.get("score", 0.0)
                scores.append(score)
                
                # ページ分布
                page_num = pii.get("page_info", {}).get("page_number", 0)
                stats["page_distribution"][f"page_{page_num}"] = stats["page_distribution"].get(f"page_{page_num}", 0) + 1
                
                # 座標カバレッジ
                if pii.get("coordinates"):
                    stats["coordinate_coverage"]["with_coordinates"] += 1
                else:
                    stats["coordinate_coverage"]["without_coordinates"] += 1
            
            # 信頼度統計計算
            if scores:
                stats["confidence_score_stats"]["average"] = sum(scores) / len(scores)
                stats["confidence_score_stats"]["min"] = min(scores)
                stats["confidence_score_stats"]["max"] = max(scores)
                stats["confidence_score_stats"]["scores"] = scores
            
            return stats
            
        except Exception as e:
            logger.error(f"統計情報生成エラー: {e}")
            return {"error": str(e)}
    
    def save_analysis_results(self, analysis_results, filename_suffix=""):
        """解析結果をJSONファイルに保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"b1_pii_analysis{filename_suffix}_{timestamp}.json"
        output_path = self.output_dir / filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"解析結果保存完了: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"解析結果保存エラー: {e}")
            raise
    
    def run_complete_analysis(self):
        """完全解析実行"""
        logger.info("=== b1.pdf完全PII解析開始 ===")
        
        try:
            # PII解析実行
            analysis_results = self.analyze_b1_pdf()
            
            # 結果保存
            output_path = self.save_analysis_results(analysis_results, "_detailed")
            
            # 結果サマリー表示
            self._display_analysis_summary(analysis_results)
            
            logger.info(f"=== b1.pdf完全PII解析完了 ===")
            logger.info(f"詳細結果: {output_path}")
            
            return analysis_results, output_path
            
        except Exception as e:
            logger.error(f"完全解析エラー: {e}")
            raise
    
    def _display_analysis_summary(self, results):
        """解析結果サマリー表示"""
        print("\n" + "="*60)
        print("b1.pdf PII解析結果サマリー")
        print("="*60)
        
        analysis_info = results.get("analysis_info", {})
        statistics = results.get("statistics", {})
        
        print(f"PDFファイル: {analysis_info.get('pdf_file', 'N/A')}")
        print(f"解析日時: {analysis_info.get('analysis_timestamp', 'N/A')}")
        print(f"検出PII総数: {analysis_info.get('total_pii_found', 0)}")
        print(f"有効エンティティ: {', '.join(analysis_info.get('enabled_entities', []))}")
        
        print("\n--- エンティティタイプ別検出数 ---")
        entity_dist = statistics.get("entity_type_distribution", {})
        for entity_type, count in entity_dist.items():
            print(f"  {entity_type}: {count}件")
        
        print("\n--- 信頼度スコア統計 ---")
        score_stats = statistics.get("confidence_score_stats", {})
        print(f"  平均: {score_stats.get('average', 0):.3f}")
        print(f"  最小: {score_stats.get('min', 0):.3f}")
        print(f"  最大: {score_stats.get('max', 0):.3f}")
        
        print("\n--- 座標情報カバレッジ ---")
        coord_coverage = statistics.get("coordinate_coverage", {})
        print(f"  座標あり: {coord_coverage.get('with_coordinates', 0)}件")
        print(f"  座標なし: {coord_coverage.get('without_coordinates', 0)}件")
        
        print("="*60)

def main():
    """メイン実行関数"""
    try:
        analyzer = B1PIIAnalyzer()
        results, output_path = analyzer.run_complete_analysis()
        
        print(f"\n✅ 解析完了！")
        print(f"📄 詳細結果: {output_path}")
        
        return results
        
    except Exception as e:
        logger.error(f"メイン実行エラー: {e}")
        print(f"\n❌ エラー: {e}")
        raise

if __name__ == "__main__":
    main()