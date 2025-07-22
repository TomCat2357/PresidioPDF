# パフォーマンス監視設計

## 概要
PresidioPDFアプリケーションの性能監視・分析システムを設計する。リアルタイムメトリクス収集、アラート機能、性能分析ダッシュボードを通じて、システムの健全性とパフォーマンスを継続的に監視する。

## 監視アーキテクチャ

### 監視層設計
```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Callable
import time
import threading
import queue
import json

class MetricType(Enum):
    COUNTER = "counter"           # カウンタ（累積値）
    GAUGE = "gauge"              # ゲージ（瞬間値）
    HISTOGRAM = "histogram"       # ヒストグラム（分布）
    TIMER = "timer"              # タイマー（処理時間）

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class MetricPoint:
    """メトリクスデータポイント"""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str]
    metric_type: MetricType

@dataclass
class AlertRule:
    """アラートルール"""
    name: str
    metric_name: str
    condition: str              # >, <, ==, >=, <=
    threshold: float
    duration_seconds: int       # 持続時間
    severity: AlertSeverity
    enabled: bool = True
```

## メトリクス収集システム

### 基本メトリクス収集
```python
# メトリクス収集基盤
import psutil
import threading
from collections import defaultdict, deque
from contextlib import contextmanager
import functools

class MetricsCollector:
    """メトリクス収集システム"""
    
    def __init__(self, buffer_size: int = 10000):
        self.metrics_buffer = deque(maxlen=buffer_size)
        self.counters = defaultdict(float)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        self.timers = defaultdict(list)
        
        self._lock = threading.Lock()
        self._collection_thread = None
        self._stop_event = threading.Event()
        
        # システムメトリクス収集開始
        self.start_system_metrics_collection()
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """カウンタ増加"""
        with self._lock:
            self.counters[name] += value
            
        self._add_metric(name, value, MetricType.COUNTER, tags or {})
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """ゲージ設定"""
        with self._lock:
            self.gauges[name] = value
            
        self._add_metric(name, value, MetricType.GAUGE, tags or {})
    
    def add_histogram_value(self, name: str, value: float, tags: Dict[str, str] = None):
        """ヒストグラム値追加"""
        with self._lock:
            self.histograms[name].append(value)
            # 古いデータ制限（最新1000件）
            if len(self.histograms[name]) > 1000:
                self.histograms[name] = self.histograms[name][-1000:]
        
        self._add_metric(name, value, MetricType.HISTOGRAM, tags or {})
    
    def record_timer(self, name: str, duration: float, tags: Dict[str, str] = None):
        """タイマー記録"""
        with self._lock:
            self.timers[name].append(duration)
            # 古いデータ制限
            if len(self.timers[name]) > 1000:
                self.timers[name] = self.timers[name][-1000:]
        
        self._add_metric(name, duration, MetricType.TIMER, tags or {})
    
    @contextmanager
    def timer(self, name: str, tags: Dict[str, str] = None):
        """タイマーコンテキストマネージャ"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_timer(name, duration, tags)
    
    def _add_metric(self, name: str, value: float, metric_type: MetricType, tags: Dict[str, str]):
        """メトリクス追加"""
        metric = MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags,
            metric_type=metric_type
        )
        
        self.metrics_buffer.append(metric)
    
    def start_system_metrics_collection(self):
        """システムメトリクス収集開始"""
        if self._collection_thread and self._collection_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._collection_thread = threading.Thread(
            target=self._collect_system_metrics,
            daemon=True
        )
        self._collection_thread.start()
    
    def stop_system_metrics_collection(self):
        """システムメトリクス収集停止"""
        self._stop_event.set()
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
    
    def _collect_system_metrics(self):
        """システムメトリクス定期収集"""
        while not self._stop_event.wait(30):  # 30秒間隔
            try:
                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=1)
                self.set_gauge('system.cpu.usage_percent', cpu_percent, {'host': 'local'})
                
                # メモリ使用量
                memory = psutil.virtual_memory()
                self.set_gauge('system.memory.usage_percent', memory.percent, {'host': 'local'})
                self.set_gauge('system.memory.available_bytes', memory.available, {'host': 'local'})
                self.set_gauge('system.memory.used_bytes', memory.used, {'host': 'local'})
                
                # ディスク使用量
                disk = psutil.disk_usage('/')
                self.set_gauge('system.disk.usage_percent', (disk.used / disk.total) * 100, {'host': 'local'})
                self.set_gauge('system.disk.free_bytes', disk.free, {'host': 'local'})
                
                # ネットワーク統計
                network = psutil.net_io_counters()
                self.set_gauge('system.network.bytes_sent', network.bytes_sent, {'host': 'local'})
                self.set_gauge('system.network.bytes_recv', network.bytes_recv, {'host': 'local'})
                
            except Exception as e:
                logging.error(f"System metrics collection error: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """メトリクスサマリー取得"""
        with self._lock:
            summary = {
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'histograms': {},
                'timers': {}
            }
            
            # ヒストグラム統計
            for name, values in self.histograms.items():
                if values:
                    summary['histograms'][name] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'avg': sum(values) / len(values),
                        'p50': self._percentile(values, 50),
                        'p95': self._percentile(values, 95),
                        'p99': self._percentile(values, 99)
                    }
            
            # タイマー統計
            for name, values in self.timers.items():
                if values:
                    summary['timers'][name] = {
                        'count': len(values),
                        'min_ms': min(values) * 1000,
                        'max_ms': max(values) * 1000,
                        'avg_ms': (sum(values) / len(values)) * 1000,
                        'p50_ms': self._percentile(values, 50) * 1000,
                        'p95_ms': self._percentile(values, 95) * 1000,
                        'p99_ms': self._percentile(values, 99) * 1000
                    }
        
        return summary
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """パーセンタイル計算"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        
        return sorted_values[index]

# メトリクス収集デコレータ
def measure_performance(metric_name: str, tags: Dict[str, str] = None):
    """パフォーマンス測定デコレータ"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metrics_collector = get_metrics_collector()
            
            with metrics_collector.timer(metric_name, tags):
                try:
                    result = func(*args, **kwargs)
                    
                    # 成功カウンタ
                    success_tags = (tags or {}).copy()
                    success_tags['status'] = 'success'
                    metrics_collector.increment_counter(
                        f"{metric_name}.calls", 1.0, success_tags
                    )
                    
                    return result
                    
                except Exception as e:
                    # エラーカウンタ
                    error_tags = (tags or {}).copy()
                    error_tags['status'] = 'error'
                    error_tags['error_type'] = type(e).__name__
                    metrics_collector.increment_counter(
                        f"{metric_name}.calls", 1.0, error_tags
                    )
                    raise
        
        return wrapper
    return decorator

# グローバルメトリクス収集インスタンス
_metrics_collector = None

def get_metrics_collector() -> MetricsCollector:
    """グローバルメトリクス収集取得"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
```

