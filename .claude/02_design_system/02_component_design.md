# コンポーネント設計

## 概要
PresidioPDF Web UIの再利用可能なUIコンポーネントライブラリを定義する。モジュラー設計、保守性、拡張性を重視し、開発効率と品質の向上を図る。

## コンポーネント分類体系

### 階層構造
```
Components/
├── Foundation/          # 基盤要素
│   ├── Typography
│   ├── Colors
│   ├── Spacing
│   └── Grid
├── Atoms/              # 最小単位コンポーネント
│   ├── Button
│   ├── Input
│   ├── Icon
│   ├── Badge
│   └── Avatar
├── Molecules/          # 複合コンポーネント
│   ├── Form Field
│   ├── Search Box
│   ├── Card Header
│   ├── Progress Bar
│   └── Alert
├── Organisms/          # 複雑なコンポーネント群
│   ├── Header
│   ├── File Upload
│   ├── Processing Panel
│   ├── Results Table
│   └── Settings Panel
└── Templates/          # ページレイアウト
    ├── Home Layout
    ├── Processing Layout
    └── Results Layout
```

## Atoms（原子）コンポーネント

### Button（ボタン）
```css
/* ボタンベース */
.btn {
  /* 基本スタイル */
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-6);
  border: 1px solid transparent;
  border-radius: var(--rounded);
  font-family: inherit;
  font-size: var(--text-base);
  font-weight: 500;
  line-height: 1;
  text-decoration: none;
  text-align: center;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  
  /* アニメーション */
  transition: all var(--transition-fast);
  
  /* フォーカス */
  &:focus-visible {
    outline: 2px solid var(--primary-500);
    outline-offset: 2px;
  }
  
  /* 無効状態 */
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    pointer-events: none;
  }
}

/* ボタンバリアント */
.btn--primary {
  background-color: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
  
  &:hover:not(:disabled) {
    background-color: var(--primary-600);
    border-color: var(--primary-600);
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }
  
  &:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: var(--shadow-sm);
  }
}

.btn--secondary {
  background-color: transparent;
  color: var(--gray-700);
  border-color: var(--gray-300);
  
  &:hover:not(:disabled) {
    background-color: var(--gray-50);
    border-color: var(--gray-400);
  }
}

.btn--danger {
  background-color: var(--error-500);
  color: white;
  border-color: var(--error-500);
  
  &:hover:not(:disabled) {
    background-color: #dc2626;
    border-color: #dc2626;
  }
}

/* ボタンサイズ */
.btn--sm {
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  min-height: 32px;
}

.btn--md {
  padding: var(--space-3) var(--space-6);
  font-size: var(--text-base);
  min-height: 40px;
}

.btn--lg {
  padding: var(--space-4) var(--space-8);
  font-size: var(--text-lg);
  min-height: 48px;
}

/* ボタン形状 */
.btn--round {
  border-radius: var(--rounded-full);
}

.btn--icon-only {
  aspect-ratio: 1;
  padding: var(--space-3);
}
```

### Input（入力フィールド）
```css
.input {
  /* 基本スタイル */
  display: block;
  width: 100%;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--gray-300);
  border-radius: var(--rounded);
  font-family: inherit;
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  color: var(--gray-800);
  background-color: white;
  appearance: none;
  
  /* プレースホルダー */
  &::placeholder {
    color: var(--gray-400);
  }
  
  /* フォーカス */
  &:focus {
    outline: none;
    border-color: var(--primary-500);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
  
  /* 無効状態 */
  &:disabled {
    background-color: var(--gray-100);
    color: var(--gray-500);
    cursor: not-allowed;
  }
  
  /* エラー状態 */
  &.input--error {
    border-color: var(--error-500);
    
    &:focus {
      border-color: var(--error-500);
      box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
    }
  }
  
  /* 成功状態 */
  &.input--success {
    border-color: var(--success-500);
    
    &:focus {
      border-color: var(--success-500);
      box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.1);
    }
  }
}

/* 入力サイズ */
.input--sm {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
}

.input--lg {
  padding: var(--space-4) var(--space-5);
  font-size: var(--text-lg);
}
```

### Icon（アイコン）
```css
.icon {
  display: inline-block;
  width: 1em;
  height: 1em;
  fill: currentColor;
  vertical-align: middle;
  flex-shrink: 0;
}

/* アイコンサイズ */
.icon--xs { font-size: 12px; }
.icon--sm { font-size: 14px; }
.icon--md { font-size: 16px; }
.icon--lg { font-size: 20px; }
.icon--xl { font-size: 24px; }

/* アイコンアニメーション */
.icon--spin {
  animation: spin 1s linear infinite;
}

.icon--pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### Badge（バッジ）
```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--rounded-full);
  font-size: var(--text-xs);
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
}

/* バッジバリアント */
.badge--primary {
  background-color: var(--primary-100);
  color: var(--primary-800);
}

.badge--success {
  background-color: var(--success-100);
  color: var(--success-800);
}

