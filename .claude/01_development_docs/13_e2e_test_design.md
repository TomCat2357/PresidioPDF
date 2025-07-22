# E2E テスト設計

## 概要
PresidioPDF Web UIのエンドツーエンド（E2E）テスト設計を定義する。ユーザージャーニー全体を自動テストし、実際のブラウザ環境でのユーザビリティと機能性を検証する。

## E2Eテスト戦略

### テストレベル定義
```python
from enum import Enum

class E2ETestLevel(Enum):
    SMOKE = "smoke"           # スモークテスト（基本機能）
    CRITICAL = "critical"     # クリティカルパス
    REGRESSION = "regression" # リグレッションテスト
    LOAD = "load"            # 負荷テスト

class UserJourney(Enum):
    FIRST_TIME_USER = "first_time_user"
    RETURNING_USER = "returning_user"
    POWER_USER = "power_user"
    ERROR_RECOVERY = "error_recovery"
```

## Playwright設定

### 基本設定
```typescript
// e2e.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30 * 1000,
  expect: {
    timeout: 5000
  },
  
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  
  reporter: [
    ['html', { outputFolder: 'e2e-report' }],
    ['json', { outputFile: 'e2e-results.json' }],
    ['junit', { outputFile: 'e2e-junit.xml' }]
  ],
  
  use: {
    baseURL: process.env.STAGING_URL || 'http://localhost:5000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox', 
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 12'] },
    }
  ]
});
```

## ページオブジェクトモデル

### ベースページクラス
```typescript
// tests/e2e/pages/base-page.ts
import { Page, Locator } from '@playwright/test';

export abstract class BasePage {
  readonly page: Page;
  readonly url: string;
  
  constructor(page: Page, url: string) {
    this.page = page;
    this.url = url;
  }
  
  async navigate(): Promise<void> {
    await this.page.goto(this.url);
  }
  
  async waitForPageLoad(): Promise<void> {
    await this.page.waitForLoadState('networkidle');
  }
  
  async takeScreenshot(name: string): Promise<void> {
    await this.page.screenshot({ 
      path: `screenshots/${name}-${Date.now()}.png`,
      fullPage: true 
    });
  }
  
  async waitForElement(locator: Locator, timeout: number = 5000): Promise<void> {
    await locator.waitFor({ state: 'visible', timeout });
  }
  
  async scrollToElement(locator: Locator): Promise<void> {
    await locator.scrollIntoViewIfNeeded();
  }
}
```

### ホームページオブジェクト
```typescript
// tests/e2e/pages/home-page.ts
import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from './base-page';

export class HomePage extends BasePage {
  readonly fileUploadArea: Locator;
  readonly fileInput: Locator;
  readonly uploadButton: Locator;
  readonly processingButton: Locator;
  readonly quickSettings: Locator;
  readonly spaCyModelSelect: Locator;
  readonly maskingMethodSelect: Locator;
  readonly detailConfigButton: Locator;
  readonly historyButton: Locator;
  
  constructor(page: Page) {
    super(page, '/');
    
    this.fileUploadArea = page.locator('#upload-area');
    this.fileInput = page.locator('#file-input');
    this.uploadButton = page.locator('button:has-text("ファイルを選択")');
    this.processingButton = page.locator('button:has-text("処理開始")');
    this.quickSettings = page.locator('.quick-settings');
    this.spaCyModelSelect = page.locator('select[name="spacy_model"]');
    this.maskingMethodSelect = page.locator('select[name="masking_method"]');
    this.detailConfigButton = page.locator('button:has-text("詳細設定")');
    this.historyButton = page.locator('button:has-text("履歴を見る")');
  }
  
  async uploadFile(filePath: string): Promise<void> {
    await this.fileInput.setInputFiles(filePath);
    await this.page.waitForSelector('.file-info', { state: 'visible' });
  }
  
  async uploadFileByDragAndDrop(filePath: string): Promise<void> {
    const buffer = await require('fs').promises.readFile(filePath);
    
    const dataTransfer = await this.page.evaluateHandle(() => new DataTransfer());
    const file = new File([buffer], filePath.split('/').pop() || 'test.pdf', { 
      type: 'application/pdf' 
    });
    
    await this.page.evaluate(
      ({ dataTransfer, file }) => dataTransfer.items.add(file),
      { dataTransfer, file }
    );
    
    await this.fileUploadArea.dispatchEvent('drop', { dataTransfer });
  }
  
  async selectSpaCyModel(model: string): Promise<void> {
    await this.spaCyModelSelect.selectOption(model);
  }
  
  async selectMaskingMethod(method: string): Promise<void> {
    await this.maskingMethodSelect.selectOption(method);
  }
  
  async startProcessing(): Promise<void> {
    await this.processingButton.click();
    await this.page.waitForURL(/.*\/processing\/.*/, { timeout: 10000 });
  }
  
  async isProcessingButtonEnabled(): Promise<boolean> {
    return await this.processingButton.isEnabled();
  }
  
  async validateFileUploadUI(): Promise<void> {
    await expect(this.fileUploadArea).toBeVisible();
    await expect(this.uploadButton).toBeVisible();
    await expect(this.processingButton).toBeDisabled();
  }
}
```