### アプリケーション固有メトリクス
```python
# PresidioPDF固有メトリクス
class PresidioPDFMetrics:
    """PresidioPDF固有メトリクス"""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_file_upload(self, file_size_bytes: int, file_type: str, success: bool):
        """ファイルアップロード記録"""
        tags = {
            'file_type': file_type,
            'status': 'success' if success else 'error'
        }
        
        self.collector.increment_counter('presidio.file.upload.count', 1.0, tags)
        
        if success:
            self.collector.add_histogram_value(
                'presidio.file.upload.size_bytes', 
                float(file_size_bytes), 
                tags
            )
    
    def record_pdf_processing(self, pages: int, entities_detected: int, 
                            processing_time: float, model: str, success: bool):
        """PDF処理記録"""
        tags = {
            'spacy_model': model,
            'status': 'success' if success else 'error'
        }
        
        self.collector.increment_counter('presidio.processing.count', 1.0, tags)
        
        if success:
            self.collector.add_histogram_value(
                'presidio.processing.pages', float(pages), tags
            )
            self.collector.add_histogram_value(
                'presidio.processing.entities_detected', float(entities_detected), tags
            )
            self.collector.record_timer(
                'presidio.processing.duration', processing_time, tags
            )
            
            # ページあたり処理時間
            if pages > 0:
                time_per_page = processing_time / pages
                self.collector.add_histogram_value(
                    'presidio.processing.time_per_page', time_per_page, tags
                )
    
    def record_entity_detection(self, entity_type: str, confidence: float, 
                              detection_method: str):
        """エンティティ検出記録"""
        tags = {
            'entity_type': entity_type,
            'detection_method': detection_method
        }
        
        self.collector.increment_counter('presidio.entities.detected', 1.0, tags)
        self.collector.add_histogram_value(
            'presidio.entities.confidence', confidence, tags
        )
    
    def record_api_request(self, endpoint: str, method: str, status_code: int, 
                          response_time: float):
        """API リクエスト記録"""
        tags = {
            'endpoint': endpoint,
            'method': method,
            'status_code': str(status_code)
        }
        
        self.collector.increment_counter('presidio.api.requests', 1.0, tags)
        self.collector.record_timer('presidio.api.response_time', response_time, tags)
    
    def record_error(self, error_type: str, component: str, severity: str):
        """エラー記録"""
        tags = {
            'error_type': error_type,
            'component': component,
            'severity': severity
        }
        
        self.collector.increment_counter('presidio.errors.count', 1.0, tags)
    
    def record_cache_operation(self, operation: str, hit: bool, cache_type: str):
        """キャッシュ操作記録"""
        tags = {
            'operation': operation,
            'result': 'hit' if hit else 'miss',
            'cache_type': cache_type
        }
        
        self.collector.increment_counter('presidio.cache.operations', 1.0, tags)
    
    def get_business_metrics(self) -> Dict[str, Any]:
        """ビジネスメトリクス取得"""
        summary = self.collector.get_metrics_summary()
        
        # ビジネス指標計算
        business_metrics = {}
        
        # 処理成功率
        success_count = summary.get('counters', {}).get('presidio.processing.count', {})
        if isinstance(success_count, dict):
            total_success = sum(v for k, v in success_count.items() if 'success' in k)
            total_error = sum(v for k, v in success_count.items() if 'error' in k)
            total_requests = total_success + total_error
            
            if total_requests > 0:
                business_metrics['processing_success_rate'] = total_success / total_requests
        
        # 平均処理時間
        processing_times = summary.get('timers', {}).get('presidio.processing.duration', {})
        if processing_times:
            business_metrics['avg_processing_time_ms'] = processing_times.get('avg_ms', 0)
        
        # エンティティ検出統計
        entities_detected = summary.get('histograms', {}).get('presidio.processing.entities_detected', {})
        if entities_detected:
            business_metrics['avg_entities_per_document'] = entities_detected.get('avg', 0)
        
        return business_metrics
```

