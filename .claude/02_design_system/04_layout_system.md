# レイアウトシステム設計

## 概要
PresidioPDF Web UIの統一的なレイアウトシステムを定義する。レスポンシブデザイン、グリッドシステム、フレキシブルレイアウトを通じて、様々なデバイスで最適な表示を実現し、コンテンツの可読性とユーザビリティを最大化する。

## グリッドシステム基盤

### 12カラムグリッドシステム
```css
:root {
  --grid-columns: 12;
  --grid-gap: 24px;
  --grid-gap-sm: 16px;
  --grid-gap-lg: 32px;
  
  /* コンテナ最大幅 */
  --container-sm: 640px;
  --container-md: 768px;
  --container-lg: 1024px;
  --container-xl: 1280px;
  --container-2xl: 1536px;
}

/* コンテナ */
.container {
  width: 100%;
  max-width: var(--container-xl);
  margin: 0 auto;
  padding: 0 var(--space-4);
}

@media (min-width: 640px) {
  .container {
    max-width: var(--container-sm);
    padding: 0 var(--space-6);
  }
}

@media (min-width: 768px) {
  .container {
    max-width: var(--container-md);
  }
}

@media (min-width: 1024px) {
  .container {
    max-width: var(--container-lg);
    padding: 0 var(--space-8);
  }
}

@media (min-width: 1280px) {
  .container {
    max-width: var(--container-xl);
  }
}

@media (min-width: 1536px) {
  .container {
    max-width: var(--container-2xl);
  }
}

/* フルワイドコンテナ */
.container-fluid {
  width: 100%;
  padding: 0 var(--space-4);
}

@media (min-width: 768px) {
  .container-fluid {
    padding: 0 var(--space-6);
  }
}

@media (min-width: 1024px) {
  .container-fluid {
    padding: 0 var(--space-8);
  }
}
```

### CSS Grid実装
```css
.grid {
  display: grid;
  grid-template-columns: repeat(var(--grid-columns), 1fr);
  gap: var(--grid-gap);
}

/* レスポンシブギャップ */
@media (max-width: 767px) {
  .grid {
    gap: var(--grid-gap-sm);
  }
}

@media (min-width: 1024px) {
  .grid {
    gap: var(--grid-gap-lg);
  }
}

/* グリッドアイテム */
.grid-item {
  grid-column: span 1;
}

/* カラムスパン */
.col-1 { grid-column: span 1; }
.col-2 { grid-column: span 2; }
.col-3 { grid-column: span 3; }
.col-4 { grid-column: span 4; }
.col-5 { grid-column: span 5; }
.col-6 { grid-column: span 6; }
.col-7 { grid-column: span 7; }
.col-8 { grid-column: span 8; }
.col-9 { grid-column: span 9; }
.col-10 { grid-column: span 10; }
.col-11 { grid-column: span 11; }
.col-12 { grid-column: span 12; }

/* レスポンシブカラム */
@media (min-width: 640px) {
  .sm\:col-1 { grid-column: span 1; }
  .sm\:col-2 { grid-column: span 2; }
  .sm\:col-3 { grid-column: span 3; }
  .sm\:col-4 { grid-column: span 4; }
  .sm\:col-6 { grid-column: span 6; }
  .sm\:col-12 { grid-column: span 12; }
}

@media (min-width: 768px) {
  .md\:col-1 { grid-column: span 1; }
  .md\:col-2 { grid-column: span 2; }
  .md\:col-3 { grid-column: span 3; }
  .md\:col-4 { grid-column: span 4; }
  .md\:col-6 { grid-column: span 6; }
  .md\:col-8 { grid-column: span 8; }
  .md\:col-12 { grid-column: span 12; }
}

@media (min-width: 1024px) {
  .lg\:col-1 { grid-column: span 1; }
  .lg\:col-2 { grid-column: span 2; }
  .lg\:col-3 { grid-column: span 3; }
  .lg\:col-4 { grid-column: span 4; }
  .lg\:col-6 { grid-column: span 6; }
  .lg\:col-8 { grid-column: span 8; }
  .lg\:col-9 { grid-column: span 9; }
  .lg\:col-12 { grid-column: span 12; }
}
```

