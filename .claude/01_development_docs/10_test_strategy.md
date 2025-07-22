# テスト戦略

## 概要
PresidioPDFプロジェクトの包括的テスト戦略を定義する。品質目標として80%以上のテストカバレッジを維持し、全警告をエラーとして扱うゼロワーニングポリシーを適用する。

## テスト方針

### テストレベル定義
```python
from enum import Enum

class TestLevel(Enum):
    UNIT = "unit"           # 単体テスト（関数・メソッド単位）
    INTEGRATION = "integration"  # 統合テスト（モジュール間連携）
    SYSTEM = "system"       # システムテスト（エンドツーエンド）
    ACCEPTANCE = "acceptance"    # 受け入れテスト（ユーザーシナリオ）

class TestCategory(Enum):
    FUNCTIONAL = "functional"    # 機能テスト
    PERFORMANCE = "performance"  # 性能テスト
    SECURITY = "security"       # セキュリティテスト
    USABILITY = "usability"     # ユーザビリティテスト
```

### テストカバレッジ目標
- **総合カバレッジ**: 80%以上
- **コア業務ロジック**: 95%以上
- **エラーハンドリング**: 90%以上
- **API エンドポイント**: 100%

## 単体テスト設計

### pytest設定
```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --strict-config
    --cov=src
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-report=xml
    --cov-fail-under=80
    -v
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: integration tests
    gpu: tests requiring GPU
    web: web interface tests
    cli: command line interface tests
filterwarnings =
    error
    ignore::UserWarning
    ignore::DeprecationWarning:spacy.*
```

### テストフィクスチャ設計
```python
# tests/conftest.py
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock
from src.config_manager import ConfigManager
from src.analyzer import AnalyzerService
from src.pdf_processor import PDFProcessor

@pytest.fixture(scope="session")
def temp_dir():
    """テスト用一時ディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def sample_config():
    """テスト用設定"""
    return {
        "nlp": {
            "spacy_model": "ja_core_news_sm",
            "confidence_threshold": 0.8,
            "batch_size": 16
        },
        "pdf_processing": {
            "masking_method": "annotation",
            "preserve_original": True
        },
        "entity_filter": {
            "enabled_entities": {
                "PERSON": True,
                "LOCATION": True,
                "PHONE_NUMBER": True
            }
        }
    }

@pytest.fixture
def sample_pdf_path(temp_dir):
    """テスト用PDFファイル"""
    # 実際のPDFファイルを生成またはコピー
    pdf_path = temp_dir / "sample.pdf"
    # PDFファイル生成ロジック
    create_test_pdf(pdf_path)
    return pdf_path

@pytest.fixture
def mock_spacy_model():
    """spaCyモデルのモック"""
    mock_model = Mock()
    mock_model.pipe.return_value = [Mock(ents=[])]
    return mock_model

@pytest.fixture
def analyzer_service(mock_spacy_model):
    """解析サービスのテストインスタンス"""
    return AnalyzerService(model=mock_spacy_model)

@pytest.fixture
def pdf_processor(sample_config, temp_dir):
    """PDF処理サービスのテストインスタンス"""
    config_manager = ConfigManager()
    return PDFProcessor(config_manager, output_dir=temp_dir)
```

### 単体テスト例
```python
# tests/test_analyzer.py
import pytest
from src.analyzer import AnalyzerService
from src.types import EntityDetection, EntityType

class TestAnalyzerService:
    """解析サービス単体テスト"""
    
    def test_analyze_text_with_person_name(self, analyzer_service):
        """個人名検出テスト"""
        text = "私の名前は田中太郎です。"
        
        # spaCyモックの設定
        mock_ent = Mock()
        mock_ent.text = "田中太郎"
        mock_ent.label_ = "PERSON"
        mock_ent.start_char = 5
        mock_ent.end_char = 9
        
        analyzer_service.model.pipe.return_value = [Mock(ents=[mock_ent])]
        
        # テスト実行
        results = analyzer_service.analyze_text(text)
        
        # 検証
        assert len(results) == 1
        assert results[0].entity_type == "PERSON"
        assert results[0].text == "田中太郎"
        assert results[0].start == 5
        assert results[0].end == 9
    
    def test_analyze_empty_text(self, analyzer_service):
        """空文字列のテスト"""
        results = analyzer_service.analyze_text("")
        assert results == []
    
    @pytest.mark.parametrize("confidence,threshold,expected", [
        (0.9, 0.8, True),
        (0.7, 0.8, False),
        (0.8, 0.8, True)
    ])
    def test_confidence_filtering(self, analyzer_service, confidence, threshold, expected):
        """信頼度フィルタリングテスト"""
        # モック設定
        mock_ent = Mock()
        mock_ent.text = "テスト"
        mock_ent.label_ = "PERSON"
        mock_ent.start_char = 0
        mock_ent.end_char = 4
        
        analyzer_service.model.pipe.return_value = [Mock(ents=[mock_ent])]
        analyzer_service.confidence_threshold = threshold
        
        # 信頼度スコア計算をモック
        with patch.object(analyzer_service, '_calculate_confidence', return_value=confidence):
            results = analyzer_service.analyze_text("テスト")
        
        # 検証
        if expected:
            assert len(results) == 1
        else:
            assert len(results) == 0
    
    @pytest.mark.slow
    def test_analyze_large_text_performance(self, analyzer_service):
        """大量テキスト処理性能テスト"""
        large_text = "田中太郎さんは東京都在住です。" * 1000
        
        import time
        start_time = time.time()
        results = analyzer_service.analyze_text(large_text)
        processing_time = time.time() - start_time
        
        # 性能検証（10秒以内）
        assert processing_time < 10.0
        assert len(results) > 0
```