### 処理画面ページオブジェクト
```typescript
// tests/e2e/pages/processing-page.ts
import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from './base-page';

export class ProcessingPage extends BasePage {
  readonly progressBar: Locator;
  readonly progressText: Locator;
  readonly currentStep: Locator;
  readonly detectedCount: Locator;
  readonly processingTime: Locator;
  readonly cancelButton: Locator;
  readonly errorMessage: Locator;
  
  constructor(page: Page) {
    super(page, '/processing');
    
    this.progressBar = page.locator('.progress-bar .progress-fill');
    this.progressText = page.locator('.progress-text');
    this.currentStep = page.locator('.current-step');
    this.detectedCount = page.locator('.detected-count');
    this.processingTime = page.locator('.processing-time');
    this.cancelButton = page.locator('button:has-text("キャンセル")');
    this.errorMessage = page.locator('.error-message');
  }
  
  async waitForProcessingComplete(timeout: number = 120000): Promise<void> {
    await this.page.waitForURL(/.*\/result\/.*/, { timeout });
  }
  
  async getProgressPercentage(): Promise<number> {
    const progressText = await this.progressText.textContent();
    if (!progressText) return 0;
    
    const match = progressText.match(/(\d+)%/);
    return match ? parseInt(match[1]) : 0;
  }
  
  async getCurrentStep(): Promise<string> {
    return (await this.currentStep.textContent()) || '';
  }
  
  async getDetectedCount(): Promise<number> {
    const countText = await this.detectedCount.textContent();
    if (!countText) return 0;
    
    const match = countText.match(/(\d+)件/);
    return match ? parseInt(match[1]) : 0;
  }
  
  async cancelProcessing(): Promise<void> {
    await this.cancelButton.click();
    
    // キャンセル確認ダイアログの処理
    this.page.on('dialog', async dialog => {
      await dialog.accept();
    });
    
    await this.page.waitForURL('/', { timeout: 10000 });
  }
  
  async validateProcessingUI(): Promise<void> {
    await expect(this.progressBar).toBeVisible();
    await expect(this.progressText).toBeVisible();
    await expect(this.currentStep).toBeVisible();
    await expect(this.cancelButton).toBeVisible();
  }
  
  async isProcessingError(): Promise<boolean> {
    try {
      await this.errorMessage.waitFor({ state: 'visible', timeout: 1000 });
      return true;
    } catch {
      return false;
    }
  }
}
```

