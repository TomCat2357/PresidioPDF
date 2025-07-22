# フロントエンド設計（Flask Web UI）

## 概要
PresidioPDF Web UIのフロントエンド設計を定義する。Flask + Jinja2テンプレートをベースとし、モダンなユーザー体験を提供するための技術スタックとアーキテクチャを設計する。

## 技術スタック

### コア技術
```yaml
backend:
  framework: Flask 2.3+
  template_engine: Jinja2
  static_files: Flask-Static

frontend:
  html: HTML5 Semantic Elements
  css: CSS3 + CSS Grid/Flexbox
  javascript: Vanilla ES6+ (TypeScript optional)
  icons: Lucide Icons or Heroicons
  
build_tools:
  css_processor: None (Pure CSS approach)
  js_bundler: None (ES6 modules)
  minification: Flask-Assets (optional)

deployment:
  development: Flask development server
  production: Gunicorn + Nginx
```

### 外部依存関係の最小化
```html
<!-- 必要最小限のCDN利用 -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/normalize.css@8.0.1/normalize.min.css">
<!-- 残りはセルフホスト -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
<script type="module" src="{{ url_for('static', filename='js/main.js') }}"></script>
```

## アーキテクチャ設計

### ディレクトリ構造
```
src/
├── templates/
│   ├── base.html              # ベーステンプレート
│   ├── components/            # 再利用可能コンポーネント
│   │   ├── header.html
│   │   ├── footer.html
│   │   ├── file_upload.html
│   │   ├── progress_bar.html
│   │   └── entity_list.html
│   ├── pages/                 # ページテンプレート
│   │   ├── home.html
│   │   ├── config.html
│   │   ├── processing.html
│   │   ├── result.html
│   │   ├── history.html
│   │   └── help.html
│   └── errors/                # エラーページ
│       ├── 404.html
│       ├── 500.html
│       └── error_base.html
├── static/
│   ├── css/
│   │   ├── main.css           # メインスタイル
│   │   ├── components/        # コンポーネントスタイル
│   │   │   ├── header.css
│   │   │   ├── buttons.css
│   │   │   ├── forms.css
│   │   │   └── cards.css
│   │   └── pages/             # ページ固有スタイル
│   │       ├── home.css
│   │       ├── config.css
│   │       └── result.css
│   ├── js/
│   │   ├── main.js            # メインスクリプト
│   │   ├── components/        # コンポーネントスクリプト
│   │   │   ├── file-upload.js
│   │   │   ├── progress-bar.js
│   │   │   └── entity-viewer.js
│   │   └── utils/             # ユーティリティ
│   │       ├── api-client.js
│   │       ├── error-handler.js
│   │       └── storage.js
│   ├── images/
│   └── icons/
```

## テンプレート設計

### ベーステンプレート
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PresidioPDF - PDF個人情報保護ツール{% endblock %}</title>
    
    <!-- SEO Meta Tags -->
    <meta name="description" content="{% block description %}AI技術でPDF個人情報を自動検出・マスキング{% endblock %}">
    <meta name="keywords" content="PDF,個人情報,マスキング,プライバシー,AI">
    
    <!-- CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/normalize.css@8.0.1/normalize.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/main.css') }}">
    {% block css %}{% endblock %}
    
    <!-- Favicon -->
    <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}">
</head>
<body class="{% block body_class %}{% endblock %}">
    <div id="app">
        <!-- Header -->
        {% include 'components/header.html' %}
        
        <!-- Main Content -->
        <main role="main" class="main-content">
            {% block content %}{% endblock %}
        </main>
        
        <!-- Footer -->
        {% include 'components/footer.html' %}
    </div>
    
    <!-- Error Modal -->
    <div id="error-container" class="error-modal" style="display: none;"></div>
    
    <!-- Loading Overlay -->
    <div id="loading-overlay" class="loading-overlay" style="display: none;">
        <div class="loading-spinner"></div>
        <p>処理中...</p>
    </div>
    
    <!-- JavaScript -->
    <script type="module" src="{{ url_for('static', filename='js/main.js') }}"></script>
    {% block js %}{% endblock %}
