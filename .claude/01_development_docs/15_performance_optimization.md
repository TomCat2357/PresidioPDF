# パフォーマンス最適化設計

## 概要
PresidioPDFの性能要件を達成するための最適化戦略を定義する。処理速度、メモリ効率、スループット、レスポンス性能の向上を図り、ユーザビリティを最大化する。

## 性能要件定義

### パフォーマンス目標
```python
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class PerformanceTargets:
    """性能目標値"""
    
    # 処理性能
    max_processing_time_per_page: float = 3.0  # 秒/ページ
    max_file_size_mb: int = 50                 # MB
    concurrent_processing_limit: int = 5       # 同時処理数
    
    # メモリ使用量
    max_memory_per_process_gb: float = 2.0     # GB
    memory_leak_threshold_mb: int = 100        # MB
    
    # レスポンス性能
    api_response_time_ms: int = 500           # ms
    file_upload_time_per_mb_sec: float = 2.0  # 秒/MB
    
    # スループット
    requests_per_second: int = 100            # RPS
    concurrent_users: int = 50                # 同時ユーザー数
    
    # Core Web Vitals
    largest_contentful_paint_ms: int = 2500   # ms
    first_input_delay_ms: int = 100           # ms
    cumulative_layout_shift: float = 0.1     # CLS
```

## PDF処理最適化

### ストリーミング処理実装
```python
# ストリーミング処理による大容量PDF対応
import asyncio
from typing import AsyncIterator, List, Optional
import fitz  # PyMuPDF
from concurrent.futures import ThreadPoolExecutor
import psutil

class StreamingPDFProcessor:
    """ストリーミングPDF処理"""
    
    def __init__(self, max_workers: int = 4, chunk_size: int = 5):
        self.max_workers = max_workers
        self.chunk_size = chunk_size  # 一度に処理するページ数
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
    async def process_pdf_stream(
        self,
        pdf_path: str,
        config: ProcessingConfig,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> AsyncIterator[ProcessingChunk]:
        """PDFをチャンク単位でストリーミング処理"""
        
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        processed_pages = 0
        
        try:
            # チャンク単位で処理
            for start_page in range(0, total_pages, self.chunk_size):
                end_page = min(start_page + self.chunk_size, total_pages)
                
                # 非同期でチャンク処理
                chunk_result = await self._process_chunk(
                    doc, start_page, end_page, config
                )
                
                processed_pages += (end_page - start_page)
                
                # 進捗報告
                if progress_callback:
                    progress = (processed_pages / total_pages) * 100
                    progress_callback(progress)
                
                yield chunk_result
                
                # メモリ監視・制御
                await self._memory_check_and_cleanup()
                
        finally:
            doc.close()
    
    async def _process_chunk(
        self,
        doc: fitz.Document,
        start_page: int,
        end_page: int,
        config: ProcessingConfig
    ) -> ProcessingChunk:
        """ページチャンク処理"""
        
        loop = asyncio.get_event_loop()
        
        # CPU集約的処理を別スレッドで実行
        return await loop.run_in_executor(
            self.executor,
            self._process_chunk_sync,
            doc, start_page, end_page, config
        )
    
    def _process_chunk_sync(
        self,
        doc: fitz.Document,
        start_page: int,
        end_page: int,
        config: ProcessingConfig
    ) -> ProcessingChunk:
        """同期チャンク処理"""
        
        entities = []
        
        for page_num in range(start_page, end_page):
            page = doc[page_num]
            text = page.get_text()
            
            # ページ単位でエンティティ検出
            page_entities = self._analyze_page_text(text, page_num + 1, config)
            entities.extend(page_entities)
        
        return ProcessingChunk(
            start_page=start_page,
            end_page=end_page,
            entities=entities,
            processing_time=time.time()
        )
    
    async def _memory_check_and_cleanup(self):
        """メモリ監視・クリーンアップ"""
        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        if memory_usage > 1500:  # 1.5GB閾値
            # ガベージコレクション強制実行
            import gc
            gc.collect()
            
            # 少し待機してメモリ解放を待つ
            await asyncio.sleep(0.1)
```

