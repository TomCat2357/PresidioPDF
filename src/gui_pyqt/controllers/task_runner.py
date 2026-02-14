"""
PresidioPDF PyQt - 非同期タスク実行基盤

Phase 2: Worker/QThreadパターン（Context7準拠）
- QObjectベースのWorkerをQThreadに移動
- Signal/Slotで進捗・完了・エラーを通知
- 長時間処理をUIスレッドから分離

Phase 5: エラーハンドリング強化
- 詳細なエラー情報（スタックトレース）
- ロギング機能の追加
- エラータイプごとの処理
"""

import logging
import traceback
from typing import Any, Callable, Optional
from PyQt6.QtCore import QObject, QThread, pyqtSignal

# ロガーの設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class GenericWorker(QObject):
    """汎用Worker（QObject継承）

    Context7パターンに従い、moveToThread()でQThreadに移動して使用。
    実行する処理は外部から関数として渡す。

    Phase 5: エラーハンドリング強化
    - 詳細なエラー情報をログに記録
    - スタックトレースの保持
    """

    # シグナル定義
    progress = pyqtSignal(int, str)  # (進捗率 0-100, メッセージ)
    finished = pyqtSignal(object)    # 完了時の結果（dict, list, etc.）
    error = pyqtSignal(str)          # エラーメッセージ

    def __init__(self, task_func: Callable, task_name: str = None, *args, **kwargs):
        """
        Args:
            task_func: 実行する処理（Callable）
            task_name: タスク名（ログ用、省略時は関数名を使用）
            *args, **kwargs: task_funcに渡す引数
        """
        super().__init__()
        self.task_func = task_func
        self.task_name = task_name or getattr(task_func, '__name__', 'UnknownTask')
        self.args = args
        self.kwargs = kwargs
        self._is_cancelled = False
        self.error_traceback: Optional[str] = None

    def run(self):
        """タスクを実行（QThreadのstartedシグナルから呼び出される）

        Phase 5: エラーハンドリング強化
        - スタックトレースの記録
        - 詳細なログ出力
        - エラータイプごとの処理
        """
        try:
            logger.info(f"タスク開始: {self.task_name}")

            # 進捗通知: 開始
            self.progress.emit(0, f"{self.task_name}: 処理を開始しています...")

            # 実際の処理を実行
            result = self.task_func(*self.args, **self.kwargs)

            # キャンセルチェック
            if self._is_cancelled:
                logger.warning(f"タスクがキャンセルされました: {self.task_name}")
                self.error.emit("処理がキャンセルされました")
                return

            # 進捗通知: 完了
            self.progress.emit(100, f"{self.task_name}: 処理が完了しました")

            logger.info(f"タスク完了: {self.task_name}")

            # 結果を通知
            self.finished.emit(result)

        except FileNotFoundError as e:
            # ファイル関連のエラー
            self.error_traceback = traceback.format_exc()
            error_msg = f"ファイルが見つかりません: {str(e)}"
            logger.error(f"タスクエラー ({self.task_name}): {error_msg}\n{self.error_traceback}")
            self.error.emit(error_msg)

        except PermissionError as e:
            # 権限エラー
            self.error_traceback = traceback.format_exc()
            error_msg = f"ファイルへのアクセス権限がありません: {str(e)}"
            logger.error(f"タスクエラー ({self.task_name}): {error_msg}\n{self.error_traceback}")
            self.error.emit(error_msg)

        except ValueError as e:
            # 値エラー（不正な入力など）
            self.error_traceback = traceback.format_exc()
            error_msg = f"不正な値です: {str(e)}"
            logger.error(f"タスクエラー ({self.task_name}): {error_msg}\n{self.error_traceback}")
            self.error.emit(error_msg)

        except Exception as e:
            # その他のエラー
            self.error_traceback = traceback.format_exc()
            error_msg = f"エラーが発生しました ({type(e).__name__}): {str(e)}"
            logger.error(f"タスクエラー ({self.task_name}): {error_msg}\n{self.error_traceback}")
            self.error.emit(error_msg)

    def cancel(self):
        """タスクのキャンセル（フラグ設定のみ）"""
        self._is_cancelled = True