## アラートシステム

### アラート管理
```python
# アラートシステム
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import json

class AlertManager:
    """アラート管理システム"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules = []
        self.alert_history = deque(maxlen=1000)
        self.active_alerts = {}
        
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        
        # 通知チャネル設定
        self.notification_channels = {
            'email': self._send_email_alert,
            'slack': self._send_slack_alert,
            'webhook': self._send_webhook_alert
        }
        
        # デフォルトアラートルール設定
        self._setup_default_alert_rules()
    
    def _setup_default_alert_rules(self):
        """デフォルトアラートルール設定"""
        default_rules = [
            AlertRule(
                name="high_cpu_usage",
                metric_name="system.cpu.usage_percent",
                condition=">",
                threshold=80.0,
                duration_seconds=300,  # 5分間
                severity=AlertSeverity.WARNING
            ),
            AlertRule(
                name="high_memory_usage",
                metric_name="system.memory.usage_percent",
                condition=">",
                threshold=90.0,
                duration_seconds=300,
                severity=AlertSeverity.ERROR
            ),
            AlertRule(
                name="processing_failure_rate",
                metric_name="presidio.processing.error_rate",
                condition=">",
                threshold=0.1,  # 10%
                duration_seconds=600,  # 10分間
                severity=AlertSeverity.ERROR
            ),
            AlertRule(
                name="slow_processing",
                metric_name="presidio.processing.duration.p95_ms",
                condition=">",
                threshold=30000,  # 30秒
                duration_seconds=300,
                severity=AlertSeverity.WARNING
            )
        ]
        
        for rule in default_rules:
            self.add_alert_rule(rule)
    
    def add_alert_rule(self, rule: AlertRule):
        """アラートルール追加"""
        self.alert_rules.append(rule)
        logging.info(f"Alert rule added: {rule.name}")
    
    def remove_alert_rule(self, rule_name: str):
        """アラートルール削除"""
        self.alert_rules = [r for r in self.alert_rules if r.name != rule_name]
        logging.info(f"Alert rule removed: {rule_name}")
    
    def start_monitoring(self):
        """監視開始"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitor_alerts,
            daemon=True
        )
        self._monitoring_thread.start()
        logging.info("Alert monitoring started")
    
    def stop_monitoring(self):
        """監視停止"""
        self._stop_monitoring.set()
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10)
        logging.info("Alert monitoring stopped")
    
    def _monitor_alerts(self):
        """アラート監視ループ"""
        while not self._stop_monitoring.wait(60):  # 1分間隔
            try:
                self._check_alert_conditions()
            except Exception as e:
                logging.error(f"Alert monitoring error: {e}")
    
    def _check_alert_conditions(self):
        """アラート条件チェック"""
        current_metrics = self.metrics_collector.get_metrics_summary()
        current_time = time.time()
        
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            # メトリクス値取得
            metric_value = self._get_metric_value(current_metrics, rule.metric_name)
            
            if metric_value is None:
                continue
            
            # 条件チェック
            condition_met = self._evaluate_condition(
                metric_value, rule.condition, rule.threshold
            )
            
            alert_key = f"{rule.name}_{rule.metric_name}"
            
            if condition_met:
                # アラート状態の管理
                if alert_key not in self.active_alerts:
                    self.active_alerts[alert_key] = {
                        'rule': rule,
                        'start_time': current_time,
                        'metric_value': metric_value,
                        'notified': False
                    }
                else:
                    # 継続時間チェック
                    alert_info = self.active_alerts[alert_key]
                    duration = current_time - alert_info['start_time']
                    
                    if duration >= rule.duration_seconds and not alert_info['notified']:
                        # アラート発火
                        self._fire_alert(rule, metric_value, duration)
                        alert_info['notified'] = True
            else:
                # アラート解除
                if alert_key in self.active_alerts:
                    alert_info = self.active_alerts[alert_key]
                    if alert_info['notified']:
                        self._resolve_alert(rule, metric_value)
                    del self.active_alerts[alert_key]
    
    def _get_metric_value(self, metrics: Dict[str, Any], metric_name: str) -> Optional[float]:
        """メトリクス値取得"""
        # ドット記法でのメトリクス取得
        parts = metric_name.split('.')
        current = metrics
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        if isinstance(current, (int, float)):
            return float(current)
        
        return None
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """条件評価"""
        if condition == '>':
            return value > threshold
        elif condition == '<':
            return value < threshold
        elif condition == '>=':
            return value >= threshold
        elif condition == '<=':
            return value <= threshold
        elif condition == '==':
            return abs(value - threshold) < 0.0001  # 浮動小数点比較
        
        return False
    
    def _fire_alert(self, rule: AlertRule, metric_value: float, duration: float):
        """アラート発火"""
        alert_data = {
            'rule_name': rule.name,
            'metric_name': rule.metric_name,
            'metric_value': metric_value,
            'threshold': rule.threshold,
            'condition': rule.condition,
            'severity': rule.severity.value,
            'duration': duration,
            'timestamp': time.time(),
            'status': 'fired'
        }
        
        self.alert_history.append(alert_data)
        
        # 通知送信
        self._send_notifications(alert_data)
        
        logging.warning(
            f"ALERT FIRED: {rule.name} - {rule.metric_name} {rule.condition} {rule.threshold} "
            f"(current: {metric_value:.2f}, duration: {duration:.1f}s)"
        )
    
    def _resolve_alert(self, rule: AlertRule, metric_value: float):
        """アラート解除"""
        alert_data = {
            'rule_name': rule.name,
            'metric_name': rule.metric_name,
            'metric_value': metric_value,
            'severity': rule.severity.value,
            'timestamp': time.time(),
            'status': 'resolved'
        }
        
        self.alert_history.append(alert_data)
        
        # 解除通知送信
        self._send_notifications(alert_data)
        
        logging.info(f"ALERT RESOLVED: {rule.name} - current value: {metric_value:.2f}")
    
    def _send_notifications(self, alert_data: Dict[str, Any]):
        """通知送信"""
        for channel_name, send_func in self.notification_channels.items():
            try:
                send_func(alert_data)
            except Exception as e:
                logging.error(f"Failed to send {channel_name} notification: {e}")
    
    def _send_email_alert(self, alert_data: Dict[str, Any]):
        """メール通知"""
        # 環境変数から設定読み込み
        smtp_host = os.getenv('ALERT_SMTP_HOST')
        smtp_port = int(os.getenv('ALERT_SMTP_PORT', '587'))
        smtp_user = os.getenv('ALERT_SMTP_USER')
        smtp_password = os.getenv('ALERT_SMTP_PASSWORD')
        recipients = os.getenv('ALERT_EMAIL_RECIPIENTS', '').split(',')
        
        if not all([smtp_host, smtp_user, smtp_password, recipients]):
            return
        
        # メール作成
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"PresidioPDF Alert: {alert_data['rule_name']}"
        
        body = f"""
        Alert Details:
        - Rule: {alert_data['rule_name']}
        - Metric: {alert_data['metric_name']}
        - Current Value: {alert_data['metric_value']:.2f}
        - Threshold: {alert_data.get('threshold', 'N/A')}
        - Severity: {alert_data['severity']}
        - Status: {alert_data['status']}
        - Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert_data['timestamp']))}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # 送信
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipients, msg.as_string())
    
    def _send_slack_alert(self, alert_data: Dict[str, Any]):
        """Slack通知"""
        webhook_url = os.getenv('ALERT_SLACK_WEBHOOK_URL')
        if not webhook_url:
            return
        
        color = {
            'info': '#36a64f',
            'warning': '#ff9900',
            'error': '#ff0000',
            'critical': '#cc0000'
        }.get(alert_data['severity'], '#cccccc')
        
        payload = {
            'attachments': [{
                'color': color,
                'title': f"PresidioPDF Alert: {alert_data['rule_name']}",
                'fields': [
                    {'title': 'Metric', 'value': alert_data['metric_name'], 'short': True},
                    {'title': 'Value', 'value': f"{alert_data['metric_value']:.2f}", 'short': True},
                    {'title': 'Threshold', 'value': str(alert_data.get('threshold', 'N/A')), 'short': True},
                    {'title': 'Severity', 'value': alert_data['severity'], 'short': True}
                ],
                'footer': 'PresidioPDF Monitoring',
                'ts': int(alert_data['timestamp'])
            }]
        }
        
        requests.post(webhook_url, json=payload, timeout=30)
    
    def _send_webhook_alert(self, alert_data: Dict[str, Any]):
        """Webhook通知"""
        webhook_url = os.getenv('ALERT_WEBHOOK_URL')
        if not webhook_url:
            return
        
        requests.post(webhook_url, json=alert_data, timeout=30)
    
    def get_alert_status(self) -> Dict[str, Any]:
        """アラート状態取得"""
        return {
            'active_alerts': len(self.active_alerts),
            'total_rules': len(self.alert_rules),
            'enabled_rules': len([r for r in self.alert_rules if r.enabled]),
            'recent_alerts': list(self.alert_history)[-10:],  # 最新10件
            'alert_details': [
                {
                    'name': info['rule'].name,
                    'metric': info['rule'].metric_name,
                    'duration': time.time() - info['start_time'],
                    'current_value': info['metric_value']
                }
                for info in self.active_alerts.values()
            ]
        }
```