### spaCy モデル最適化
```python
# spaCy処理最適化
import spacy
from spacy.lang.ja import Japanese
from typing import List, Generator, Tuple
import threading
from queue import Queue

class OptimizedNLPProcessor:
    """最適化されたNLP処理"""
    
    def __init__(self, model_name: str = "ja_core_news_sm", batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size
        self.nlp = None
        self._model_lock = threading.Lock()
        
        # モデルの遅延読み込み
        self._initialize_model()
        
    def _initialize_model(self):
        """モデル初期化（最適化設定）"""
        with self._model_lock:
            if self.nlp is None:
                self.nlp = spacy.load(self.model_name)
                
                # 不要なコンポーネント無効化（高速化）
                disabled_components = ['tagger', 'parser', 'lemmatizer']
                for component in disabled_components:
                    if component in self.nlp.pipe_names:
                        self.nlp.disable_pipe(component)
                
                # バッチ処理最適化
                if hasattr(self.nlp, 'max_length'):
                    self.nlp.max_length = 2000000  # 大容量テキスト対応
    
    def process_texts_batch(self, texts: List[str]) -> List[List[EntityDetection]]:
        """バッチ処理によるテキスト解析"""
        results = []
        
        # バッチサイズ単位で処理
        for batch_start in range(0, len(texts), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(texts))
            batch_texts = texts[batch_start:batch_end]
            
            # spaCy pipe処理（高速化）
            docs = list(self.nlp.pipe(
                batch_texts,
                batch_size=self.batch_size,
                n_process=1  # GIL考慮
            ))
            
            # エンティティ抽出
            for doc in docs:
                entities = self._extract_entities(doc)
                results.append(entities)
        
        return results
    
    def _extract_entities(self, doc) -> List[EntityDetection]:
        """エンティティ抽出（最適化版）"""
        entities = []
        
        # 事前計算されたエンティティリスト使用
        for ent in doc.ents:
            if self._is_target_entity(ent.label_):
                entity = EntityDetection(
                    entity_type=ent.label_,
                    text=ent.text,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=self._calculate_confidence_fast(ent),
                    page=1,  # ページ情報は別途設定
                    coordinates=Coordinates(x=0, y=0, width=0, height=0)
                )
                entities.append(entity)
        
        return entities
    
    def _calculate_confidence_fast(self, ent) -> float:
        """高速信頼度計算"""
        # 簡易信頼度計算（詳細計算は必要時のみ）
        base_confidence = 0.8
        
        # エンティティタイプ別調整
        type_multipliers = {
            'PERSON': 1.0,
            'ORG': 0.9,
            'GPE': 0.95,
            'PHONE': 1.0,
            'EMAIL': 1.0
        }
        
        multiplier = type_multipliers.get(ent.label_, 0.8)
        return min(base_confidence * multiplier, 1.0)
    
    def preload_model_cache(self):
        """モデルキャッシュ事前読み込み"""
        # ダミーテキストで初期化実行
        dummy_text = "これはテストです。田中太郎さんの連絡先は03-1234-5678です。"
        list(self.nlp.pipe([dummy_text]))
```

