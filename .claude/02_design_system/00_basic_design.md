# デザインシステム基本設計

## 概要
PresidioPDF Web UIの統一的なデザインシステムを定義する。視覚的一貫性、ユーザビリティ、アクセシビリティを確保し、効率的な開発とメンテナンスを可能にする。

## デザイン哲学

### コアバリュー
```yaml
design_values:
  simplicity: "シンプルで直感的なインターフェース"
  trustworthiness: "個人情報を扱うツールとしての信頼性"
  accessibility: "すべてのユーザーが使いやすいデザイン"
  efficiency: "タスク完了までの効率性"
  transparency: "処理状況の明確な可視化"
```

### デザイン原則
1. **機能優先**: 装飾よりも機能性を重視
2. **一貫性**: 全画面で統一されたUI要素
3. **予測可能性**: ユーザーの期待に沿った動作
4. **フィードバック**: すべての操作に明確な反応
5. **エラー防止**: ミスを未然に防ぐUI設計

## ビジュアル・アイデンティティ

### ブランドカラー
```css
/* プライマリカラー（信頼性を表現） */
:root {
  --primary-50: #eff6ff;
  --primary-100: #dbeafe;
  --primary-200: #bfdbfe;
  --primary-300: #93c5fd;
  --primary-400: #60a5fa;
  --primary-500: #3b82f6;  /* メインブランドカラー */
  --primary-600: #2563eb;
  --primary-700: #1d4ed8;
  --primary-800: #1e40af;
  --primary-900: #1e3a8a;
}

/* セカンダリカラー（安全性を表現） */
:root {
  --secondary-50: #f0fdf4;
  --secondary-100: #dcfce7;
  --secondary-200: #bbf7d0;
  --secondary-300: #86efac;
  --secondary-400: #4ade80;
  --secondary-500: #22c55e;  /* 成功・安全色 */
  --secondary-600: #16a34a;
  --secondary-700: #15803d;
  --secondary-800: #166534;
  --secondary-900: #14532d;
}

/* 警告・エラーカラー */
:root {
  --warning-500: #f59e0b;   /* 警告色 */
  --error-500: #ef4444;     /* エラー色 */
  --info-500: #06b6d4;      /* 情報色 */
}
```

### グレースケールパレット
```css
:root {
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
}
```

## タイポグラフィ

### フォントスタック
```css
:root {
  --font-family-sans: 'Noto Sans JP', 'Hiragino Sans', 'ヒラギノ角ゴ ProN W3', 
                       'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'YuGothic', 
                       'Meiryo', sans-serif;
  --font-family-mono: 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 
                       'Liberation Mono', 'Courier New', monospace;
}
```

### フォントサイズスケール
```css
:root {
  --text-xs: 0.75rem;    /* 12px - キャプション */
  --text-sm: 0.875rem;   /* 14px - 説明文 */
  --text-base: 1rem;     /* 16px - 本文 */
  --text-lg: 1.125rem;   /* 18px - 小見出し */
  --text-xl: 1.25rem;    /* 20px - 見出し */
  --text-2xl: 1.5rem;    /* 24px - 大見出し */
  --text-3xl: 1.875rem;  /* 30px - ページタイトル */
  --text-4xl: 2.25rem;   /* 36px - 特大見出し */
}
```

### 行間・文字間隔
```css
:root {
  --leading-tight: 1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;
  --leading-loose: 2;
  
  --tracking-tight: -0.025em;
  --tracking-normal: 0;
  --tracking-wide: 0.025em;
}
```

## スペーシングシステム

### 基本スペーシング
```css
:root {
  --space-px: 1px;
  --space-0: 0;
  --space-1: 0.25rem;  /* 4px */
  --space-2: 0.5rem;   /* 8px */
  --space-3: 0.75rem;  /* 12px */
  --space-4: 1rem;     /* 16px */
  --space-5: 1.25rem;  /* 20px */
  --space-6: 1.5rem;   /* 24px */
  --space-8: 2rem;     /* 32px */
  --space-10: 2.5rem;  /* 40px */
  --space-12: 3rem;    /* 48px */
  --space-16: 4rem;    /* 64px */
  --space-20: 5rem;    /* 80px */
  --space-24: 6rem;    /* 96px */
}
```

### コンポーネント間隔ルール
- **要素内余白**: 8px, 16px, 24px
- **コンポーネント間**: 16px, 24px, 32px
- **セクション間**: 32px, 48px, 64px
- **ページ余白**: 16px (モバイル), 24px (タブレット), 32px (デスクトップ)

## ボーダー・シャドウ

### ボーダー半径
```css
:root {
  --rounded-none: 0;
  --rounded-sm: 0.125rem;   /* 2px */
  --rounded: 0.25rem;       /* 4px - 標準 */
  --rounded-md: 0.375rem;   /* 6px */
  --rounded-lg: 0.5rem;     /* 8px - カード */
  --rounded-xl: 0.75rem;    /* 12px */
  --rounded-2xl: 1rem;      /* 16px */
  --rounded-full: 9999px;   /* 完全な円形 */
}
```

### ボックスシャドウ
```css
:root {
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}
```

## コンポーネント基本定義

