# SEO要件

## 概要
PresidioPDF Web UIにおけるSEO最適化要件を定義する。個人情報保護ツールとしての専門性と信頼性を検索エンジンに適切に伝え、関連キーワードでの検索流入を最大化する。

## ターゲットキーワード戦略

### プライマリキーワード
- **メインキーワード**: `PDF 個人情報 マスキング`
- **サブキーワード**: `PDF 個人情報 検出`、`PDF プライバシー保護`
- **技術キーワード**: `Presidio 日本語`、`PDF セキュリティ ツール`

### ロングテールキーワード
- `PDF ファイル 個人情報 削除 無料`
- `日本語 個人情報 自動検出 ツール`
- `GDPR対応 PDF マスキング ソフト`
- `住所 電話番号 PDF から除去`

### 競合分析キーワード
- `PDF-XChange`、`Adobe Acrobat Pro DC`との差別化
- `オープンソース PDF エディタ`としてのポジショニング

## メタタグ設計

### ホームページ (`/`)
```html
<title>PresidioPDF - AI搭載PDF個人情報検出・マスキングツール | 無料・オープンソース</title>
<meta name="description" content="Microsoftアルコール基盤のAI技術で日本語PDF文書から個人情報を自動検出・マスキング。住所・電話番号・氏名を安全に処理。GDPR対応、完全無料のプライバシー保護ツール。">
<meta name="keywords" content="PDF,個人情報,マスキング,プライバシー保護,GDPR,Microsoft Presidio,日本語,無料,オープンソース">

<!-- Open Graph -->
<meta property="og:title" content="PresidioPDF - AI搭載PDF個人情報マスキングツール">
<meta property="og:description" content="日本語PDF文書から個人情報を自動検出・安全にマスキング。企業のプライバシー保護を支援する無料ツール。">
<meta property="og:type" content="website">
<meta property="og:url" content="https://presidiopdf.example.com">
<meta property="og:image" content="https://presidiopdf.example.com/og-image.jpg">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="PresidioPDF - AI搭載PDF個人情報マスキングツール">
<meta name="twitter:description" content="日本語PDF文書から個人情報を自動検出・安全にマスキング">
<meta name="twitter:image" content="https://presidiopdf.example.com/twitter-image.jpg">
```

### 機能ページ別メタタグ
```python
# メタタグテンプレート
META_TAGS = {
    "/": {
        "title": "PresidioPDF - AI搭載PDF個人情報検出・マスキングツール",
        "description": "Microsoft Presidio基盤のAI技術で日本語PDF文書から個人情報を自動検出・マスキング...",
        "keywords": "PDF,個人情報,マスキング,プライバシー保護,GDPR"
    },
    "/config": {
        "title": "設定 - PresidioPDF個人情報検出設定",
        "description": "PDF個人情報検出の詳細設定。spaCyモデル選択、マスキング方法、検出対象の細かなカスタマイズが可能。",
        "keywords": "PDF設定,個人情報検出設定,spaCy,マスキング方法"
    },
    "/help": {
        "title": "使い方・FAQ - PresidioPDF個人情報マスキングツール",
        "description": "PresidioPDFの詳しい使い方、よくある質問、トラブルシューティング。初心者でも安心して利用可能。",
        "keywords": "PDF使い方,FAQ,個人情報マスキング,ヘルプ,チュートリアル"
    }
}
```

## 構造化データ（Schema.org）

### WebApplicationスキーマ
```json
{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "PresidioPDF",
  "description": "AI技術を活用したPDF個人情報検出・マスキングツール",
  "url": "https://presidiopdf.example.com",
  "applicationCategory": "SecurityApplication",
  "operatingSystem": "Web Browser",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "JPY"
  },
  "creator": {
    "@type": "Organization",
    "name": "PresidioPDF Project"
  },
  "featureList": [
    "AI個人情報自動検出",
    "安全なPDFマスキング",
    "日本語特化処理",
    "GDPR対応",
    "オープンソース"
  ]
}
```

