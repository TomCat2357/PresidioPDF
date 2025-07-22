# アニメーション系統設計

## 概要
PresidioPDF Web UIのアニメーションシステムを定義する。ユーザビリティ向上、フィードバック提供、視覚的魅力の向上を図り、ブランドアイデンティティの強化に貢献する統一的なモーションデザインを提供する。

## アニメーション原則

### デザイン哲学
```yaml
animation_principles:
  purposeful: "すべてのアニメーションは明確な目的を持つ"
  subtle: "控えめで品格のあるモーション"
  responsive: "ユーザーの行動に対する即座の反応"
  accessible: "モーション感度に配慮した設計"
  performant: "60FPSを保つ軽量な実装"
```

### 使用指針
1. **機能的アニメーション**: UI状態変化の説明
2. **フィードバック**: ユーザー操作への応答
3. **注意誘導**: 重要な情報への導線
4. **ブランディング**: 信頼性と専門性の表現

## タイミング・イージング設計

### 基本タイミング
```css
:root {
  /* 基本継続時間 */
  --duration-instant: 0ms;
  --duration-fast: 150ms;      /* UI反応（ホバー、フォーカス） */
  --duration-normal: 300ms;    /* 標準遷移 */
  --duration-slow: 500ms;      /* 複雑な変化 */
  --duration-extra-slow: 800ms; /* 特別な演出 */
  
  /* イージング関数 */
  --ease-linear: linear;
  --ease-in: cubic-bezier(0.4, 0, 1, 1);           /* 加速 */
  --ease-out: cubic-bezier(0, 0, 0.2, 1);          /* 減速 */
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);     /* 標準 */
  --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55); /* バウンス */
  --ease-elastic: cubic-bezier(0.175, 0.885, 0.32, 1.275); /* エラスティック */
}
```

### イージング使用パターン
```css
/* 一般的なUI要素 */
.ui-transition {
  transition: all var(--duration-fast) var(--ease-out);
}

/* 重要な状態変化 */
.state-transition {
  transition: all var(--duration-normal) var(--ease-in-out);
}

/* 注意を引くアニメーション */
.attention-seeking {
  animation-duration: var(--duration-slow);
  animation-timing-function: var(--ease-bounce);
}
```

## モーション分類システム

### 1. マイクロインタラクション

#### ボタンアニメーション
```css
.btn {
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
  overflow: hidden;
}

.btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.btn:active {
  transform: translateY(0);
  transition-duration: calc(var(--duration-fast) / 2);
}

/* リップル効果 */
.btn::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  transition: width var(--duration-normal) var(--ease-out),
              height var(--duration-normal) var(--ease-out);
}

.btn:active::after {
  width: 200px;
  height: 200px;
}
```

#### 入力フィールドフォーカス
```css
.input {
  position: relative;
  border: 2px solid var(--gray-300);
  transition: border-color var(--duration-fast) var(--ease-out);
}

.input::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 0;
  height: 2px;
  background: var(--primary-500);
  transform: translateX(-50%);
  transition: width var(--duration-normal) var(--ease-out);
}

.input:focus::after {
  width: 100%;
}

/* ラベルフローティング */
.form-field {
  position: relative;
}

.floating-label {
  position: absolute;
  top: 50%;
  left: 12px;
  transform: translateY(-50%);
  color: var(--gray-500);
  pointer-events: none;
  transition: all var(--duration-normal) var(--ease-out);
}

.input:focus + .floating-label,
.input:not(:placeholder-shown) + .floating-label {
  top: 0;
  left: 8px;
  transform: translateY(-50%) scale(0.85);
  color: var(--primary-500);
  background: white;
  padding: 0 4px;
}
```

### 2. ページ遷移アニメーション

#### フェード遷移
```css
.page-transition {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}

.page-transition--enter {
  opacity: 1;
  transform: translateY(0);
}

.page-transition--leave {
  opacity: 0;
  transform: translateY(-20px);
}
```

#### スライド遷移
```css
.slide-container {
  position: relative;
  overflow: hidden;
}

.slide-item {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  transition: transform var(--duration-slow) var(--ease-in-out);
}

.slide-item--current {
  transform: translateX(0);
}

.slide-item--next {
  transform: translateX(100%);
}

.slide-item--prev {
  transform: translateX(-100%);
}
```