.badge--warning {
  background-color: var(--warning-100);
  color: var(--warning-800);
}

.badge--error {
  background-color: var(--error-100);
  color: var(--error-800);
}

.badge--gray {
  background-color: var(--gray-100);
  color: var(--gray-800);
}

/* バッジサイズ */
.badge--sm {
  padding: var(--space-px) var(--space-2);
  font-size: 10px;
}

.badge--lg {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
}
```

## Molecules（分子）コンポーネント

### Form Field（フォームフィールド）
```css
.form-field {
  margin-bottom: var(--space-6);
}

.form-label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--gray-700);
  
  /* 必須マーク */
  .required::after {
    content: ' *';
    color: var(--error-500);
  }
}

.form-input-wrapper {
  position: relative;
}

/* アイコン付き入力 */
.form-input-wrapper--with-icon {
  .input {
    padding-left: var(--space-10);
  }
  
  .form-icon {
    position: absolute;
    left: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    color: var(--gray-400);
    pointer-events: none;
  }
}

.form-help {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--gray-500);
}

.form-error {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--error-500);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.form-error::before {
  content: '⚠';
  font-weight: bold;
}
```

### Progress Bar（プログレスバー）
```css
.progress {
  width: 100%;
  height: 8px;
  background-color: var(--gray-200);
  border-radius: var(--rounded-full);
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(
    90deg,
    var(--primary-500),
    var(--primary-400)
  );
  border-radius: inherit;
  transition: width 0.3s ease-in-out;
  position: relative;
}

/* アニメーション付きプログレスバー */
.progress-bar--animated::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    transparent
  );
  animation: progress-shine 2s ease-in-out infinite;
}

@keyframes progress-shine {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* プログレス情報表示 */
.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
  font-size: var(--text-sm);
  color: var(--gray-600);
}

.progress-label {
  font-weight: 500;
}

.progress-percentage {
  color: var(--gray-800);
  font-weight: 600;
}
```

### Alert（アラート）
```css
.alert {
  padding: var(--space-4);
  border-radius: var(--rounded-md);
  border-left: 4px solid;
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.alert-icon {
  flex-shrink: 0;
  margin-top: 2px;
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-title {
  font-weight: 600;
  margin-bottom: var(--space-1);
}

.alert-message {
  color: inherit;
  opacity: 0.9;
}

/* アラートバリアント */
.alert--info {
  background-color: var(--info-50);
  color: var(--info-800);
  border-left-color: var(--info-500);
}

.alert--success {
  background-color: var(--success-50);
  color: var(--success-800);
  border-left-color: var(--success-500);
}

.alert--warning {
  background-color: var(--warning-50);
  color: var(--warning-800);
  border-left-color: var(--warning-500);
}

.alert--error {
  background-color: var(--error-50);
  color: var(--error-800);
  border-left-color: var(--error-500);
}

/* 閉じるボタン付きアラート */
.alert--dismissible {
  padding-right: var(--space-10);
  position: relative;
}

.alert-dismiss {
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
  background: none;
  border: none;
  color: inherit;
  opacity: 0.7;
  cursor: pointer;
  padding: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--rounded-sm);
  
  &:hover {
    opacity: 1;
    background-color: rgba(0, 0, 0, 0.1);
  }
}
```

## Organisms（組織）コンポーネント

### File Upload（ファイルアップロード）
```css
.file-upload {
  border: 2px dashed var(--gray-300);
  border-radius: var(--rounded-lg);
  padding: var(--space-8);
  text-align: center;
  background-color: var(--gray-50);
  transition: all var(--transition-fast);
  cursor: pointer;
  position: relative;
}

.file-upload:hover {
  border-color: var(--primary-400);
  background-color: var(--primary-50);
}

.file-upload--dragover {
  border-color: var(--primary-500);
  background-color: var(--primary-100);
  transform: scale(1.02);
}

.file-upload--error {
  border-color: var(--error-500);
  background-color: var(--error-50);
}

.file-upload-icon {
  font-size: 48px;
  color: var(--gray-400);
  margin-bottom: var(--space-4);
}

.file-upload-title {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--gray-800);
  margin-bottom: var(--space-2);
}

.file-upload-description {
  color: var(--gray-600);
  margin-bottom: var(--space-4);
}

.file-upload-constraints {
  font-size: var(--text-sm);
  color: var(--gray-500);
}

.file-upload-input {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* アップロード済みファイル表示 */
.file-upload--has-file {
  border-style: solid;
  border-color: var(--success-500);
  background-color: var(--success-50);
}

.uploaded-file-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
  padding: var(--space-4);
  border-radius: var(--rounded);
  border: 1px solid var(--success-200);
  margin-top: var(--space-4);
}

