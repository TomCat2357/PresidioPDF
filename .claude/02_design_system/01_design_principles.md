# デザイン原則

## 概要
PresidioPDF Web UIの設計判断を導く基本原則を定義する。これらの原則は、ユーザビリティ、アクセシビリティ、技術的実現可能性のバランスを保ちながら、一貫性のある優れたユーザー体験を創出するための指針となる。

## 1. ユーザー中心設計（User-Centered Design）

### 基本思想
個人情報処理という重要なタスクを行うユーザーのニーズ、不安、期待を最優先に考慮する。

### 具体的な適用
```css
/* ユーザーの心理的負担を軽減する色彩設計 */
:root {
  --color-trust: #3b82f6;      /* 信頼性を表現する青色 */
  --color-safety: #22c55e;     /* 安全性を表現する緑色 */
  --color-caution: #f59e0b;    /* 注意を促す黄色 */
  --color-danger: #ef4444;     /* 危険を表現する赤色 */
}

/* 心理的安全性を高めるコンテナ設計 */
.secure-container {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border: 1px solid var(--color-trust);
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.1);
}

.secure-container::before {
  content: '🔒';
  display: inline-block;
  margin-right: 8px;
  opacity: 0.7;
}
```

### 設計チェックリスト
- [ ] ユーザーの目標達成を最優先にしているか？
- [ ] 認知的負荷を最小限に抑えているか？
- [ ] エラーからの回復が容易か？
- [ ] プライバシーへの配慮が十分か？

## 2. 透明性とフィードバック（Transparency & Feedback）

### 基本思想
処理状況、エラー内容、システムの動作をユーザーに明確に伝える。

### プログレス表示設計
```css
/* 段階的プログレス表示 */
.progress-indicator {
  width: 100%;
  background: var(--gray-200);
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar {
  height: 8px;
  background: linear-gradient(90deg, var(--color-trust), var(--color-safety));
  border-radius: 4px;
  transition: width 0.3s ease-in-out;
  position: relative;
}

.progress-bar::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.2) 50%,
    transparent 100%
  );
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
```

### ステータス表示システム
```html
<!-- 処理段階の明示 -->
<div class="processing-status">
  <div class="status-step active" data-step="1">
    <span class="step-icon">📄</span>
    <span class="step-text">ファイル読み込み</span>
  </div>
  <div class="status-step" data-step="2">
    <span class="step-icon">🔍</span>
    <span class="step-text">個人情報検出</span>
  </div>
  <div class="status-step" data-step="3">
    <span class="step-icon">🛡️</span>
    <span class="step-text">マスキング処理</span>
  </div>
  <div class="status-step" data-step="4">
    <span class="step-icon">✅</span>
    <span class="step-text">完了</span>
  </div>
</div>
```

### 実装原則
- 処理時間が3秒以上かかる場合は進捗表示を必須とする
- エラーメッセージには解決策を含める
- 成功時には具体的な結果を表示する

## 3. 一貫性と予測可能性（Consistency & Predictability）

### 視覚的一貫性
```css
/* 統一された間隔システム */
.component-spacing {
  /* 要素内の間隔: 8の倍数 */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
}

/* 一貫したボタン設計 */
.btn-base {
  height: 40px;
  padding: 0 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
  
  /* すべてのボタンに共通するフォーカススタイル */
  &:focus-visible {
    outline: 2px solid var(--color-trust);
    outline-offset: 2px;
  }
}
```

### インタラクションパターン
```css
/* 統一されたホバー効果 */
.interactive-element {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.interactive-element:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 一貫したローディング状態 */
.loading-state {
  position: relative;
  pointer-events: none;
  opacity: 0.7;
}

.loading-state::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-trust);
  border-top-color: transparent;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  animation: spin 1s linear infinite;
}
```

## 4. セキュリティの可視化（Security Visualization）