### 3. ローディング・処理中アニメーション

#### スピナー
```css
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--gray-200);
  border-top-color: var(--primary-500);
  border-radius: 50%;
  animation: spin var(--duration-extra-slow) linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* パルススピナー */
.spinner-pulse {
  width: 20px;
  height: 20px;
  background: var(--primary-500);
  border-radius: 50%;
  animation: pulse var(--duration-slow) ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.7;
  }
}
```

#### プログレスインジケーター
```css
.progress-bar {
  position: relative;
  background: var(--gray-200);
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-500), var(--primary-400));
  border-radius: inherit;
  transition: width var(--duration-normal) var(--ease-out);
  position: relative;
}

/* アニメーション付きプログレス */
.progress-fill--animated::after {
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
  animation: progress-shine 2s ease-in-out infinite;
}

@keyframes progress-shine {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
```

#### スケルトンローディング
```css
.skeleton {
  background: var(--gray-200);
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}

.skeleton::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.4) 50%,
    transparent 100%
  );
  animation: skeleton-loading 1.5s ease-in-out infinite;
}

@keyframes skeleton-loading {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* スケルトンバリエーション */
.skeleton-text {
  height: 16px;
  margin-bottom: 8px;
}

.skeleton-text:last-child {
  width: 60%;
}

.skeleton-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

.skeleton-rect {
  width: 100%;
  height: 120px;
}
```

### 4. ステータス・フィードバックアニメーション

#### 成功・エラーアニメーション
```css
.status-animation {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  position: relative;
}

.status-success {
  background: var(--success-500);
  animation: status-bounce var(--duration-slow) var(--ease-bounce);
}

.status-success::after {
  content: '✓';
  color: white;
  font-weight: bold;
  font-size: 12px;
  animation: checkmark-draw var(--duration-normal) var(--ease-out) 0.2s;
}

@keyframes status-bounce {
  0% {
    transform: scale(0);
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
  }
}

@keyframes checkmark-draw {
  0% {
    opacity: 0;
    transform: scale(0);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

.status-error {
  background: var(--error-500);
  animation: status-shake var(--duration-slow) var(--ease-out);
}

@keyframes status-shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-2px); }
  20%, 40%, 60%, 80% { transform: translateX(2px); }
}
```

#### 通知アニメーション
```css
.notification {
  transform: translateX(100%);
  opacity: 0;
  transition: all var(--duration-normal) var(--ease-out);
}

.notification--enter {
  transform: translateX(0);
  opacity: 1;
}

.notification--leave {
  transform: translateX(100%);
  opacity: 0;
  transition: all var(--duration-fast) var(--ease-in);
}

/* スライドイン通知 */
.notification-slide {
  animation: notification-slide-in var(--duration-normal) var(--ease-out);
}

@keyframes notification-slide-in {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
```

### 5. 注意誘導アニメーション

#### パルス効果
```css
.pulse {
  animation: pulse var(--duration-slow) ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.05);
  }
}

/* 重要度によるパルス調整 */
.pulse--subtle {
  animation-duration: calc(var(--duration-slow) * 2);
}

.pulse--urgent {
  animation-duration: calc(var(--duration-slow) * 0.5);
}
```

#### 点滅効果
```css
.blink {
  animation: blink var(--duration-slow) ease-in-out infinite;
}

@keyframes blink {
  0%, 50%, 100% { opacity: 1; }
  25%, 75% { opacity: 0.3; }
}
```

#### 揺れ効果（エラー・注意）
```css
.wobble {
  animation: wobble var(--duration-slow) var(--ease-out);
}

@keyframes wobble {
  0% { transform: translateX(0%); }
  15% { transform: translateX(-25%) rotate(-5deg); }
  30% { transform: translateX(20%) rotate(3deg); }
  45% { transform: translateX(-15%) rotate(-3deg); }
  60% { transform: translateX(10%) rotate(2deg); }
  75% { transform: translateX(-5%) rotate(-1deg); }
  100% { transform: translateX(0%); }
}
```

## アクセシビリティ対応