</body>
</html>
```

### コンポーネントテンプレート例
```html
<!-- templates/components/file_upload.html -->
<div class="file-upload-component" id="file-upload">
    <div class="upload-area" id="upload-area">
        <div class="upload-icon">📄</div>
        <h3>PDFファイルを選択</h3>
        <p class="upload-description">
            ファイルをドラッグ&ドロップするか、クリックして選択してください<br>
            <small>最大ファイルサイズ: 50MB</small>
        </p>
        <input type="file" id="file-input" accept=".pdf,application/pdf" style="display: none;">
        <button type="button" class="btn btn-primary" onclick="document.getElementById('file-input').click()">
            ファイルを選択
        </button>
    </div>
    
    <div class="file-info" id="file-info" style="display: none;">
        <div class="file-details">
            <span class="file-name" id="file-name"></span>
            <span class="file-size" id="file-size"></span>
        </div>
        <button type="button" class="btn btn-secondary btn-sm" id="remove-file">削除</button>
    </div>
    
    <div class="upload-progress" id="upload-progress" style="display: none;">
        <div class="progress-bar">
            <div class="progress-fill" id="upload-progress-fill"></div>
        </div>
        <span class="progress-text" id="upload-progress-text">0%</span>
    </div>
</div>
```

## CSS設計（BEM方式）

### メインスタイルシート
```css
/* static/css/main.css */
:root {
    /* カラーパレット */
    --primary-color: #3b82f6;
    --primary-hover: #2563eb;
    --secondary-color: #6b7280;
    --success-color: #10b981;
    --warning-color: #f59e0b;
    --error-color: #ef4444;
    --info-color: #06b6d4;
    
    /* グレースケール */
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;
    
    /* タイポグラフィ */
    --font-family-sans: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --font-size-xs: 0.75rem;
    --font-size-sm: 0.875rem;
    --font-size-base: 1rem;
    --font-size-lg: 1.125rem;
    --font-size-xl: 1.25rem;
    --font-size-2xl: 1.5rem;
    --font-size-3xl: 1.875rem;
    
    /* スペーシング */
    --spacing-1: 0.25rem;
    --spacing-2: 0.5rem;
    --spacing-3: 0.75rem;
    --spacing-4: 1rem;
    --spacing-5: 1.25rem;
    --spacing-6: 1.5rem;
    --spacing-8: 2rem;
    --spacing-10: 2.5rem;
    --spacing-12: 3rem;
    
    /* ブレークポイント */
    --breakpoint-sm: 640px;
    --breakpoint-md: 768px;
    --breakpoint-lg: 1024px;
    --breakpoint-xl: 1280px;
    
    /* アニメーション */
    --transition-fast: 150ms ease-in-out;
    --transition-normal: 300ms ease-in-out;
    --transition-slow: 500ms ease-in-out;
}

/* リセット & ベーススタイル */
*,
*::before,
*::after {
    box-sizing: border-box;
}

body {
    font-family: var(--font-family-sans);
    font-size: var(--font-size-base);
    line-height: 1.6;
    color: var(--gray-800);
    background-color: var(--gray-50);
    margin: 0;
    padding: 0;
}

#app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

.main-content {
    flex: 1;
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--spacing-6);
    width: 100%;
}

/* レスポンシブ調整 */
@media (max-width: 768px) {
    .main-content {
        padding: var(--spacing-4);
    }
}
```

### コンポーネントスタイル
```css
/* static/css/components/buttons.css */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-2);
    padding: var(--spacing-3) var(--spacing-6);
    border: 1px solid transparent;
    border-radius: 0.5rem;
    font-size: var(--font-size-base);
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
    transition: all var(--transition-fast);
    outline: none;
}

.btn:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
}

.btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

/* ボタンバリアント */
.btn--primary {
    background-color: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
}

.btn--primary:hover:not(:disabled) {
    background-color: var(--primary-hover);
    border-color: var(--primary-hover);
}

.btn--secondary {
    background-color: transparent;
    color: var(--gray-700);
    border-color: var(--gray-300);
}

.btn--secondary:hover:not(:disabled) {
    background-color: var(--gray-50);
    border-color: var(--gray-400);
}

/* ボタンサイズ */
.btn--sm {
    padding: var(--spacing-2) var(--spacing-4);
    font-size: var(--font-size-sm);
}

.btn--lg {
    padding: var(--spacing-4) var(--spacing-8);
    font-size: var(--font-size-lg);
}
```

## JavaScript設計（ES6モジュール）

### メインスクリプト
```javascript
// static/js/main.js
import { FileUploadComponent } from './components/file-upload.js';
import { ProgressBarComponent } from './components/progress-bar.js';
import { ApiClient } from './utils/api-client.js';
import { ErrorHandler } from './utils/error-handler.js';
import { LocalStorage } from './utils/storage.js';