### 結果画面ページオブジェクト
```typescript
// tests/e2e/pages/result-page.ts
import { Page, Locator, expect, Download } from '@playwright/test';
import { BasePage } from './base-page';

export class ResultPage extends BasePage {
  readonly summarySection: Locator;
  readonly totalDetectedCount: Locator;
  readonly entityBreakdown: Locator;
  readonly processingTime: Locator;
  readonly downloadPdfButton: Locator;
  readonly downloadReportButton: Locator;
  readonly downloadOriginalButton: Locator;
  readonly newProcessingButton: Locator;
  readonly detailsList: Locator;
  readonly entityItems: Locator;
  
  constructor(page: Page) {
    super(page, '/result');
    
    this.summarySection = page.locator('.result-summary');
    this.totalDetectedCount = page.locator('.total-detected');
    this.entityBreakdown = page.locator('.entity-breakdown');
    this.processingTime = page.locator('.processing-time');
    this.downloadPdfButton = page.locator('button:has-text("処理済みPDFダウンロード")');
    this.downloadReportButton = page.locator('button:has-text("レポートDL")');
    this.downloadOriginalButton = page.locator('button:has-text("元ファイルDL")');
    this.newProcessingButton = page.locator('button:has-text("新しい処理を開始")');
    this.detailsList = page.locator('.detection-details');
    this.entityItems = page.locator('.entity-item');
  }
  
  async getTotalDetectedCount(): Promise<number> {
    const countText = await this.totalDetectedCount.textContent();
    if (!countText) return 0;
    
    const match = countText.match(/(\d+)件/);
    return match ? parseInt(match[1]) : 0;
  }
  
  async getEntityBreakdown(): Promise<Record<string, number>> {
    const breakdown: Record<string, number> = {};
    const items = await this.entityBreakdown.locator('.entity-count').all();
    
    for (const item of items) {
      const text = await item.textContent();
      if (text) {
        const match = text.match(/(.+?): (\d+)件/);
        if (match) {
          breakdown[match[1]] = parseInt(match[2]);
        }
      }
    }
    
    return breakdown;
  }
  
  async downloadProcessedPdf(): Promise<Download> {
    const downloadPromise = this.page.waitForEvent('download');
    await this.downloadPdfButton.click();
    return await downloadPromise;
  }
  
  async downloadReport(): Promise<Download> {
    const downloadPromise = this.page.waitForEvent('download');
    await this.downloadReportButton.click();
    return await downloadPromise;
  }
  
  async downloadOriginal(): Promise<Download> {
    const downloadPromise = this.page.waitForEvent('download');
    await this.downloadOriginalButton.click();
    return await downloadPromise;
  }
  
  async startNewProcessing(): Promise<void> {
    await this.newProcessingButton.click();
    await this.page.waitForURL('/', { timeout: 5000 });
  }
  
  async getEntityDetails(): Promise<Array<{type: string, text: string, confidence: number, page: number}>> {
    const details = [];
    const items = await this.entityItems.all();
    
    for (const item of items) {
      const type = await item.locator('.entity-type').textContent() || '';
      const text = await item.locator('.entity-text').textContent() || '';
      const confidenceText = await item.locator('.confidence').textContent() || '';
      const pageText = await item.locator('.page-number').textContent() || '';
      
      const confidence = parseFloat(confidenceText.match(/(\d+(?:\.\d+)?)%/)?.[1] || '0');
      const page = parseInt(pageText.match(/(\d+)/)?.[1] || '0');
      
      details.push({ type, text, confidence, page });
    }
    
    return details;
  }
  
  async validateResultUI(): Promise<void> {
    await expect(this.summarySection).toBeVisible();
    await expect(this.totalDetectedCount).toBeVisible();
    await expect(this.downloadPdfButton).toBeVisible();
    await expect(this.newProcessingButton).toBeVisible();
  }
}
```

## E2Eテストスイート