### FAQスキーマ
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "PresidioPDFで検出できる個人情報の種類は？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "個人名、住所、電話番号、メールアドレス、クレジットカード番号、マイナンバーなど、日本語個人情報を幅広く検出できます。"
      }
    }
  ]
}
```

## サイトマップ設計

### XML Sitemap
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://presidiopdf.example.com/</loc>
    <lastmod>2024-01-15</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://presidiopdf.example.com/config</loc>
    <lastmod>2024-01-15</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://presidiopdf.example.com/help</loc>
    <lastmod>2024-01-15</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>
```

### robots.txt
```
User-agent: *
Allow: /
Disallow: /processing/
Disallow: /result/
Disallow: /api/
Disallow: /uploads/

Sitemap: https://presidiopdf.example.com/sitemap.xml
```

## コンテンツSEO戦略

### コンテンツ階層
```
1. 概要・価値提案 (ホームページ)
   ├─ AI技術による高精度検出
   ├─ 日本語特化の個人情報処理
   └─ 企業プライバシー保護支援

2. 機能詳細・使い方
   ├─ ステップバイステップガイド
   ├─ 設定項目の詳細説明
   └─ ベストプラクティス

3. 技術情報・信頼性
   ├─ Microsoft Presidio技術説明
   ├─ セキュリティ・プライバシー対策
   └─ オープンソース透明性
```

### キーワード密度最適化
- **メインキーワード密度**: 1-2%
- **関連キーワード**: 自然な文章内での適切な配置
- **シノニム活用**: 「マスキング」「匿名化」「削除」「保護」

## 技術的SEO要件

### パフォーマンス最適化
```python
# Flask-Compress設定
from flask_compress import Compress

app = Flask(__name__)
Compress(app)

# キャッシュ設定
@app.after_request
def add_cache_headers(response):
    if request.endpoint in ['static', 'favicon']:
        response.cache_control.max_age = 31536000  # 1年
    return response
```

### Core Web Vitals目標値
- **LCP (Largest Contentful Paint)**: < 2.5秒
- **FID (First Input Delay)**: < 100ms
- **CLS (Cumulative Layout Shift)**: < 0.1

### モバイルフレンドリー
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
```

## リンク構築戦略

### 内部リンク最適化
```html
<!-- 関連機能への内部リンク -->
<nav aria-label="主要機能">
  <a href="/config" title="個人情報検出の詳細設定">詳細設定</a>
  <a href="/help" title="PDF個人情報マスキングの使い方">使い方ガイド</a>
  <a href="/history" title="過去の処理履歴確認">処理履歴</a>
</nav>
```

### 外部リンク・被リンク戦略
- **技術ブログ投稿**: Microsoft Presidio、spaCy技術解説
- **GitHub リポジトリ**: オープンソースコミュニティからの被リンク
- **プライバシー関連フォーラム**: 専門的な議論への参加

## 測定・分析設計

### Google Analytics 4 設定
```javascript
// GA4トラッキング
gtag('config', 'G-XXXXXXXXXX', {
  // カスタムイベント設定
  custom_map: {
    'custom_parameter_1': 'file_upload',
    'custom_parameter_2': 'processing_complete'
  }
});

// カスタムイベント例
gtag('event', 'file_upload', {
  'event_category': 'PDF Processing',
  'event_label': 'Upload Success',
  'file_size': fileSizeKB
});
```

### Search Console 最適化
- **クロールエラー監視**: 定期的なサイトヘルス確認
- **検索パフォーマンス分析**: CTR改善施策
- **索引カバレッジ**: 全ページの適切なインデックス確認

## ローカルSEO（該当する場合）

### 企業利用向け最適化
```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "PresidioPDF",
  "applicationCategory": "BusinessApplication",
  "description": "企業向けPDF個人情報保護ソリューション",
  "operatingSystem": "Web",
  "permissions": "ローカル処理、外部送信なし"
}
```

### 業界特化コンテンツ
- 法務業界向け契約書処理事例
- 人事部門向け履歴書マスキング活用
- 医療機関向けプライバシー保護対策