class PresidioPDFApp {
    constructor() {
        this.apiClient = new ApiClient('/api');
        this.errorHandler = new ErrorHandler();
        this.storage = new LocalStorage();
        this.components = {};
        
        this.init();
    }
    
    init() {
        this.initializeComponents();
        this.bindGlobalEvents();
        this.loadUserPreferences();
    }
    
    initializeComponents() {
        // ファイルアップロードコンポーネント
        const fileUploadElement = document.getElementById('file-upload');
        if (fileUploadElement) {
            this.components.fileUpload = new FileUploadComponent(fileUploadElement, {
                apiClient: this.apiClient,
                errorHandler: this.errorHandler,
                onUploadSuccess: (uploadData) => this.handleUploadSuccess(uploadData),
                onUploadError: (error) => this.handleUploadError(error)
            });
        }
        
        // プログレスバーコンポーネント
        const progressBarElement = document.getElementById('progress-bar');
        if (progressBarElement) {
            this.components.progressBar = new ProgressBarComponent(progressBarElement);
        }
    }
    
    bindGlobalEvents() {
        // グローバルエラーハンドリング
        window.addEventListener('error', (event) => {
            this.errorHandler.handleGlobalError(event.error);
        });
        
        // 未処理Promise拒否
        window.addEventListener('unhandledrejection', (event) => {
            this.errorHandler.handleGlobalError(event.reason);
        });
        
        // ページ離脱時の確認
        window.addEventListener('beforeunload', (event) => {
            if (this.hasActiveProcessing()) {
                event.preventDefault();
                event.returnValue = '処理が実行中です。ページを離れますか？';
            }
        });
    }
    
    loadUserPreferences() {
        const preferences = this.storage.getItem('user_preferences');
        if (preferences) {
            this.applyPreferences(preferences);
        }
    }
    
    handleUploadSuccess(uploadData) {
        console.log('Upload successful:', uploadData);
        this.storage.setItem('last_upload', uploadData);
        
        // 処理画面への遷移準備
        const processingButton = document.getElementById('start-processing');
        if (processingButton) {
            processingButton.disabled = false;
            processingButton.dataset.uploadId = uploadData.upload_id;
        }
    }
    
    handleUploadError(error) {
        console.error('Upload failed:', error);
        this.errorHandler.displayError(error);
    }
    
    hasActiveProcessing() {
        const processingId = this.storage.getItem('active_processing_id');
        return processingId !== null;
    }
    
    applyPreferences(preferences) {
        // ユーザー設定の適用
        if (preferences.theme) {
            document.body.dataset.theme = preferences.theme;
        }
        if (preferences.language) {
            document.documentElement.lang = preferences.language;
        }
    }
}

// アプリケーション初期化
document.addEventListener('DOMContentLoaded', () => {
    window.presidioApp = new PresidioPDFApp();
});
```

### ファイルアップロードコンポーネント
```javascript
// static/js/components/file-upload.js
export class FileUploadComponent {
    constructor(element, options = {}) {
        this.element = element;
        this.options = {
            maxFileSize: 50 * 1024 * 1024, // 50MB
            allowedTypes: ['application/pdf'],
            ...options
        };
        
        this.state = {
            file: null,
            uploading: false,
            uploadProgress: 0
        };
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.setupDragAndDrop();
    }
    
    bindEvents() {
        const fileInput = this.element.querySelector('#file-input');
        const uploadArea = this.element.querySelector('#upload-area');
        const removeButton = this.element.querySelector('#remove-file');
        
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        uploadArea.addEventListener('click', () => fileInput.click());
        removeButton?.addEventListener('click', () => this.removeFile());
    }
    