## 外部監視システム統合

### Prometheus統合
```python
# Prometheus メトリクスエクスポート
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

class PrometheusMetricsExporter:
    """Prometheusメトリクスエクスポーター"""
    
    def __init__(self):
        # Prometheusメトリクス定義
        self.request_count = Counter(
            'presidio_requests_total',
            'Total number of requests',
            ['method', 'endpoint', 'status']
        )
        
        self.request_duration = Histogram(
            'presidio_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint']
        )
        
        self.processing_duration = Histogram(
            'presidio_processing_duration_seconds',
            'PDF processing duration in seconds',
            ['model', 'status']
        )
        
        self.entities_detected = Histogram(
            'presidio_entities_detected',
            'Number of entities detected',
            ['entity_type', 'model']
        )
        
        self.system_cpu = Gauge(
            'presidio_system_cpu_percent',
            'System CPU usage percentage'
        )
        
        self.system_memory = Gauge(
            'presidio_system_memory_percent',
            'System memory usage percentage'
        )
        
        self.active_processing = Gauge(
            'presidio_active_processing_jobs',
            'Number of active processing jobs'
        )
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """リクエストメトリクス記録"""
        self.request_count.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_processing(self, model: str, duration: float, entities: int, success: bool):
        """処理メトリクス記録"""
        status = 'success' if success else 'error'
        
        self.processing_duration.labels(
            model=model,
            status=status
        ).observe(duration)
        
        if success:
            self.entities_detected.labels(
                entity_type='total',
                model=model
            ).observe(entities)
    
    def update_system_metrics(self, cpu_percent: float, memory_percent: float):
        """システムメトリクス更新"""
        self.system_cpu.set(cpu_percent)
        self.system_memory.set(memory_percent)
    
    def set_active_processing_jobs(self, count: int):
        """アクティブ処理ジョブ数設定"""
        self.active_processing.set(count)
    
    def generate_metrics(self) -> Response:
        """Prometheusメトリクス生成"""
        return Response(
            generate_latest(),
            mimetype=CONTENT_TYPE_LATEST
        )

# Flask統合
def setup_prometheus_monitoring(app: Flask):
    """Prometheusモニタリング設定"""
    exporter = PrometheusMetricsExporter()
    
    @app.route('/metrics')
    def prometheus_metrics():
        return exporter.generate_metrics()
    
    @app.before_request
    def before_request():
        request.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            exporter.record_request(
                method=request.method,
                endpoint=request.endpoint or 'unknown',
                status_code=response.status_code,
                duration=duration
            )
        return response
    
    # 定期システムメトリクス更新
    def update_system_metrics():
        while True:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent
                exporter.update_system_metrics(cpu_percent, memory_percent)
            except Exception as e:
                logging.error(f"System metrics update error: {e}")
            time.sleep(30)
    
    metrics_thread = threading.Thread(target=update_system_metrics, daemon=True)
    metrics_thread.start()
    
    return exporter
```