class TaskRunner(QObject):
    """タスク実行管理クラス

    WorkerをQThreadに移動して実行を管理する。
    Context7推奨パターン: moveToThread()を使用。
    """

    # シグナル定義（Workerから転送）
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    started = pyqtSignal()  # タスク開始時
    running_state_changed = pyqtSignal(bool)  # 実行状態の変化（True=実行中）

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.thread: Optional[QThread] = None
        self.worker: Optional[GenericWorker] = None
        self._is_running = False

    def is_running(self) -> bool:
        """実行中かどうか"""
        return self._is_running

    def start_task(self, task_func: Callable, *args, task_name: str = None, **kwargs):
        """タスクを開始

        Args:
            task_func: 実行する処理（Callable）
            *args: task_funcに渡す位置引数
            task_name: タスク名（省略時は関数名を使用）
            **kwargs: task_funcに渡すキーワード引数
        """
        if self._is_running:
            logger.warning("タスク開始失敗: 別のタスクが実行中です")
            self.error.emit("別のタスクが実行中です")
            return

        # タスク名を取得
        name = task_name or getattr(task_func, '__name__', 'UnknownTask')
        logger.info(f"新しいタスクを開始: {name}")

        # QThreadとWorkerを作成
        self.thread = QThread()
        self.worker = GenericWorker(task_func, name, *args, **kwargs)

        # WorkerをQThreadに移動（Context7パターン）
        self.worker.moveToThread(self.thread)

        # Signal/Slot接続
        # スレッド開始時にWorkerのrunを実行
        self.thread.started.connect(self.worker.run)

        # Workerのシグナルを転送
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)

        # スレッド終了時のクリーンアップ
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup)

        # Workerの削除をスレッド終了時に設定
        self.thread.finished.connect(self.worker.deleteLater)

        # 実行状態を設定
        self._is_running = True
        self.started.emit()
        self.running_state_changed.emit(True)

        # スレッドを開始
        self.thread.start()

    def stop_task(self):
        """タスクを停止（キャンセル要求）

        Phase 5: ログ追加
        """
        logger.info("タスク停止要求")

        if self.worker:
            task_name = getattr(self.worker, 'task_name', 'Unknown')
            logger.info(f"タスクのキャンセル: {task_name}")
            self.worker.cancel()

        if self.thread and self.thread.isRunning():
            self.thread.quit()
            if not self.thread.wait(5000):  # 5秒タイムアウト
                logger.warning("スレッドの終了タイムアウト")
                self.thread.terminate()
                self.thread.wait()

    def _on_progress(self, percent: int, message: str):
        """進捗通知を転送"""
        self.progress.emit(percent, message)

    def _on_finished(self, result: Any):
        """完了通知を転送"""
        self.finished.emit(result)

    def _on_error(self, error_msg: str):
        """エラー通知を転送"""
        self.error.emit(error_msg)

    def _cleanup(self):
        """スレッド終了後のクリーンアップ"""
        self._is_running = False
        self.running_state_changed.emit(False)
        if self.thread:
            self.thread.deleteLater()
            self.thread = None
        self.worker = None


class ProgressCallback:
    """進捗通知用のコールバッククラス

    Workerから渡された関数内で進捗を通知するために使用。

    使用例:
        def my_task(progress_callback):
            for i in range(10):
                progress_callback.report(i * 10, f"ステップ {i}")
                # 処理...
            return result

        runner.start_task(my_task, ProgressCallback(worker))
    """

    def __init__(self, worker: GenericWorker):
        self.worker = worker

    def report(self, percent: int, message: str):
        """進捗を報告"""
        if self.worker:
            self.worker.progress.emit(percent, message)