### PyMuPDF最適化
```python
# PyMuPDF最適化処理
import fitz
from typing import List, Dict, Any, Optional
import concurrent.futures
from contextlib import contextmanager

class OptimizedPDFHandler:
    """最適化PDF処理"""
    
    def __init__(self):
        self.text_cache = {}
        self.coordinate_cache = {}
        
    @contextmanager
    def open_pdf_optimized(self, pdf_path: str):
        """最適化PDF開く"""
        doc = None
        try:
            doc = fitz.open(pdf_path)
            # メモリマップ有効化
            doc.set_metadata({})  # メタデータ削除でメモリ削減
            yield doc
        finally:
            if doc:
                doc.close()
    
    def extract_text_parallel(self, doc: fitz.Document, max_workers: int = 4) -> Dict[int, str]:
        """並列テキスト抽出"""
        page_count = len(doc)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # ページ単位で並列処理
            future_to_page = {
                executor.submit(self._extract_page_text, doc, page_num): page_num
                for page_num in range(page_count)
            }
            
            results = {}
            for future in concurrent.futures.as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    text = future.result()
                    results[page_num] = text
                except Exception as e:
                    logging.error(f"Page {page_num} text extraction failed: {e}")
                    results[page_num] = ""
        
        return results
    
    def _extract_page_text(self, doc: fitz.Document, page_num: int) -> str:
        """ページテキスト抽出（キャッシュ付き）"""
        cache_key = f"{doc.name}_{page_num}"
        
        if cache_key in self.text_cache:
            return self.text_cache[cache_key]
        
        try:
            page = doc[page_num]
            # OCRオプション指定（必要時のみ）
            text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            
            # キャッシュ保存（サイズ制限付き）
            if len(self.text_cache) < 1000:  # キャッシュサイズ制限
                self.text_cache[cache_key] = text
            
            return text
            
        except Exception as e:
            logging.error(f"Text extraction error on page {page_num}: {e}")
            return ""
    
    def find_text_coordinates_optimized(
        self, 
        doc: fitz.Document, 
        entities: List[EntityDetection]
    ) -> List[EntityDetection]:
        """最適化テキスト座標検索"""
        
        # ページごとにエンティティをグループ化
        page_entities = {}
        for entity in entities:
            page_num = entity.page - 1  # 0ベースに変換
            if page_num not in page_entities:
                page_entities[page_num] = []
            page_entities[page_num].append(entity)
        
        updated_entities = []
        
        for page_num, page_entity_list in page_entities.items():
            try:
                page = doc[page_num]
                
                # ページ内の全テキストブロック取得（一度だけ）
                text_instances = page.search_for("")  # 全テキスト取得
                
                for entity in page_entity_list:
                    # 高速文字列検索
                    coordinates = self._find_text_coordinates_fast(
                        page, entity.text, text_instances
                    )
                    
                    if coordinates:
                        entity.coordinates = coordinates
                    
                    updated_entities.append(entity)
                    
            except Exception as e:
                logging.error(f"Coordinate search error on page {page_num}: {e}")
                updated_entities.extend(page_entity_list)
        
        return updated_entities
    
    def _find_text_coordinates_fast(
        self, 
        page: fitz.Page, 
        text: str, 
        text_instances: Optional[List] = None
    ) -> Optional[Coordinates]:
        """高速座標検索"""
        
        try:
            # 直接座標検索
            rects = page.search_for(text)
            
            if rects:
                rect = rects[0]  # 最初のマッチを使用
                return Coordinates(
                    x=rect.x0,
                    y=rect.y0,
                    width=rect.width,
                    height=rect.height
                )
            
            # 部分マッチ検索（フォールバック）
            if len(text) > 10:
                partial_text = text[:10]
                partial_rects = page.search_for(partial_text)
                if partial_rects:
                    rect = partial_rects[0]
                    return Coordinates(
                        x=rect.x0,
                        y=rect.y0,
                        width=rect.width * (len(text) / len(partial_text)),
                        height=rect.height
                    )
            
        except Exception as e:
            logging.debug(f"Text coordinate search failed: {e}")
        
        return None
    
    def apply_annotations_batch(
        self, 
        doc: fitz.Document, 
        entities: List[EntityDetection],
        annotation_style: Dict[str, Any] = None
    ) -> bool:
        """バッチアノテーション適用"""
        
        if not annotation_style:
            annotation_style = {
                'fill_color': (1, 1, 0),    # 黄色
                'border_color': (1, 0.5, 0),  # オレンジ
                'opacity': 0.7
            }
        
        try:
            # ページごとにアノテーションをグループ化
            page_annotations = {}
            for entity in entities:
                page_num = entity.page - 1
                if page_num not in page_annotations:
                    page_annotations[page_num] = []
                page_annotations[page_num].append(entity)
            
            # ページ単位で一括処理
            for page_num, page_entities in page_annotations.items():
                page = doc[page_num]
                
                for entity in page_entities:
                    if entity.coordinates:
                        rect = fitz.Rect(
                            entity.coordinates.x,
                            entity.coordinates.y,
                            entity.coordinates.x + entity.coordinates.width,
                            entity.coordinates.y + entity.coordinates.height
                        )
                        
                        # アノテーション追加
                        annot = page.add_highlight_annot(rect)
                        annot.set_colors(
                            fill=annotation_style['fill_color'],
                            stroke=annotation_style['border_color']
                        )
                        annot.set_opacity(annotation_style['opacity'])
                        annot.update()
            
            return True
            
        except Exception as e:
            logging.error(f"Batch annotation failed: {e}")
            return False
```