### ボタンスタイル
```css
/* ボタンベーススタイル */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-6);
  border: 1px solid transparent;
  border-radius: var(--rounded);
  font-size: var(--text-base);
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: all 150ms ease-in-out;
  outline: none;
  user-select: none;
}

/* ボタンバリアント */
.btn--primary {
  background-color: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

.btn--primary:hover:not(:disabled) {
  background-color: var(--primary-600);
  border-color: var(--primary-600);
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
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
}

.btn--lg {
  padding: var(--space-4) var(--space-8);
  font-size: var(--text-lg);
}

/* ボタン状態 */
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn:focus-visible {
  outline: 2px solid var(--primary-500);
  outline-offset: 2px;
}
```

### フォームコントロール
```css
/* 入力フィールドベーススタイル */
.form-control {
  display: block;
  width: 100%;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--gray-300);
  border-radius: var(--rounded);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  color: var(--gray-800);
  background-color: white;
  transition: border-color 150ms ease-in-out, box-shadow 150ms ease-in-out;
}

.form-control:focus {
  outline: none;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-control:disabled {
  background-color: var(--gray-100);
  cursor: not-allowed;
}

/* ラベル */
.form-label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--gray-700);
}

/* ヘルプテキスト */
.form-help {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--gray-500);
}

/* エラーメッセージ */
.form-error {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--error-500);
}
```

### カードコンポーネント
```css
.card {
  background-color: white;
  border: 1px solid var(--gray-200);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.card__header {
  padding: var(--space-6);
  border-bottom: 1px solid var(--gray-200);
}

.card__body {
  padding: var(--space-6);
}

.card__footer {
  padding: var(--space-6);
  border-top: 1px solid var(--gray-200);
  background-color: var(--gray-50);
}

.card__title {
  margin: 0 0 var(--space-2) 0;
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--gray-800);
}

.card__subtitle {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--gray-600);
}
```

## レスポンシブデザイン

### ブレークポイント
```css
:root {
  --breakpoint-sm: 640px;   /* タブレット縦 */
  --breakpoint-md: 768px;   /* タブレット横 */
  --breakpoint-lg: 1024px;  /* デスクトップ小 */
  --breakpoint-xl: 1280px;  /* デスクトップ大 */
  --breakpoint-2xl: 1536px; /* デスクトップ特大 */
}

/* メディアクエリ */
@media (min-width: 640px) { /* sm */ }
@media (min-width: 768px) { /* md */ }
@media (min-width: 1024px) { /* lg */ }
@media (min-width: 1280px) { /* xl */ }
```

### コンテナサイズ
```css
.container {
  width: 100%;
  margin: 0 auto;
  padding: 0 var(--space-4);
}

@media (min-width: 640px) {
  .container {
    max-width: 640px;
  }
}

@media (min-width: 768px) {
  .container {
    max-width: 768px;
    padding: 0 var(--space-6);
  }
}

@media (min-width: 1024px) {
  .container {
    max-width: 1024px;
    padding: 0 var(--space-8);
  }
}

@media (min-width: 1280px) {
  .container {
    max-width: 1280px;
  }
}
```

## アクセシビリティ基準

### WCAG 2.1 対応
```css
/* フォーカス管理 */
:focus-visible {
  outline: 2px solid var(--primary-500);
  outline-offset: 2px;
}

/* 色覚対応 */
.status--success {
  color: var(--secondary-600);
}
.status--success::before {
  content: '✓ ';
  font-weight: bold;
}

.status--error {
  color: var(--error-500);
}
.status--error::before {
  content: '⚠ ';
  font-weight: bold;
}

/* 縮小表示対応 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

/* ハイコントラスト対応 */
@media (prefers-contrast: high) {
  :root {
    --gray-300: #999;
    --gray-400: #777;
    --gray-500: #555;
  }
}
```

### スクリーンリーダー対応
```css
/* スクリーンリーダー専用テキスト */
.sr-only {
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

.sr-only-focusable:focus {
  position: static;
  width: auto;
  height: auto;
  padding: inherit;
  margin: inherit;
  overflow: visible;
  clip: auto;
  white-space: normal;
}
```

## ダークモード対応

### カラートークン拡張
```css
/* ライトモード（デフォルト） */
:root {
  --bg-primary: white;
  --bg-secondary: var(--gray-50);
  --text-primary: var(--gray-800);
  --text-secondary: var(--gray-600);
  --border-color: var(--gray-200);
}

/* ダークモード */
@media (prefers-color-scheme: dark) {
  :root {
    --bg-primary: var(--gray-900);
    --bg-secondary: var(--gray-800);
    --text-primary: var(--gray-100);
    --text-secondary: var(--gray-400);
    --border-color: var(--gray-700);
  }
}

/* 手動ダークモード切り替え */
[data-theme='dark'] {
  --bg-primary: var(--gray-900);
  --bg-secondary: var(--gray-800);
  --text-primary: var(--gray-100);
  --text-secondary: var(--gray-400);
  --border-color: var(--gray-700);
}
```

## 使用ガイダンス

### コンポーネント選択指針
1. **ボタン**: プライマリは主要アクション、セカンダリは補助アクション
2. **カラー**: エラーは赤、成功は緑、警告は黄色、情報は青
3. **スペーシング**: 関連要素は近く、異なるグループは遠く配置
4. **タイポグラフィ**: 階層を明確にし、読みやすさを優先

### 実装時の注意点
- CSS変数を活用し、マジックナンバーを避ける
- レスポンシブ対応を最初から考慮する
- アクセシビリティチェックを定期的に実施する
- 一貫性のあるネーミング規則に従う