### セキュリティ指標の表現
```css
/* セキュリティレベル表示 */
.security-indicator {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-radius: 6px;
  font-weight: 500;
}

.security-indicator--high {
  background: rgba(34, 197, 94, 0.1);
  color: var(--color-safety);
  border-left: 4px solid var(--color-safety);
}

.security-indicator--medium {
  background: rgba(245, 158, 11, 0.1);
  color: var(--color-caution);
  border-left: 4px solid var(--color-caution);
}

.security-indicator--low {
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  border-left: 4px solid var(--color-danger);
}

/* データ保護状況の可視化 */
.data-protection-status {
  position: relative;
  background: linear-gradient(135deg, #e0f2fe, #f0f9ff);
  border: 1px solid rgba(59, 130, 246, 0.2);
  padding: 16px;
  border-radius: 8px;
}

.data-protection-status::before {
  content: '🛡️';
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0.5;
}
```

### 個人情報マスキング視覚表現
```css
/* マスキング済みテキストの表現 */
.masked-text {
  background: repeating-linear-gradient(
    45deg,
    var(--color-safety),
    var(--color-safety) 2px,
    transparent 2px,
    transparent 6px
  );
  color: transparent;
  border-radius: 2px;
  position: relative;
}

.masked-text::after {
  content: '■■■■';
  position: absolute;
  top: 0;
  left: 0;
  color: var(--color-safety);
  font-weight: bold;
}

/* 検出された個人情報のハイライト */
.detected-pii {
  background: rgba(239, 68, 68, 0.15);
  border-bottom: 2px solid var(--color-danger);
  padding: 2px 4px;
  border-radius: 3px;
  position: relative;
}

.detected-pii::before {
  content: attr(data-entity-type);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-danger);
  color: white;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 10px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.detected-pii:hover::before {
  opacity: 1;
}
```

## 5. 効率性と生産性（Efficiency & Productivity）

### ショートカット・キーボードナビゲーション
```css
/* キーボードショートカット表示 */
.keyboard-shortcut {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--gray-600);
  background: var(--gray-100);
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid var(--gray-300);
  font-family: var(--font-mono);
}

/* フォーカストラップの可視化 */
.focus-trap-active {
  outline: 2px solid var(--color-trust);
  outline-offset: -2px;
  border-radius: 4px;
}

/* タブナビゲーション強化 */
[tabindex]:focus-visible {
  outline: 2px solid var(--color-trust);
  outline-offset: 2px;
}
```

### バッチ操作UI
```html
<!-- 複数ファイル処理インターフェース -->
<div class="batch-operation-panel">
  <div class="batch-header">
    <h3>一括処理</h3>
    <div class="file-counter">
      <span class="selected-count">3</span> / 
      <span class="total-count">5</span> ファイル選択中
    </div>
  </div>
  
  <div class="batch-controls">
    <button class="btn btn--primary" data-action="process-all">
      全て処理開始
    </button>
    <button class="btn btn--secondary" data-action="select-all">
      全選択
    </button>
    <button class="btn btn--secondary" data-action="clear-selection">
      選択解除
    </button>
  </div>
</div>
```

## 6. アクセシビリティファースト（Accessibility First）

### 色覚対応
```css
/* 色だけに依存しない情報伝達 */
.status-success {
  color: var(--color-safety);
}
.status-success::before {
  content: '✓ ';
  font-weight: bold;
}

.status-error {
  color: var(--color-danger);
}
.status-error::before {
  content: '⚠ ';
  font-weight: bold;
}

.status-processing {
  color: var(--color-trust);
}
.status-processing::before {
  content: '⟳ ';
  animation: spin 2s linear infinite;
}
```