## メモリ最適化

### メモリプール・キャッシング戦略
```python
# メモリ最適化システム
import gc
import weakref
from typing import Dict, Any, Optional, Union
import threading
import psutil
from collections import OrderedDict

class MemoryOptimizer:
    """メモリ最適化管理"""
    
    def __init__(self, max_memory_mb: int = 1500):
        self.max_memory_mb = max_memory_mb
        self.memory_warning_threshold = max_memory_mb * 0.8
        self.object_pool = {}
        self.weak_references = weakref.WeakValueDictionary()
        self._lock = threading.Lock()
        
    def get_memory_usage(self) -> Dict[str, float]:
        """メモリ使用量取得"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }
    
    def check_memory_pressure(self) -> bool:
        """メモリプレッシャー確認"""
        current_memory = self.get_memory_usage()['rss_mb']
        return current_memory > self.memory_warning_threshold
    
    def optimize_memory_if_needed(self):
        """必要時メモリ最適化実行"""
        if self.check_memory_pressure():
            self.force_memory_cleanup()
    
    def force_memory_cleanup(self):
        """強制メモリクリーンアップ"""
        with self._lock:
            # オブジェクトプールクリア
            self.object_pool.clear()
            
            # 弱参照クリア
            self.weak_references.clear()
            
            # ガベージコレクション実行
            collected = gc.collect()
            
            logging.info(f"Memory cleanup completed. Collected {collected} objects.")
    
    @contextmanager
    def memory_monitor(self, operation_name: str):
        """メモリ監視コンテキスト"""
        start_memory = self.get_memory_usage()['rss_mb']
        
        try:
            yield
        finally:
            end_memory = self.get_memory_usage()['rss_mb']
            memory_delta = end_memory - start_memory
            
            logging.info(f"Operation '{operation_name}' memory delta: {memory_delta:.2f} MB")
            
            # 大量メモリ使用時は警告
            if memory_delta > 200:  # 200MB以上
                logging.warning(f"High memory usage detected: {memory_delta:.2f} MB")

class LRUCache:
    """LRU キャッシュ実装"""
    
    def __init__(self, maxsize: int = 1000, ttl_seconds: int = 3600):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()
        self.timestamps = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """キャッシュ取得"""
        with self._lock:
            if key not in self.cache:
                return None
            
            # TTL確認
            if self._is_expired(key):
                self._remove_key(key)
                return None
            
            # LRU更新
            value = self.cache.pop(key)
            self.cache[key] = value
            
            return value
    
    def put(self, key: str, value: Any):
        """キャッシュ保存"""
        with self._lock:
            # 既存キー更新
            if key in self.cache:
                self.cache.pop(key)
            
            # サイズ制限チェック
            while len(self.cache) >= self.maxsize:
                oldest_key = next(iter(self.cache))
                self._remove_key(oldest_key)
            
            # 新規追加
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def _is_expired(self, key: str) -> bool:
        """TTL期限切れ確認"""
        if key not in self.timestamps:
            return True
        
        return time.time() - self.timestamps[key] > self.ttl_seconds
    
    def _remove_key(self, key: str):
        """キー削除"""
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)
    
    def clear(self):
        """キャッシュクリア"""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計"""
        return {
            'size': len(self.cache),
            'maxsize': self.maxsize,
            'hit_ratio': getattr(self, '_hits', 0) / max(getattr(self, '_requests', 1), 1)
        }

# オブジェクトプール
class ObjectPool:
    """再利用オブジェクトプール"""
    
    def __init__(self, factory_func: Callable, max_size: int = 50):
        self.factory_func = factory_func
        self.max_size = max_size
        self.pool = []
        self._lock = threading.Lock()
    
    def acquire(self) -> Any:
        """オブジェクト取得"""
        with self._lock:
            if self.pool:
                return self.pool.pop()
            else:
                return self.factory_func()
    
    def release(self, obj: Any):
        """オブジェクト返却"""
        with self._lock:
            if len(self.pool) < self.max_size:
                # オブジェクトリセット
                if hasattr(obj, 'reset'):
                    obj.reset()
                self.pool.append(obj)
    
    @contextmanager
    def get_object(self):
        """オブジェクト取得コンテキスト"""
        obj = self.acquire()
        try:
            yield obj
        finally:
            self.release(obj)
```