### 基本機能テスト
```typescript
// tests/e2e/basic-functionality.test.ts
import { test, expect } from '@playwright/test';
import { HomePage } from './pages/home-page';
import { ProcessingPage } from './pages/processing-page';
import { ResultPage } from './pages/result-page';
import path from 'path';

test.describe('PresidioPDF Basic Functionality', () => {
  const testPdfPath = path.join(__dirname, 'fixtures', 'sample-with-pii.pdf');
  
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('完全なPDF処理ワークフロー', async ({ page }) => {
    const homePage = new HomePage(page);
    const processingPage = new ProcessingPage(page);
    const resultPage = new ResultPage(page);
    
    // ホーム画面の検証
    await homePage.validateFileUploadUI();
    
    // ファイルアップロード
    await homePage.uploadFile(testPdfPath);
    await expect(homePage.processingButton).toBeEnabled();
    
    // クイック設定
    await homePage.selectSpaCyModel('ja_core_news_sm');
    await homePage.selectMaskingMethod('annotation');
    
    // 処理開始
    await homePage.startProcessing();
    
    // 処理画面の検証
    await processingPage.validateProcessingUI();
    
    // 進捗監視
    let previousProgress = 0;
    while (true) {
      const currentProgress = await processingPage.getProgressPercentage();
      expect(currentProgress).toBeGreaterThanOrEqual(previousProgress);
      previousProgress = currentProgress;
      
      if (currentProgress === 100) break;
      
      await page.waitForTimeout(1000);
    }
    
    // 処理完了まで待機
    await processingPage.waitForProcessingComplete();
    
    // 結果画面の検証
    await resultPage.validateResultUI();
    
    const detectedCount = await resultPage.getTotalDetectedCount();
    expect(detectedCount).toBeGreaterThan(0);
    
    // エンティティ詳細確認
    const entityDetails = await resultPage.getEntityDetails();
    expect(entityDetails).toHaveLength(detectedCount);
    
    // ダウンロード機能確認
    const processedPdf = await resultPage.downloadProcessedPdf();
    expect(processedPdf.suggestedFilename()).toMatch(/.*\.pdf$/);
    
    const report = await resultPage.downloadReport();
    expect(report.suggestedFilename()).toMatch(/.*\.json$/);
  });
  
  test('ドラッグ&ドロップでのファイルアップロード', async ({ page }) => {
    const homePage = new HomePage(page);
    
    await homePage.validateFileUploadUI();
    await homePage.uploadFileByDragAndDrop(testPdfPath);
    await expect(homePage.processingButton).toBeEnabled();
  });
  
  test('無効ファイルのエラーハンドリング', async ({ page }) => {
    const homePage = new HomePage(page);
    const invalidFilePath = path.join(__dirname, 'fixtures', 'invalid.txt');
    
    await homePage.fileInput.setInputFiles(invalidFilePath);
    
    // エラーメッセージ確認
    await expect(page.locator('.error-message')).toBeVisible();
    await expect(page.locator('.error-message')).toContainText('PDFファイルのみ');
  });
  
  test('処理中のキャンセル機能', async ({ page }) => {
    const homePage = new HomePage(page);
    const processingPage = new ProcessingPage(page);
    
    await homePage.uploadFile(testPdfPath);
    await homePage.startProcessing();
    
    await processingPage.validateProcessingUI();
    
    // 処理開始後少し待ってからキャンセル
    await page.waitForTimeout(2000);
    await processingPage.cancelProcessing();
    
    // ホーム画面に戻ることを確認
    await expect(page).toHaveURL('/');
  });
});
```

### レスポンシブテスト
```typescript
// tests/e2e/responsive.test.ts
import { test, expect, devices } from '@playwright/test';
import { HomePage } from './pages/home-page';

const mobileViewports = [
  devices['iPhone 12'],
  devices['Pixel 5'],
  devices['Samsung Galaxy S21'],
];

const tabletViewports = [
  devices['iPad'],
  devices['iPad Pro'],
];

test.describe('Responsive Design Tests', () => {
  
  mobileViewports.forEach(device => {
    test(`モバイル対応: ${device.name}`, async ({ browser }) => {
      const context = await browser.newContext({
        ...device
      });
      const page = await context.newPage();
      const homePage = new HomePage(page);
      
      await homePage.navigate();
      
      // モバイルレイアウトの確認
      await expect(homePage.fileUploadArea).toBeVisible();
      await expect(homePage.quickSettings).toBeVisible();
      
      // タッチ操作確認
      await homePage.uploadButton.tap();
      
      await context.close();
    });
  });
  
  tabletViewports.forEach(device => {
    test(`タブレット対応: ${device.name}`, async ({ browser }) => {
      const context = await browser.newContext({
        ...device
      });
      const page = await context.newPage();
      const homePage = new HomePage(page);
      
      await homePage.navigate();
      
      // タブレットレイアウトの確認
      await expect(homePage.fileUploadArea).toBeVisible();
      await expect(homePage.quickSettings).toBeVisible();
      
      await context.close();
    });
  });
});
```