### モーション感度対応
```css
/* reduced-motionユーザーへの配慮 */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  
  /* 重要な状態変化は保持 */
  .critical-animation {
    animation: none !important;
    transition: opacity var(--duration-fast) !important;
  }
}

/* 高コントラストモード対応 */
@media (prefers-contrast: high) {
  .skeleton::after {
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(0, 0, 0, 0.3) 50%,
      transparent 100%
    );
  }
}
```

### フォーカス管理
```css
.focus-animation {
  outline: none;
  box-shadow: 0 0 0 0 var(--primary-500);
  transition: box-shadow var(--duration-fast) var(--ease-out);
}

.focus-animation:focus-visible {
  box-shadow: 0 0 0 3px var(--primary-500);
}
```

## パフォーマンス最適化

### GPU加速対象プロパティ
```css
/* 推奨: GPUで加速される変換 */
.gpu-optimized {
  transform: translateZ(0); /* レイヤー作成 */
  will-change: transform, opacity; /* ブラウザヒント */
}

/* 避けるべき: レイアウト再計算を引き起こす */
.avoid-layout-thrash {
  /* ❌ width, height, margin, padding の変更 */
  /* ❌ left, top, right, bottom の変更 */
  
  /* ✅ transform, opacity の使用を推奨 */
  transform: scale(1.1);
  opacity: 0.8;
}
```

### アニメーション最適化パターン
```css
.optimized-animation {
  /* レイヤー分離 */
  transform: translateZ(0);
  
  /* ブラウザ最適化ヒント */
  will-change: transform, opacity;
  
  /* 不要時の will-change クリア */
  &:not(:hover):not(:focus):not(.is-animating) {
    will-change: auto;
  }
}
```

## JavaScript連携

### アニメーション制御クラス
```javascript
class AnimationController {
  constructor() {
    this.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
  
  animate(element, animation, options = {}) {
    if (this.prefersReducedMotion && !options.forceAnimation) {
      // 即座に最終状態に
      element.classList.add(animation.replace('animate-', 'final-'));
      return Promise.resolve();
    }
    
    return new Promise(resolve => {
      element.addEventListener('animationend', resolve, { once: true });
      element.classList.add(animation);
    });
  }
  
  transition(element, fromClass, toClass, duration = 300) {
    return new Promise(resolve => {
      if (this.prefersReducedMotion) {
        element.classList.remove(fromClass);
        element.classList.add(toClass);
        resolve();
        return;
      }
      
      element.style.transition = `all ${duration}ms ease`;
      element.classList.remove(fromClass);
      element.classList.add(toClass);
      
      setTimeout(resolve, duration);
    });
  }
}
```

### 使用例
```javascript
const animator = new AnimationController();

// ボタンクリック時のフィードバック
document.querySelectorAll('.btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    await animator.animate(btn, 'animate-press');
    // 処理実行
  });
});

// ページ遷移アニメーション
async function navigateTo(nextPage) {
  const currentPage = document.querySelector('.page.active');
  const nextPageElement = document.querySelector(`.page[data-page="${nextPage}"]`);
  
  await animator.transition(currentPage, 'active', 'leaving');
  currentPage.style.display = 'none';
  
  nextPageElement.style.display = 'block';
  await animator.transition(nextPageElement, 'entering', 'active');
}
```

## アニメーション実装ガイドライン

### 開発時チェックリスト
- [ ] 60FPSを維持しているか？
- [ ] `prefers-reduced-motion` に対応しているか？
- [ ] GPU加速対象プロパティを使用しているか？
- [ ] アニメーション完了時のクリーンアップは適切か？
- [ ] タブレット・モバイルでの動作は滑らかか？

### デバッグ・測定ツール
```css
/* アニメーション境界の可視化 */
.debug-animation {
  outline: 2px dashed red;
  background: rgba(255, 0, 0, 0.1);
}

/* パフォーマンス測定 */
.perf-monitor::before {
  content: counter(animation-frame);
  counter-increment: animation-frame;
  position: fixed;
  top: 10px;
  right: 10px;
  background: black;
  color: white;
  padding: 4px 8px;
  font-family: monospace;
  z-index: 9999;
}
```

このアニメーションシステムにより、PresidioPDF Web UIは魅力的で機能的なユーザー体験を提供し、ブランドの価値を効果的に表現します。