## I/O最適化

### 非同期I/O・ファイル処理
```python
# 非同期I/O最適化
import asyncio
import aiofiles
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp

class AsyncFileProcessor:
    """非同期ファイル処理"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or mp.cpu_count()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
    
    async def read_file_chunks(self, file_path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """非同期チャンク読み込み"""
        async with aiofiles.open(file_path, 'rb') as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    
    async def process_file_async(self, file_path: str, processor_func: Callable) -> Any:
        """非同期ファイル処理"""
        loop = asyncio.get_event_loop()
        
        # CPU集約的処理を別スレッドで実行
        return await loop.run_in_executor(
            self.executor,
            processor_func,
            file_path
        )
    
    async def batch_file_operations(self, operations: List[Tuple[str, Callable]]) -> List[Any]:
        """バッチファイル操作"""
        tasks = []
        
        for file_path, processor_func in operations:
            task = self.process_file_async(file_path, processor_func)
            tasks.append(task)
        
        # 全タスク並行実行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return results

# ディスク最適化
class DiskOptimizer:
    """ディスク I/O 最適化"""
    
    def __init__(self, temp_dir: str = "/tmp/presidio"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        
    def create_memory_mapped_file(self, size_bytes: int) -> str:
        """メモリマップファイル作成"""
        temp_file = self.temp_dir / f"mmap_{secrets.token_hex(8)}.tmp"
        
        # スパースファイル作成
        with open(temp_file, 'wb') as f:
            f.seek(size_bytes - 1)
            f.write(b'\0')
        
        return str(temp_file)
    
    def cleanup_temp_files(self, max_age_hours: int = 24):
        """古い一時ファイル削除"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        for temp_file in self.temp_dir.glob("*.tmp"):
            try:
                if temp_file.stat().st_mtime < cutoff_time:
                    temp_file.unlink()
                    logging.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                logging.warning(f"Failed to cleanup {temp_file}: {e}")
    
    def optimize_file_access_pattern(self, file_path: str):
        """ファイルアクセスパターン最適化"""
        try:
            # ファイルシステムヒント設定（Linux）
            import os
            import fcntl
            
            with open(file_path, 'rb') as f:
                # シーケンシャル読み取りヒント
                fcntl.fcntl(f.fileno(), fcntl.F_SETFL, os.O_RDONLY)
                
                # プリフェッチ設定
                os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_SEQUENTIAL)
                
        except (AttributeError, OSError):
            # Windows or unsupported system
            pass
```