## ダッシュボード・可視化

### メトリクスダッシュボード
```python
# ダッシュボードAPI
from flask import jsonify, render_template

class MonitoringDashboard:
    """監視ダッシュボード"""
    
    def __init__(self, metrics_collector: MetricsCollector, alert_manager: AlertManager):
        self.metrics_collector = metrics_collector
        self.alert_manager = alert_manager
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """ダッシュボードデータ取得"""
        metrics_summary = self.metrics_collector.get_metrics_summary()
        alert_status = self.alert_manager.get_alert_status()
        
        # 時系列データ準備（簡易版）
        time_series_data = self._prepare_time_series_data()
        
        return {
            'overview': {
                'total_requests': self._get_total_requests(metrics_summary),
                'success_rate': self._calculate_success_rate(metrics_summary),
                'avg_processing_time': self._get_avg_processing_time(metrics_summary),
                'active_alerts': alert_status['active_alerts']
            },
            'system_metrics': {
                'cpu_usage': metrics_summary['gauges'].get('system.cpu.usage_percent', 0),
                'memory_usage': metrics_summary['gauges'].get('system.memory.usage_percent', 0),
                'disk_usage': metrics_summary['gauges'].get('system.disk.usage_percent', 0)
            },
            'processing_metrics': {
                'processing_times': metrics_summary['timers'].get('presidio.processing.duration', {}),
                'entities_detected': metrics_summary['histograms'].get('presidio.processing.entities_detected', {}),
                'pages_processed': metrics_summary['histograms'].get('presidio.processing.pages', {})
            },
            'alerts': {
                'active': alert_status['alert_details'],
                'recent': alert_status['recent_alerts']
            },
            'time_series': time_series_data
        }
    
    def _get_total_requests(self, metrics: Dict[str, Any]) -> int:
        """総リクエスト数取得"""
        api_requests = metrics.get('counters', {}).get('presidio.api.requests', 0)
        return int(api_requests)
    
    def _calculate_success_rate(self, metrics: Dict[str, Any]) -> float:
        """成功率計算"""
        processing_counters = metrics.get('counters', {})
        
        success_count = 0
        total_count = 0
        
        for key, value in processing_counters.items():
            if 'presidio.processing.count' in key:
                total_count += value
                if 'success' in key:
                    success_count += value
        
        return (success_count / total_count * 100) if total_count > 0 else 0.0
    
    def _get_avg_processing_time(self, metrics: Dict[str, Any]) -> float:
        """平均処理時間取得"""
        processing_times = metrics.get('timers', {}).get('presidio.processing.duration', {})
        return processing_times.get('avg_ms', 0.0)
    
    def _prepare_time_series_data(self) -> Dict[str, List]:
        """時系列データ準備"""
        # 簡易実装（実際は時系列DB使用推奨）
        now = time.time()
        timestamps = [now - i * 300 for i in range(24, 0, -1)]  # 過去2時間、5分間隔
        
        return {
            'timestamps': [int(ts) for ts in timestamps],
            'cpu_usage': [50 + (i % 30) for i in range(24)],  # ダミーデータ
            'memory_usage': [60 + (i % 20) for i in range(24)],
            'processing_times': [2000 + (i % 1000) for i in range(24)]
        }
    
    def setup_dashboard_routes(self, app: Flask):
        """ダッシュボードルート設定"""
        
        @app.route('/dashboard')
        def dashboard():
            """ダッシュボード画面"""
            return render_template('dashboard.html')
        
        @app.route('/api/dashboard/data')
        def dashboard_data():
            """ダッシュボードデータAPI"""
            return jsonify(self.get_dashboard_data())
        
        @app.route('/api/metrics/summary')
        def metrics_summary():
            """メトリクスサマリーAPI"""
            return jsonify(self.metrics_collector.get_metrics_summary())
        
        @app.route('/api/alerts/status')
        def alerts_status():
            """アラート状態API"""
            return jsonify(self.alert_manager.get_alert_status())

# ダッシュボード HTML テンプレート（簡易版）
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>PresidioPDF Monitoring Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metric-card { 
            display: inline-block; 
            background: #f5f5f5; 
            padding: 20px; 
            margin: 10px; 
            border-radius: 8px; 
            min-width: 200px;
        }
        .metric-value { font-size: 2em; font-weight: bold; color: #333; }
        .metric-label { color: #666; }
        .alert-active { color: #ff4444; }
        .alert-resolved { color: #44ff44; }
        canvas { margin: 20px 0; }
    </style>
</head>
<body>
    <h1>PresidioPDF Monitoring Dashboard</h1>
    
    <div id="overview">
        <div class="metric-card">
            <div class="metric-value" id="total-requests">-</div>
            <div class="metric-label">Total Requests</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="success-rate">-</div>
            <div class="metric-label">Success Rate (%)</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="avg-processing-time">-</div>
            <div class="metric-label">Avg Processing Time (ms)</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" id="active-alerts">-</div>
            <div class="metric-label">Active Alerts</div>
        </div>
    </div>
    
    <canvas id="systemMetricsChart" width="800" height="400"></canvas>
    
    <div id="alerts-section">
        <h2>Active Alerts</h2>
        <div id="active-alerts"></div>
    </div>
    
    <script>
        // ダッシュボードデータ更新
        function updateDashboard() {
            fetch('/api/dashboard/data')
                .then(response => response.json())
                .then(data => {
                    // 概要メトリクス更新
                    document.getElementById('total-requests').textContent = data.overview.total_requests;
                    document.getElementById('success-rate').textContent = data.overview.success_rate.toFixed(1);
                    document.getElementById('avg-processing-time').textContent = Math.round(data.overview.avg_processing_time);
                    document.getElementById('active-alerts').textContent = data.overview.active_alerts;
                    
                    // アラート表示更新
                    updateAlertsDisplay(data.alerts);
                })
                .catch(error => console.error('Dashboard update error:', error));
        }
        
        function updateAlertsDisplay(alerts) {
            const container = document.getElementById('active-alerts');
            container.innerHTML = '';
            
            alerts.active.forEach(alert => {
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert-active';
                alertDiv.textContent = `${alert.name}: ${alert.current_value.toFixed(2)} (${alert.duration.toFixed(0)}s)`;
                container.appendChild(alertDiv);
            });
        }
        
        // 初回読み込み
        updateDashboard();
        
        // 30秒間隔で更新
        setInterval(updateDashboard, 30000);
    </script>
</body>
</html>
'''
```