### スクリーンリーダー対応
```html
<!-- 意味のある構造化 -->
<main role="main" aria-label="PDF個人情報マスキング">
  <section aria-labelledby="upload-heading">
    <h2 id="upload-heading">ファイルアップロード</h2>
    
    <div class="upload-area" 
         role="region" 
         aria-label="PDFファイルアップロード領域"
         aria-describedby="upload-instructions">
      
      <p id="upload-instructions" class="sr-only">
        PDFファイルをドラッグアンドドロップするか、
        ファイル選択ボタンをクリックしてファイルを選択してください。
      </p>
      
      <input type="file" 
             id="file-input"
             accept=".pdf"
             aria-label="PDFファイル選択">
    </div>
  </section>
  
  <section aria-labelledby="processing-heading" aria-live="polite">
    <h2 id="processing-heading">処理状況</h2>
    <div id="processing-status" role="status"></div>
  </section>
</main>
```

## 7. パフォーマンスと応答性（Performance & Responsiveness）

### 知覚パフォーマンス向上
```css
/* スケルトンローディング */
.skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: loading 1.5s infinite;
}

@keyframes loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skeleton-text {
  height: 16px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.skeleton-text:last-child {
  width: 60%;
}

/* 遅延ローディングの表現 */
.lazy-loading {
  background: var(--gray-100);
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
}

.lazy-loading::after {
  content: '読み込み中...';
  color: var(--gray-600);
  font-size: 14px;
}
```

### レスポンシブ最適化
```css
/* コンテント優先のレスポンシブ */
.content-priority-container {
  display: flex;
  flex-direction: column;
}

@media (min-width: 768px) {
  .content-priority-container {
    flex-direction: row;
    gap: 24px;
  }
  
  .content-priority-container > .primary-content {
    flex: 2;
    order: 1;
  }
  
  .content-priority-container > .secondary-content {
    flex: 1;
    order: 2;
  }
}

/* タッチフレンドリー設計 */
@media (pointer: coarse) {
  .btn,
  .interactive-element {
    min-height: 44px;
    min-width: 44px;
  }
  
  .file-upload-area {
    padding: 32px;
  }
}
```

## 8. エラー防止と回復（Error Prevention & Recovery）

### プリベンティブUX
```html
<!-- エラー防止の入力支援 -->
<div class="form-group">
  <label for="email" class="form-label">
    メールアドレス
    <span class="required-indicator" aria-label="必須">*</span>
  </label>
  
  <input type="email" 
         id="email"
         class="form-control"
         pattern="[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
         aria-describedby="email-help email-error"
         required>
         
  <div id="email-help" class="form-help">
    例: user@example.com
  </div>
  
  <div id="email-error" class="form-error" role="alert" aria-live="polite">
    <!-- エラーメッセージ動的挿入 -->
  </div>
</div>
```

### グレースフルデグラデーション
```css
/* 機能低下時の代替表現 */
.enhanced-feature {
  /* 最新ブラウザ向け機能 */
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

/* フォールバック */
.no-grid .enhanced-feature {
  display: block;
}

.no-grid .enhanced-feature > * {
  margin-bottom: 24px;
  width: 100%;
  max-width: 500px;
}

/* JavaScript無効時の対応 */
.no-js .js-required {
  display: none;
}

.no-js .js-fallback {
  display: block;
  padding: 16px;
  background: var(--color-caution);
  color: white;
  border-radius: 6px;
}
```

## 設計原則適用チェックリスト

### 新機能開発時
- [ ] ユーザーの主目標達成を妨げていないか？
- [ ] 一貫性のあるビジュアル言語を使用しているか？
- [ ] アクセシビリティ要件を満たしているか？
- [ ] エラー状態の処理が適切か？
- [ ] パフォーマンスへの影響を考慮したか？

### レビュー時の観点
- [ ] 認知的負荷が適切なレベルか？
- [ ] セキュリティ面の配慮が可視化されているか？
- [ ] レスポンシブ対応が十分か？
- [ ] キーボード操作が可能か？
- [ ] エラーメッセージが建設的か？

これらの設計原則は、PresidioPDF Web UIの開発・改善において常に参照される基準として機能し、優れたユーザー体験の実現を支援します。