## ネットワーク・通信最適化

### HTTP/WebSocket最適化
```python
# ネットワーク最適化
from flask import Flask, request, Response, stream_template
import gzip
import json
from typing import Generator, Dict, Any

class NetworkOptimizer:
    """ネットワーク最適化"""
    
    def __init__(self, app: Flask):
        self.app = app
        self._setup_compression()
        self._setup_caching()
        self._setup_streaming()
    
    def _setup_compression(self):
        """圧縮設定"""
        @self.app.after_request
        def compress_response(response):
            # gzip圧縮対象
            compressible_types = [
                'application/json',
                'text/html',
                'text/css',
                'text/javascript',
                'application/javascript'
            ]
            
            if (response.content_type in compressible_types and
                'gzip' in request.headers.get('Accept-Encoding', '') and
                len(response.data) > 500):  # 500バイト以上で圧縮
                
                response.data = gzip.compress(response.data)
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = len(response.data)
            
            return response
    
    def _setup_caching(self):
        """キャッシュヘッダー設定"""
        @self.app.after_request
        def add_cache_headers(response):
            # 静的リソースキャッシュ
            if request.endpoint == 'static':
                response.headers['Cache-Control'] = 'public, max-age=86400'  # 1日
            
            # APIレスポンスキャッシュ制御
            elif request.path.startswith('/api/'):
                if request.method == 'GET':
                    response.headers['Cache-Control'] = 'public, max-age=300'  # 5分
                else:
                    response.headers['Cache-Control'] = 'no-cache'
            
            return response
    
    def _setup_streaming(self):
        """ストリーミングレスポンス設定"""
        
        def stream_json_response(data_generator: Generator[Dict[str, Any], None, None]) -> Response:
            """JSONストリーミングレスポンス"""
            def generate():
                yield '{"items":['
                first = True
                
                for item in data_generator:
                    if not first:
                        yield ','
                    yield json.dumps(item, ensure_ascii=False)
                    first = False
                
                yield ']}'
            
            return Response(
                generate(),
                content_type='application/json',
                headers={'Transfer-Encoding': 'chunked'}
            )
        
        self.stream_json_response = stream_json_response

# WebSocket最適化
import socketio

class OptimizedWebSocket:
    """WebSocket最適化"""
    
    def __init__(self):
        self.sio = socketio.Server(
            cors_allowed_origins="*",
            async_mode='threading',
            ping_timeout=60,
            ping_interval=25
        )
        
        self._setup_connection_pooling()
        self._setup_message_batching()
    
    def _setup_connection_pooling(self):
        """コネクションプール設定"""
        self.active_connections = {}
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_received': 0
        }
    
    def _setup_message_batching(self):
        """メッセージバッチング設定"""
        self.message_batch = {}
        self.batch_timer = None
        
        @self.sio.event
        async def connect(sid, environ):
            self.active_connections[sid] = {
                'connected_at': time.time(),
                'last_activity': time.time()
            }
            self.connection_stats['active_connections'] += 1
            
        @self.sio.event
        async def disconnect(sid):
            self.active_connections.pop(sid, None)
            self.connection_stats['active_connections'] -= 1
    
    def send_progress_batch(self, updates: List[Dict[str, Any]]):
        """進捗更新バッチ送信"""
        # 類似更新をまとめて送信（帯域幅節約）
        grouped_updates = {}
        
        for update in updates:
            key = f"{update.get('processing_id', 'unknown')}"
            if key not in grouped_updates:
                grouped_updates[key] = update
            else:
                # 最新の進捗で上書き
                grouped_updates[key].update(update)
        
        # バッチ送信
        for sid in self.active_connections:
            for update in grouped_updates.values():
                self.sio.emit('progress_update', update, room=sid)
```

## データベース・ストレージ最適化

