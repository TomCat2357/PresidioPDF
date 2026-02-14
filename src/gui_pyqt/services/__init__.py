"""
PresidioPDF PyQt - Services

Phase 2: 既存CLIロジックの再利用
- read/detect/mask等の処理を呼び出し可能な形で提供
"""

from .pipeline_service import PipelineService

__all__ = ["PipelineService"]