.uploaded-file-details {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.uploaded-file-name {
  font-weight: 500;
  color: var(--gray-800);
}

.uploaded-file-size {
  font-size: var(--text-sm);
  color: var(--gray-600);
}

.uploaded-file-remove {
  background: none;
  border: none;
  color: var(--gray-500);
  cursor: pointer;
  padding: var(--space-1);
  border-radius: var(--rounded-sm);
  
  &:hover {
    color: var(--error-500);
    background-color: var(--error-50);
  }
}
```

### Processing Panel（処理パネル）
```css
.processing-panel {
  background: white;
  border: 1px solid var(--gray-200);
  border-radius: var(--rounded-lg);
  padding: var(--space-6);
  box-shadow: var(--shadow-sm);
}

.processing-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-6);
}

.processing-title {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--gray-800);
}

.processing-cancel {
  /* cancel button styles */
}

.processing-steps {
  margin-bottom: var(--space-6);
}

.processing-step {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-left: 3px solid var(--gray-200);
  padding-left: var(--space-4);
  margin-left: var(--space-2);
  position: relative;
}

.processing-step::before {
  content: '';
  position: absolute;
  left: -6px;
  top: 50%;
  transform: translateY(-50%);
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--gray-200);
  border: 2px solid white;
  box-shadow: 0 0 0 1px var(--gray-200);
}

.processing-step--active {
  border-left-color: var(--primary-500);
  
  &::before {
    background-color: var(--primary-500);
    box-shadow: 0 0 0 1px var(--primary-500);
  }
}

.processing-step--completed {
  border-left-color: var(--success-500);
  
  &::before {
    background-color: var(--success-500);
    box-shadow: 0 0 0 1px var(--success-500);
    content: '✓';
    font-size: 8px;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 12px;
    height: 12px;
    left: -7px;
  }
}

.processing-step-icon {
  font-size: var(--text-lg);
}

.processing-step-content {
  flex: 1;
}

.processing-step-title {
  font-weight: 500;
  color: var(--gray-800);
}

.processing-step-description {
  font-size: var(--text-sm);
  color: var(--gray-600);
  margin-top: var(--space-1);
}

.processing-progress {
  margin-bottom: var(--space-4);
}

.processing-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-4);
  background-color: var(--gray-50);
  padding: var(--space-4);
  border-radius: var(--rounded);
}

.processing-stat {
  text-align: center;
}

.processing-stat-value {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--primary-600);
}

.processing-stat-label {
  font-size: var(--text-sm);
  color: var(--gray-600);
  margin-top: var(--space-1);
}
```

## Templates（テンプレート）

### Layout Base（基本レイアウト）
```css
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.layout-header {
  background: white;
  border-bottom: 1px solid var(--gray-200);
  padding: 0 var(--space-6);
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}

.layout-main {
  flex: 1;
  padding: var(--space-6);
  background-color: var(--gray-50);
}

.layout-container {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.layout-footer {
  background: white;
  border-top: 1px solid var(--gray-200);
  padding: var(--space-6);
  text-align: center;
  color: var(--gray-600);
  font-size: var(--text-sm);
}

/* レスポンシブレイアウト */
@media (max-width: 768px) {
  .layout-header,
  .layout-main,
  .layout-footer {
    padding-left: var(--space-4);
    padding-right: var(--space-4);
  }
}
```

## コンポーネント命名規則

### BEM記法準拠
```css
/* Block */
.card { }

/* Element */
.card__header { }
.card__body { }
.card__footer { }

/* Modifier */
.card--elevated { }
.card--compact { }
.card__header--with-actions { }

/* State */
.card.is-loading { }
.card.is-error { }
```

### 状態管理クラス
```css
/* 表示状態 */
.is-hidden { display: none !important; }
.is-visible { display: block !important; }

/* インタラクション状態 */
.is-active { }
.is-disabled { }
.is-loading { }

/* データ状態 */
.has-error { }
.has-success { }
.has-warning { }

/* レスポンシブ表示 */
.sm:hidden { }
.md:block { }
.lg:flex { }
```

## JavaScriptとの連携

### データ属性パターン
```html
<!-- コンポーネント初期化 -->
<div class="file-upload" 
     data-component="file-upload"
     data-max-size="50MB"
     data-allowed-types="pdf">
</div>

<!-- 状態管理 -->
<button class="btn btn--primary"
        data-loading-text="処理中..."
        data-success-text="完了">
  処理開始
</button>

<!-- イベント委譲 -->
<div data-action="click->upload#handleFileSelect">
  ファイル選択
</div>
```

### コンポーネントライフサイクル
```javascript
// コンポーネント基底クラス
class Component {
  constructor(element, options = {}) {
    this.element = element;
    this.options = Object.assign({}, this.constructor.DEFAULTS, options);
    this.initialized = false;
    
    this.init();
  }
  
  init() {
    if (this.initialized) return;
    
    this.bindEvents();
    this.initialized = true;
    this.element.classList.add('is-initialized');
  }
  
  bindEvents() {
    // Override in subclasses
  }
  
  destroy() {
    this.element.classList.remove('is-initialized');
    this.initialized = false;
  }
}
```

これらのコンポーネントは、一貫性のあるデザインシステムの基盤となり、効率的な開発と保守を支援します。