## 統合テスト設計

### PDF処理統合テスト
```python
# tests/integration/test_pdf_processing.py
import pytest
from pathlib import Path
from src.pdf_processor import PDFProcessor
from src.types import ProcessingResult

@pytest.mark.integration
class TestPDFProcessingIntegration:
    """PDF処理統合テスト"""
    
    def test_complete_pdf_processing_workflow(self, pdf_processor, sample_pdf_path):
        """完全なPDF処理ワークフローテスト"""
        # 処理実行
        result = pdf_processor.process_pdf(sample_pdf_path)
        
        # 結果検証
        assert isinstance(result, ProcessingResult)
        assert result.success
        assert result.output_file.exists()
        assert result.statistics.total_count >= 0
        
        # 出力ファイル検証
        assert result.output_file.suffix == '.pdf'
        assert result.output_file.stat().st_size > 0
    
    def test_pdf_processing_with_custom_config(self, pdf_processor, sample_pdf_path, sample_config):
        """カスタム設定でのPDF処理テスト"""
        # カスタム設定適用
        sample_config["pdf_processing"]["masking_method"] = "highlight"
        sample_config["entity_filter"]["enabled_entities"]["PERSON"] = False
        
        result = pdf_processor.process_pdf(sample_pdf_path, config=sample_config)
        
        # 設定反映確認
        assert result.config_snapshot.pdf_processing.masking_method == "highlight"
        assert not result.config_snapshot.entity_filter.enabled_entities["PERSON"]
    
    def test_error_handling_invalid_pdf(self, pdf_processor, temp_dir):
        """無効PDFファイルのエラーハンドリングテスト"""
        # 無効PDFファイル作成
        invalid_pdf = temp_dir / "invalid.pdf"
        invalid_pdf.write_text("This is not a PDF file")
        
        # エラー発生確認
        with pytest.raises(FileValidationError) as exc_info:
            pdf_processor.process_pdf(invalid_pdf)
        
        assert "INVALID_FILE_FORMAT" in str(exc_info.value)
    
    @pytest.mark.gpu
    def test_gpu_model_processing(self, pdf_processor, sample_pdf_path):
        """GPU対応モデルでの処理テスト"""
        # GPU設定でのテスト（CI環境では無効化される可能性がある）
        config = {
            "nlp": {"spacy_model": "ja_core_news_trf"},
            "pdf_processing": {"masking_method": "annotation"}
        }
        
        try:
            result = pdf_processor.process_pdf(sample_pdf_path, config=config)
            assert result.success
        except ModelLoadError:
            pytest.skip("GPU model not available in test environment")
```

## システムテスト設計