### Flexboxシステム
```css
.flex {
  display: flex;
}

.flex-col {
  flex-direction: column;
}

.flex-row {
  flex-direction: row;
}

.flex-wrap {
  flex-wrap: wrap;
}

.flex-nowrap {
  flex-wrap: nowrap;
}

/* 配置 */
.justify-start { justify-content: flex-start; }
.justify-end { justify-content: flex-end; }
.justify-center { justify-content: center; }
.justify-between { justify-content: space-between; }
.justify-around { justify-content: space-around; }
.justify-evenly { justify-content: space-evenly; }

.items-start { align-items: flex-start; }
.items-end { align-items: flex-end; }
.items-center { align-items: center; }
.items-baseline { align-items: baseline; }
.items-stretch { align-items: stretch; }

/* フレックスアイテム */
.flex-1 { flex: 1 1 0%; }
.flex-auto { flex: 1 1 auto; }
.flex-initial { flex: 0 1 auto; }
.flex-none { flex: none; }

.flex-grow { flex-grow: 1; }
.flex-grow-0 { flex-grow: 0; }

.flex-shrink { flex-shrink: 1; }
.flex-shrink-0 { flex-shrink: 0; }
```

## 専用レイアウトパターン

### アプリケーションレイアウト
```css
/* メインアプリレイアウト */
.app-layout {
  display: grid;
  grid-template-areas: 
    "header header"
    "sidebar main"
    "footer footer";
  grid-template-columns: 250px 1fr;
  grid-template-rows: auto 1fr auto;
  min-height: 100vh;
}

.app-header {
  grid-area: header;
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

.app-sidebar {
  grid-area: sidebar;
  background: var(--gray-50);
  border-right: 1px solid var(--gray-200);
  padding: var(--space-6);
  overflow-y: auto;
}

.app-main {
  grid-area: main;
  padding: var(--space-6);
  overflow-y: auto;
  background: white;
}

.app-footer {
  grid-area: footer;
  background: var(--gray-50);
  border-top: 1px solid var(--gray-200);
  padding: var(--space-4) var(--space-6);
  text-align: center;
  color: var(--gray-600);
}

/* レスポンシブアプリレイアウト */
@media (max-width: 768px) {
  .app-layout {
    grid-template-areas: 
      "header"
      "main"
      "footer";
    grid-template-columns: 1fr;
  }
  
  .app-sidebar {
    position: fixed;
    top: 64px;
    left: -250px;
    width: 250px;
    height: calc(100vh - 64px);
    z-index: 90;
    transition: left var(--transition-normal);
  }
  
  .app-sidebar.is-open {
    left: 0;
  }
  
  .app-main {
    position: relative;
  }
  
  .app-main::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 80;
    opacity: 0;
    visibility: hidden;
    transition: all var(--transition-normal);
  }
  
  .app-sidebar.is-open + .app-main::before {
    opacity: 1;
    visibility: visible;
  }
}
```

### カードレイアウト
```css
/* カードグリッド */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-6);
}

@media (max-width: 640px) {
  .card-grid {
    grid-template-columns: 1fr;
    gap: var(--space-4);
  }
}

/* Masonryスタイル（CSS Grid） */
.masonry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: var(--space-4);
  grid-auto-rows: max-content;
}

.masonry-item {
  break-inside: avoid;
  margin-bottom: var(--space-4);
}

/* フォールバック（CSSカラムス） */
@supports not (grid-template-rows: masonry) {
  .masonry-grid {
    column-count: 3;
    column-gap: var(--space-4);
  }
  
  @media (max-width: 768px) {
    .masonry-grid {
      column-count: 2;
    }
  }
  
  @media (max-width: 480px) {
    .masonry-grid {
      column-count: 1;
    }
  }
}
```