    setupDragAndDrop() {
        const uploadArea = this.element.querySelector('#upload-area');
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });
        
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.add('upload-area--dragover');
            });
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.remove('upload-area--dragover');
            });
        });
        
        uploadArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFile(files[0]);
            }
        });
    }
    
    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.handleFile(file);
        }
    }
    
    handleFile(file) {
        // ファイル検証
        const validation = this.validateFile(file);
        if (!validation.valid) {
            this.options.errorHandler?.displayError({
                message: validation.error,
                type: 'validation_error'
            });
            return;
        }
        
        this.state.file = file;
        this.updateUI();
        this.uploadFile();
    }
    
    validateFile(file) {
        if (file.size > this.options.maxFileSize) {
            return {
                valid: false,
                error: `ファイルサイズが制限を超えています（最大${this.formatFileSize(this.options.maxFileSize)}）`
            };
        }
        
        if (!this.options.allowedTypes.includes(file.type)) {
            return {
                valid: false,
                error: 'PDFファイルのみアップロード可能です'
            };
        }
        
        return { valid: true };
    }
    
    async uploadFile() {
        if (!this.state.file || this.state.uploading) return;
        
        this.state.uploading = true;
        this.updateUI();
        
        try {
            const formData = new FormData();
            formData.append('file', this.state.file);
            
            const response = await this.options.apiClient.upload(formData, {
                onProgress: (progress) => {
                    this.state.uploadProgress = progress;
                    this.updateUploadProgress();
                }
            });
            
            this.state.uploading = false;
            this.options.onUploadSuccess?.(response);
        } catch (error) {
            this.state.uploading = false;
            this.options.onUploadError?.(error);
        }
        
        this.updateUI();
    }
    
    updateUI() {
        const uploadArea = this.element.querySelector('#upload-area');
        const fileInfo = this.element.querySelector('#file-info');
        const uploadProgress = this.element.querySelector('#upload-progress');
        
        if (this.state.file) {
            uploadArea.style.display = 'none';
            fileInfo.style.display = 'flex';
            
            const fileName = fileInfo.querySelector('#file-name');
            const fileSize = fileInfo.querySelector('#file-size');
            
            fileName.textContent = this.state.file.name;
            fileSize.textContent = this.formatFileSize(this.state.file.size);
        }
        
        if (this.state.uploading) {
            uploadProgress.style.display = 'block';
        } else {
            uploadProgress.style.display = 'none';
        }
    }
    
    updateUploadProgress() {
        const progressFill = this.element.querySelector('#upload-progress-fill');
        const progressText = this.element.querySelector('#upload-progress-text');
        
        progressFill.style.width = `${this.state.uploadProgress}%`;
        progressText.textContent = `${Math.round(this.state.uploadProgress)}%`;
    }
    
    removeFile() {
        this.state.file = null;
        this.state.uploading = false;
        this.state.uploadProgress = 0;
        
        const fileInput = this.element.querySelector('#file-input');
        fileInput.value = '';
        
        const uploadArea = this.element.querySelector('#upload-area');
        const fileInfo = this.element.querySelector('#file-info');
        const uploadProgress = this.element.querySelector('#upload-progress');
        
        uploadArea.style.display = 'block';
        fileInfo.style.display = 'none';
        uploadProgress.style.display = 'none';
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}
```

## レスポンシブ対応

### モバイルファーストアプローチ
```css
/* モバイル（デフォルト） */
.container {
    padding: var(--spacing-4);
}

.grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--spacing-4);
}

/* タブレット */
@media (min-width: 768px) {
    .container {
        padding: var(--spacing-6);
    }
    
    .grid {
        grid-template-columns: repeat(2, 1fr);
        gap: var(--spacing-6);
    }
}

/* デスクトップ */
@media (min-width: 1024px) {
    .container {
        padding: var(--spacing-8);
    }
    
    .grid {
        grid-template-columns: repeat(3, 1fr);
        gap: var(--spacing-8);
    }
}
```

## アクセシビリティ対応

### WCAG 2.1準拠
```html
<!-- セマンティックHTML -->
<main role="main" aria-label="メインコンテンツ">
    <section aria-labelledby="upload-section-title">
        <h2 id="upload-section-title">ファイルアップロード</h2>
        
        <div class="file-upload" 
             role="region" 
             aria-label="PDFファイルアップロード"
             aria-describedby="upload-instructions">
            
            <p id="upload-instructions" class="sr-only">
                PDFファイルを選択してアップロードしてください。最大ファイルサイズは50MBです。
            </p>
            
            <button type="button" 
                    class="upload-button"
                    aria-describedby="file-requirements">
                <span aria-hidden="true">📄</span>
                ファイルを選択
            </button>
            
            <div id="file-requirements" class="text-sm text-gray-600">
                対応形式: PDF / 最大サイズ: 50MB
            </div>
        </div>
    </section>
</main>
```