### CLI システムテスト
```python
# tests/system/test_cli_system.py
import subprocess
import pytest
from pathlib import Path

@pytest.mark.system
class TestCLISystem:
    """CLIシステムテスト"""
    
    def test_cli_basic_processing(self, sample_pdf_path, temp_dir):
        """CLI基本処理テスト"""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        
        cmd = [
            "uv", "run", "python", "-m", "src.cli",
            str(sample_pdf_path),
            "--output-dir", str(output_dir),
            "--verbose"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        # 実行成功確認
        assert result.returncode == 0
        assert "処理完了" in result.stdout or "completed" in result.stdout.lower()
        
        # 出力ファイル確認
        output_files = list(output_dir.glob("*.pdf"))
        assert len(output_files) > 0
    
    def test_cli_help_option(self):
        """CLIヘルプオプションテスト"""
        cmd = ["uv", "run", "python", "-m", "src.cli", "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "--spacy-model" in result.stdout
    
    def test_cli_invalid_file_error(self, temp_dir):
        """CLI無効ファイルエラーテスト"""
        invalid_file = temp_dir / "nonexistent.pdf"
        
        cmd = ["uv", "run", "python", "-m", "src.cli", str(invalid_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        assert result.returncode != 0
        assert "エラー" in result.stderr or "error" in result.stderr.lower()
```

### Web UIシステムテスト
```python
# tests/system/test_web_system.py
import pytest
import requests
import time
import subprocess
from multiprocessing import Process

@pytest.mark.web
@pytest.mark.system
class TestWebUISystem:
    """Web UIシステムテスト"""
    
    @pytest.fixture(scope="class")
    def web_server(self):
        """テスト用Webサーバー起動"""
        def start_server():
            subprocess.run([
                "uv", "run", "python", "src/web_main.py", 
                "--port", "5001", "--debug"
            ])
        
        server_process = Process(target=start_server)
        server_process.start()
        
        # サーバー起動待ち
        for _ in range(10):
            try:
                requests.get("http://localhost:5001/", timeout=1)
                break
            except requests.exceptions.RequestException:
                time.sleep(1)
        else:
            pytest.fail("Web server failed to start")
        
        yield "http://localhost:5001"
        
        server_process.terminate()
        server_process.join()
    
    def test_home_page_access(self, web_server):
        """ホームページアクセステスト"""
        response = requests.get(f"{web_server}/")
        
        assert response.status_code == 200
        assert "PresidioPDF" in response.text
    
    def test_file_upload_api(self, web_server, sample_pdf_path):
        """ファイルアップロードAPIテスト"""
        with open(sample_pdf_path, 'rb') as f:
            files = {'file': ('sample.pdf', f, 'application/pdf')}
            response = requests.post(f"{web_server}/api/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert 'upload_id' in data
        assert data['filename'] == 'sample.pdf'
    
    def test_processing_api_workflow(self, web_server, sample_pdf_path):
        """処理APIワークフローテスト"""
        # ファイルアップロード
        with open(sample_pdf_path, 'rb') as f:
            files = {'file': ('sample.pdf', f, 'application/pdf')}
            upload_response = requests.post(f"{web_server}/api/upload", files=files)
        
        upload_data = upload_response.json()
        upload_id = upload_data['upload_id']
        
        # 処理開始
        process_data = {'upload_id': upload_id, 'config': {}}
        process_response = requests.post(f"{web_server}/api/process", json=process_data)
        
        assert process_response.status_code == 200
        process_data = process_response.json()
        processing_id = process_data['processing_id']
        
        # 処理状況確認（ポーリング）
        for _ in range(30):  # 最大30秒待機
            status_response = requests.get(f"{web_server}/api/process/{processing_id}/status")
            status_data = status_response.json()
            
            if status_data['status'] == 'completed':
                break
            elif status_data['status'] == 'error':
                pytest.fail(f"Processing failed: {status_data.get('message')}")
            
            time.sleep(1)
        else:
            pytest.fail("Processing timeout")
        
        # 結果取得
        result_response = requests.get(f"{web_server}/api/process/{processing_id}/result")
        assert result_response.status_code == 200
        result_data = result_response.json()
        assert 'report' in result_data
        assert 'download_url' in result_data
```

## 性能テスト設計