### フォームレイアウト
```css
/* フォームグリッド */
.form-grid {
  display: grid;
  gap: var(--space-4);
}

.form-grid--2col {
  grid-template-columns: repeat(2, 1fr);
}

.form-grid--3col {
  grid-template-columns: repeat(3, 1fr);
}

/* フィールドスパン */
.form-field--full {
  grid-column: 1 / -1;
}

.form-field--half {
  grid-column: span 1;
}

/* レスポンシブフォーム */
@media (max-width: 768px) {
  .form-grid--2col,
  .form-grid--3col {
    grid-template-columns: 1fr;
  }
}

/* インラインフォーム */
.form-inline {
  display: flex;
  align-items: end;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.form-inline .form-field {
  margin-bottom: 0;
  min-width: 200px;
  flex: 1;
}

@media (max-width: 640px) {
  .form-inline {
    flex-direction: column;
    align-items: stretch;
  }
  
  .form-inline .form-field {
    min-width: auto;
  }
}
```

## 特殊レイアウトコンポーネント

### 処理フローレイアウト
```css
.process-flow {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  grid-template-rows: repeat(3, auto);
  gap: var(--space-4) var(--space-8);
  align-items: center;
  max-width: 800px;
  margin: 0 auto;
}

.process-step {
  background: white;
  border: 2px solid var(--gray-200);
  border-radius: var(--rounded-lg);
  padding: var(--space-6);
  text-align: center;
  position: relative;
}

.process-step--active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}

.process-step--completed {
  border-color: var(--success-500);
  background: var(--success-50);
}

/* プロセス接続線 */
.process-connector {
  width: 2px;
  height: 40px;
  background: var(--gray-300);
  justify-self: center;
}

.process-connector--active {
  background: var(--primary-500);
}

.process-connector--completed {
  background: var(--success-500);
}

/* モバイルレスポンシブ */
@media (max-width: 768px) {
  .process-flow {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    gap: var(--space-4);
  }
  
  .process-connector {
    width: 40px;
    height: 2px;
    justify-self: stretch;
  }
}
```

### ダッシュボードレイアウト
```css
.dashboard {
  display: grid;
  grid-template-areas:
    "stats stats stats"
    "chart table table"
    "chart recent recent";
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto 1fr 1fr;
  gap: var(--space-6);
  min-height: 600px;
}

.dashboard-stats {
  grid-area: stats;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-4);
}

.dashboard-chart {
  grid-area: chart;
}

.dashboard-table {
  grid-area: table;
}

.dashboard-recent {
  grid-area: recent;
}

/* レスポンシブダッシュボード */
@media (max-width: 1024px) {
  .dashboard {
    grid-template-areas:
      "stats"
      "chart"
      "table"
      "recent";
    grid-template-columns: 1fr;
    grid-template-rows: none;
  }
}

@media (max-width: 640px) {
  .dashboard-stats {
    grid-template-columns: 1fr;
  }
}
```

## レスポンシブ設計パターン

### ブレークポイント戦略
```css
/* モバイルファースト設計 */
/* デフォルト: モバイル（~639px） */
.responsive-element {
  font-size: var(--text-sm);
  padding: var(--space-4);
}

/* sm: タブレット縦（640px~） */
@media (min-width: 640px) {
  .responsive-element {
    font-size: var(--text-base);
    padding: var(--space-6);
  }
}

/* md: タブレット横（768px~） */
@media (min-width: 768px) {
  .responsive-element {
    font-size: var(--text-lg);
    display: flex;
    align-items: center;
  }
}

/* lg: デスクトップ小（1024px~） */
@media (min-width: 1024px) {
  .responsive-element {
    padding: var(--space-8);
  }
}

/* xl: デスクトップ大（1280px~） */
@media (min-width: 1280px) {
  .responsive-element {
    font-size: var(--text-xl);
  }
}
```

### コンテナクエリ対応
```css
/* コンテナクエリ（未来対応） */
.component-container {
  container-type: inline-size;
}

@container (min-width: 300px) {
  .responsive-component {
    display: flex;
    gap: var(--space-4);
  }
}

@container (min-width: 500px) {
  .responsive-component {
    grid-template-columns: 1fr 2fr;
  }
}

/* フォールバック（現在のブラウザサポート） */
@supports not (container-type: inline-size) {
  @media (min-width: 640px) {
    .responsive-component {
      display: flex;
      gap: var(--space-4);
    }
  }
}
```