### 負荷テスト
```typescript
// tests/e2e/load.test.ts
import { test, expect } from '@playwright/test';
import { HomePage } from './pages/home-page';
import { ProcessingPage } from './pages/processing-page';
import path from 'path';

test.describe('Load Tests', () => {
  const testPdfPath = path.join(__dirname, 'fixtures', 'large-sample.pdf');
  
  test('大量ファイル処理性能テスト', async ({ page }) => {
    const homePage = new HomePage(page);
    const processingPage = new ProcessingPage(page);
    
    // 大きなPDFファイルでの処理時間測定
    const startTime = Date.now();
    
    await homePage.navigate();
    await homePage.uploadFile(testPdfPath);
    await homePage.startProcessing();
    
    // 処理完了まで待機（タイムアウト延長）
    await processingPage.waitForProcessingComplete(300000); // 5分
    
    const processingTime = Date.now() - startTime;
    console.log(`処理時間: ${processingTime / 1000}秒`);
    
    // 処理時間要件確認（例：300秒以内）
    expect(processingTime).toBeLessThan(300000);
  });
  
  test('並行アクセス負荷テスト', async ({ browser }) => {
    const concurrentUsers = 5;
    const promises = [];
    
    for (let i = 0; i < concurrentUsers; i++) {
      const promise = (async () => {
        const context = await browser.newContext();
        const page = await context.newPage();
        const homePage = new HomePage(page);
        
        try {
          await homePage.navigate();
          await homePage.uploadFile(testPdfPath);
          await homePage.startProcessing();
          
          // 処理完了確認
          await page.waitForURL(/.*\/result\/.*/, { timeout: 120000 });
          return { success: true, user: i };
        } catch (error) {
          return { success: false, user: i, error };
        } finally {
          await context.close();
        }
      })();
      
      promises.push(promise);
    }
    
    const results = await Promise.all(promises);
    const successCount = results.filter(r => r.success).length;
    
    console.log(`成功: ${successCount}/${concurrentUsers}`);
    expect(successCount).toBe(concurrentUsers);
  });
});
```

## テスト実行・レポート

### テスト実行スクリプト
```json
{
  "scripts": {
    "e2e": "playwright test",
    "e2e:headed": "playwright test --headed",
    "e2e:debug": "playwright test --debug",
    "e2e:smoke": "playwright test --grep '@smoke'",
    "e2e:critical": "playwright test --grep '@critical'", 
    "e2e:mobile": "playwright test --project=mobile-chrome",
    "e2e:report": "playwright show-report e2e-report"
  }
}
```

### CI/CD統合用テストランナー
```bash
#!/bin/bash
# scripts/run-e2e-tests.sh

set -e

ENVIRONMENT=${1:-staging}
BROWSER=${2:-chromium}

echo "Running E2E tests on $ENVIRONMENT environment with $BROWSER browser"

# 環境URL設定
case $ENVIRONMENT in
  staging)
    export STAGING_URL="https://staging.presidiopdf.com"
    ;;
  production)
    export STAGING_URL="https://presidiopdf.com"
    ;;
  local)
    export STAGING_URL="http://localhost:5000"
    ;;
esac

# テストサーバーのヘルスチェック
echo "Checking server health..."
curl -f $STAGING_URL/health || { echo "Server is not healthy"; exit 1; }

# Playwrightインストール
npx playwright install $BROWSER

# テスト実行
npx playwright test \
  --project=$BROWSER \
  --reporter=html,json,junit \
  --output-dir=test-results \
  --trace=on-first-retry

echo "E2E tests completed successfully"
```