### 負荷テスト
```python
# tests/performance/test_performance.py
import pytest
import time
import concurrent.futures
from pathlib import Path

@pytest.mark.performance
class TestPerformance:
    """性能テスト"""
    
    def test_single_pdf_processing_time(self, pdf_processor, sample_pdf_path):
        """単一PDF処理時間テスト"""
        start_time = time.time()
        result = pdf_processor.process_pdf(sample_pdf_path)
        processing_time = time.time() - start_time
        
        # 性能要件: 10ページPDF を30秒以内で処理
        page_count = result.statistics.by_page.__len__() if result.statistics.by_page else 1
        time_per_page = processing_time / max(page_count, 1)
        
        assert time_per_page < 3.0, f"Processing too slow: {time_per_page:.2f}s per page"
    
    def test_concurrent_processing(self, pdf_processor, sample_pdf_path):
        """並行処理性能テスト"""
        def process_pdf():
            return pdf_processor.process_pdf(sample_pdf_path)
        
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_pdf) for _ in range(3)]
            results = [f.result() for f in futures]
        
        total_time = time.time() - start_time
        
        # 3つの処理が並行実行されることを確認
        assert all(r.success for r in results)
        assert total_time < 60.0  # 3つ並行で1分以内
    
    @pytest.mark.slow
    def test_memory_usage(self, pdf_processor, sample_pdf_path):
        """メモリ使用量テスト"""
        import psutil
        import gc
        
        # 初期メモリ使用量
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss
        
        # 処理実行
        result = pdf_processor.process_pdf(sample_pdf_path)
        
        # 処理後メモリ使用量
        peak_memory = psutil.Process().memory_info().rss
        memory_increase = peak_memory - initial_memory
        
        # メモリ使用量制限: 1GB以内
        assert memory_increase < 1024 * 1024 * 1024, f"Memory usage too high: {memory_increase / 1024 / 1024:.2f}MB"
        
        # クリーンアップ確認
        del result
        gc.collect()
        time.sleep(1)
        final_memory = psutil.Process().memory_info().rss
        memory_leaked = final_memory - initial_memory
        
        # メモリリーク検証: 100MB以内
        assert memory_leaked < 100 * 1024 * 1024, f"Memory leak detected: {memory_leaked / 1024 / 1024:.2f}MB"
```

## テスト実行・レポート

### 継続的テスト実行
```bash
# 全テスト実行
uv run pytest

# カテゴリ別テスト実行
uv run pytest -m "unit"
uv run pytest -m "integration"  
uv run pytest -m "system"
uv run pytest -m "performance"

# 除外テスト実行
uv run pytest -m "not slow"
uv run pytest -m "not gpu"

# 詳細レポート生成
uv run pytest --cov=src --cov-report=html --cov-report=term-missing --junitxml=reports/junit.xml
```

### テスト結果分析
```python
# scripts/test_analysis.py
import xml.etree.ElementTree as ET
from pathlib import Path

def analyze_test_results():
    """テスト結果分析"""
    junit_file = Path("reports/junit.xml")
    if not junit_file.exists():
        return
    
    tree = ET.parse(junit_file)
    root = tree.getroot()
    
    total_tests = int(root.get('tests', 0))
    failures = int(root.get('failures', 0))
    errors = int(root.get('errors', 0))
    skipped = int(root.get('skipped', 0))
    
    success_rate = ((total_tests - failures - errors) / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Test Results Summary:")
    print(f"  Total: {total_tests}")
    print(f"  Passed: {total_tests - failures - errors - skipped}")
    print(f"  Failed: {failures}")
    print(f"  Errors: {errors}")
    print(f"  Skipped: {skipped}")
    print(f"  Success Rate: {success_rate:.2f}%")
    
    # 失敗したテストの詳細
    for testcase in root.iter('testcase'):
        failure = testcase.find('failure')
        error = testcase.find('error')
        if failure is not None or error is not None:
            test_name = f"{testcase.get('classname')}.{testcase.get('name')}"
            print(f"FAILED: {test_name}")

if __name__ == "__main__":
    analyze_test_results()
```

## テスト品質保証

### テスト品質メトリクス
```python
# scripts/test_quality_check.py
def check_test_quality():
    """テスト品質チェック"""
    import ast
    import os
    
    test_files = []
    for root, dirs, files in os.walk("tests"):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))
    
    metrics = {
        "total_test_files": len(test_files),
        "total_test_functions": 0,
        "files_with_fixtures": 0,
        "files_with_parametrize": 0
    }
    
    for test_file in test_files:
        with open(test_file, 'r') as f:
            content = f.read()
            tree = ast.parse(content)
        
        # テスト関数カウント
        test_functions = [node for node in ast.walk(tree) 
                         if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
        metrics["total_test_functions"] += len(test_functions)
        
        # フィクスチャ使用チェック
        if "@pytest.fixture" in content:
            metrics["files_with_fixtures"] += 1
            
        # パラメータ化テストチェック
        if "@pytest.mark.parametrize" in content:
            metrics["files_with_parametrize"] += 1
    
    print("Test Quality Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    # 品質基準チェック
    avg_tests_per_file = metrics["total_test_functions"] / metrics["total_test_files"]
    if avg_tests_per_file < 5:
        print(f"WARNING: Low test density ({avg_tests_per_file:.1f} tests per file)")

if __name__ == "__main__":
    check_test_quality()
```