## アスペクト比とサイジング

### アスペクト比制御
```css
.aspect-ratio {
  position: relative;
  width: 100%;
}

.aspect-ratio::before {
  content: '';
  display: block;
  width: 100%;
  padding-bottom: calc(var(--aspect-ratio, 1) * 100%);
}

.aspect-ratio > * {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 一般的なアスペクト比 */
.aspect-square { --aspect-ratio: 1; }
.aspect-video { --aspect-ratio: 0.5625; } /* 16:9 */
.aspect-photo { --aspect-ratio: 0.75; }   /* 4:3 */

/* CSS aspect-ratio対応 */
@supports (aspect-ratio: 1) {
  .aspect-ratio {
    aspect-ratio: var(--aspect-ratio, 1);
  }
  
  .aspect-ratio::before {
    display: none;
  }
  
  .aspect-ratio > * {
    position: static;
  }
}
```

### Intrinsic Web Design
```css
/* 内在的なサイジング */
.intrinsic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
  gap: var(--space-6);
}

.intrinsic-flex {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.intrinsic-flex > * {
  flex: 1 1 min(300px, 100%);
}
```

## パフォーマンス最適化

### レイアウトシフト対策
```css
/* サイズ予約によるCLS対策 */
.content-placeholder {
  min-height: 200px;
  background: var(--gray-100);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--gray-500);
}

/* 画像プレースホルダー */
.image-placeholder {
  background: var(--gray-200);
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 16 / 9;
}

/* フォント読み込み中のレイアウト保持 */
.font-loading {
  font-display: swap;
  line-height: 1.5;
  min-height: 1.5em;
}
```

### GPU最適化レイアウト
```css
.gpu-optimized-layout {
  /* 3D変換を使用してレイヤー作成 */
  transform: translateZ(0);
  
  /* 変更予定のプロパティを事前通知 */
  will-change: transform, opacity;
}

/* スクロール最適化 */
.scroll-optimized {
  /* スクロール境界動作制御 */
  overscroll-behavior: contain;
  
  /* スムーズスクロール */
  scroll-behavior: smooth;
  
  /* スクロールバースタイリング */
  scrollbar-width: thin;
  scrollbar-color: var(--gray-400) var(--gray-100);
}

.scroll-optimized::-webkit-scrollbar {
  width: 6px;
}

.scroll-optimized::-webkit-scrollbar-track {
  background: var(--gray-100);
}

.scroll-optimized::-webkit-scrollbar-thumb {
  background: var(--gray-400);
  border-radius: 3px;
}
```

## デバッグ・開発ツール

### レイアウトデバッグ
```css
/* グリッドビジュアライザー */
.debug-grid {
  position: relative;
}

.debug-grid::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: 
    repeating-linear-gradient(
      0deg,
      rgba(255, 0, 0, 0.1),
      rgba(255, 0, 0, 0.1) 1px,
      transparent 1px,
      transparent calc(100% / var(--grid-columns))
    );
  pointer-events: none;
  z-index: 9999;
}

/* ブレークポイント表示 */
.debug-breakpoint::after {
  content: 'xs';
  position: fixed;
  top: 10px;
  left: 10px;
  background: red;
  color: white;
  padding: 4px 8px;
  font-family: monospace;
  font-size: 12px;
  z-index: 9999;
}

@media (min-width: 640px) {
  .debug-breakpoint::after {
    content: 'sm';
    background: orange;
  }
}

@media (min-width: 768px) {
  .debug-breakpoint::after {
    content: 'md';
    background: yellow;
    color: black;
  }
}

@media (min-width: 1024px) {
  .debug-breakpoint::after {
    content: 'lg';
    background: green;
  }
}

@media (min-width: 1280px) {
  .debug-breakpoint::after {
    content: 'xl';
    background: blue;
  }
}
```

このレイアウトシステムにより、PresidioPDF Web UIは様々なデバイスで一貫した優れたユーザー体験を提供し、効率的な開発・保守を支援します。