### ファイルシステム最適化
```python
# ストレージ最適化
import sqlite3
import json
from pathlib import Path
import hashlib
import shutil

class OptimizedStorage:
    """最適化ストレージ"""
    
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True, parents=True)
        
        # SQLite最適化設定
        self.db_path = self.storage_dir / "presidio.db"
        self._setup_database()
    
    def _setup_database(self):
        """データベース最適化設定"""
        with sqlite3.connect(self.db_path) as conn:
            # SQLite最適化設定
            conn.execute('PRAGMA journal_mode=WAL')        # Write-Ahead Logging
            conn.execute('PRAGMA synchronous=NORMAL')      # 高速化
            conn.execute('PRAGMA temp_store=MEMORY')       # 一時データメモリ保存
            conn.execute('PRAGMA mmap_size=268435456')     # 256MB memory map
            conn.execute('PRAGMA cache_size=10000')        # キャッシュサイズ
            
            # インデックス作成
            conn.execute('''
                CREATE TABLE IF NOT EXISTS processing_cache (
                    file_hash TEXT PRIMARY KEY,
                    config_hash TEXT,
                    result_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_processing_cache_accessed 
                ON processing_cache(last_accessed)
            ''')
    
    def get_file_hash(self, file_path: str) -> str:
        """ファイルハッシュ計算（キャッシュキー用）"""
        hasher = hashlib.blake2b(digest_size=32)
        
        with open(file_path, 'rb') as f:
            # チャンク単位で読み込み（メモリ効率）
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def cache_processing_result(self, file_path: str, config: Dict[str, Any], 
                              result: ProcessingResult) -> bool:
        """処理結果キャッシュ"""
        try:
            file_hash = self.get_file_hash(file_path)
            config_hash = hashlib.md5(
                json.dumps(config, sort_keys=True).encode()
            ).hexdigest()
            
            result_json = json.dumps(result.to_dict(), ensure_ascii=False)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO processing_cache 
                    (file_hash, config_hash, result_data, last_accessed)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (file_hash, config_hash, result_json))
            
            return True
            
        except Exception as e:
            logging.error(f"Cache save failed: {e}")
            return False
    
    def get_cached_result(self, file_path: str, config: Dict[str, Any]) -> Optional[ProcessingResult]:
        """キャッシュ結果取得"""
        try:
            file_hash = self.get_file_hash(file_path)
            config_hash = hashlib.md5(
                json.dumps(config, sort_keys=True).encode()
            ).hexdigest()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT result_data FROM processing_cache 
                    WHERE file_hash = ? AND config_hash = ?
                ''', (file_hash, config_hash))
                
                row = cursor.fetchone()
                if row:
                    # アクセス時刻更新
                    conn.execute('''
                        UPDATE processing_cache 
                        SET last_accessed = CURRENT_TIMESTAMP 
                        WHERE file_hash = ? AND config_hash = ?
                    ''', (file_hash, config_hash))
                    
                    result_data = json.loads(row[0])
                    return ProcessingResult.from_dict(result_data)
            
            return None
            
        except Exception as e:
            logging.error(f"Cache retrieval failed: {e}")
            return None
    
    def cleanup_old_cache(self, max_age_days: int = 30):
        """古いキャッシュクリーンアップ"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                DELETE FROM processing_cache 
                WHERE last_accessed < datetime('now', '-{} days')
            '''.format(max_age_days))
    
    def optimize_file_storage(self, file_path: str) -> str:
        """ファイルストレージ最適化"""
        # ファイル重複排除
        file_hash = self.get_file_hash(file_path)
        optimized_dir = self.storage_dir / "optimized"
        optimized_dir.mkdir(exist_ok=True)
        
        optimized_path = optimized_dir / f"{file_hash}.pdf"
        
        if not optimized_path.exists():
            # ハードリンク作成（可能な場合）
            try:
                optimized_path.hardlink_to(file_path)
            except OSError:
                # ハードリンク失敗時はコピー
                shutil.copy2(file_path, optimized_path)
        
        return str(optimized_path)
```