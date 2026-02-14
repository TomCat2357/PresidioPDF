"""
PresidioPDF PyQt - Controllers

Phase 2: 非同期実行基盤
- Worker/QThreadパターン
- 長時間処理のUIスレッド分離
"""

from .task_runner import TaskRunner, GenericWorker

__all__ = ["TaskRunner", "GenericWorker"]
