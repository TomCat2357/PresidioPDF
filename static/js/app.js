/**
 * PDF個人情報マスキングツール - Webアプリケーション
 * JavaScript フロントエンド（PDF.js統合版）
 */

// PDF.js設定
console.log('Checking PDF.js availability:', typeof pdfjsLib);
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    console.log('PDF.js worker configured');
} else {
    console.error('PDF.js library not found!');
}

class PresidioPDFWebApp {
    constructor() {
        this.currentPdfDocument = null; // PDF.js document
        this.currentPdf = null;
        this.currentPage = 0;
        this.totalPages = 0;
        this.zoomLevel = 100;
        this.detectionResults = [];
        this.selectedEntityIndex = -1;
        this.selectedHighlight = null;
        this.editMode = false;
        this.settings = {
            entities: ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
            threshold: 0.5,
            masking_method: "highlight"
        };
        
        // PDF.js関連
        this.pdfCanvas = null;
        this.pdfContext = null;
        this.textLayer = null;
        this.highlightOverlay = null;
        this.isTextSelecting = false;
        this.textSelection = null;
        
        this.initializeElements();
        this.bindEvents();
        this.loadSettings();
        this.setupZoomSlider();
        this.initializePdfViewer();
    }
    
    initializeElements() {
        this.elements = {
            uploadArea: document.getElementById('uploadArea'),
            pdfFileInput: document.getElementById('pdfFileInput'),
            selectedFileName: document.getElementById('selectedFileName'),
            detectBtn: document.getElementById('detectBtn'),
            settingsBtn: document.getElementById('settingsBtn'),
            prevPageBtn: document.getElementById('prevPageBtn'),
            nextPageBtn: document.getElementById('nextPageBtn'),
            pageInfo: document.getElementById('pageInfo'),
            zoomSlider: document.getElementById('zoomSlider'),
            zoomValue: document.getElementById('zoomValue'),
            showHighlights: document.getElementById('showHighlights'),
            zoomDisplay: document.getElementById('zoomDisplay'),
            entityList: document.getElementById('entityList'),
            resultCount: document.getElementById('resultCount'),
            saveBtn: document.getElementById('saveBtn'),
            statusMessage: document.getElementById('statusMessage'),
            loadingOverlay: document.getElementById('loadingOverlay'),
            pdfViewer: document.getElementById('pdfViewer'),
            pdfPlaceholder: document.getElementById('pdfPlaceholder'),
            pdfCanvasContainer: document.getElementById('pdfCanvasContainer'),
            pdfCanvas: document.getElementById('pdfCanvas'),
            textLayer: document.getElementById('textLayer'),
            highlightOverlay: document.getElementById('highlightOverlay'),
            // 設定モーダル要素
            thresholdSlider: document.getElementById('thresholdSlider'),
            thresholdValue: document.getElementById('thresholdValue'),
            saveSettingsBtn: document.getElementById('saveSettingsBtn'),
            // ハイライト編集要素
            selectedHighlightText: document.getElementById('selectedHighlightText'),
            selectedHighlightType: document.getElementById('selectedHighlightType'),
            selectedHighlightConfidence: document.getElementById('selectedHighlightConfidence'),
            selectedHighlightPage: document.getElementById('selectedHighlightPage'),
            selectedHighlightPosition: document.getElementById('selectedHighlightPosition'),
            extendLeftBtn: document.getElementById('extendLeftBtn'),
            extendRightBtn: document.getElementById('extendRightBtn'),
            shrinkLeftBtn: document.getElementById('shrinkLeftBtn'),
            shrinkRightBtn: document.getElementById('shrinkRightBtn'),
            clearSelectionBtn: document.getElementById('clearSelectionBtn'),
            deleteHighlightBtn: document.getElementById('deleteHighlightBtn')
        };
    }
    
    initializePdfViewer() {
        console.log('Initializing PDF viewer...');
        this.pdfCanvas = this.elements.pdfCanvas;
        console.log('pdfCanvas element:', this.pdfCanvas);
        
        if (this.pdfCanvas) {
            this.pdfContext = this.pdfCanvas.getContext('2d');
            console.log('pdfContext:', this.pdfContext);
        } else {
            console.error('pdfCanvas element not found!');
        }
        
        this.textLayer = this.elements.textLayer;
        this.highlightOverlay = this.elements.highlightOverlay;
        console.log('textLayer:', this.textLayer);
        console.log('highlightOverlay:', this.highlightOverlay);
    }
    
    bindEvents() {
        // ファイルアップロード関連
        this.elements.uploadArea.addEventListener('click', () => {
            this.elements.pdfFileInput.click();
        });
        
        this.elements.pdfFileInput.addEventListener('change', (e) => {
            this.handleFileSelect(e.target.files[0]);
        });
        
        // ドラッグ&ドロップ
        this.elements.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.elements.uploadArea.classList.add('dragover');
        });
        
        this.elements.uploadArea.addEventListener('dragleave', () => {
            this.elements.uploadArea.classList.remove('dragover');
        });
        
        this.elements.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.elements.uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        });
        
        // ボタンイベント
        this.elements.detectBtn.addEventListener('click', () => {
            this.detectEntities();
        });
        
        this.elements.prevPageBtn.addEventListener('click', () => {
            this.previousPage();
        });
        
        this.elements.nextPageBtn.addEventListener('click', () => {
            this.nextPage();
        });
        
        this.elements.zoomSlider.addEventListener('input', (e) => {
            this.updateZoom(parseInt(e.target.value));
        });
        
        this.elements.showHighlights.addEventListener('change', () => {
            this.renderPdfPage();
        });
        
        this.elements.saveBtn.addEventListener('click', () => {
            this.savePdf();
        });
        
        // 設定モーダル
        this.elements.thresholdSlider.addEventListener('input', (e) => {
            this.elements.thresholdValue.textContent = e.target.value;
        });
        
        this.elements.saveSettingsBtn.addEventListener('click', () => {
            this.saveSettings();
        });
        
        // ハイライト編集ボタン
        this.elements.extendLeftBtn?.addEventListener('click', () => {
            this.adjustHighlight('extend_left');
        });
        
        this.elements.extendRightBtn?.addEventListener('click', () => {
            this.adjustHighlight('extend_right');
        });
        
        this.elements.shrinkLeftBtn?.addEventListener('click', () => {
            this.adjustHighlight('shrink_left');
        });
        
        this.elements.shrinkRightBtn?.addEventListener('click', () => {
            this.adjustHighlight('shrink_right');
        });
        
        this.elements.clearSelectionBtn?.addEventListener('click', () => {
            this.clearSelection();
        });
        
        this.elements.deleteHighlightBtn?.addEventListener('click', () => {
            this.deleteHighlight();
        });
        
        // PDF.js キャンバス関連のイベント
        this.setupPdfCanvasEvents();
        
        // キーボードショートカット
        document.addEventListener('keydown', (e) => {
            this.handleKeyDown(e);
        });
    }
    
    setupPdfCanvasEvents() {
        let isMouseDown = false;
        let startX, startY;
        
        // マウスダウン
        this.pdfCanvas.addEventListener('mousedown', (e) => {
            isMouseDown = true;
            const rect = this.pdfCanvas.getBoundingClientRect();
            startX = e.clientX - rect.left;
            startY = e.clientY - rect.top;
            
            // ハイライト選択チェック
            this.checkHighlightSelection(startX, startY);
        });
        
        // マウス移動（テキスト選択）
        this.pdfCanvas.addEventListener('mousemove', (e) => {
            if (isMouseDown && !this.selectedHighlight) {
                const rect = this.pdfCanvas.getBoundingClientRect();
                const currentX = e.clientX - rect.left;
                const currentY = e.clientY - rect.top;
                
                this.handleTextSelection(startX, startY, currentX, currentY);
            }
        });
        
        // マウスアップ
        this.pdfCanvas.addEventListener('mouseup', (e) => {
            if (isMouseDown && this.textSelection) {
                this.finalizeTextSelection();
            }
            isMouseDown = false;
        });
        
        // ダブルクリック（単語選択）
        this.pdfCanvas.addEventListener('dblclick', (e) => {
            const rect = this.pdfCanvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            this.selectWordAtPosition(x, y);
        });
    }
    
    async handleFileSelect(file) {
        if (!file) return;
        
        if (file.type !== 'application/pdf') {
            this.showError('PDFファイルを選択してください');
            return;
        }
        
        try {
            this.showLoading(true);
            this.updateStatus('PDFファイルを読み込み中...');
            console.log('Loading PDF file:', file.name);
            
            // PDF.jsでPDFを読み込み
            const arrayBuffer = await file.arrayBuffer();
            console.log('File converted to ArrayBuffer, size:', arrayBuffer.byteLength);
            
            this.currentPdfDocument = await pdfjsLib.getDocument(arrayBuffer).promise;
            console.log('PDF document loaded successfully');
            
            this.totalPages = this.currentPdfDocument.numPages;
            this.currentPage = 0;
            console.log('Total pages:', this.totalPages);
            
            // UIを更新
            this.elements.selectedFileName.textContent = file.name;
            this.elements.detectBtn.disabled = false;
            this.updatePageInfo();
            
            // プレースホルダーを非表示にし、キャンバスを表示
            console.log('Hiding placeholder and showing canvas...');
            this.elements.pdfPlaceholder.style.display = 'none';
            this.elements.pdfCanvasContainer.style.display = 'block';
            
            // 最初のページを表示
            await this.renderPdfPage();
            
            // Flask側にもアップロード（検出用）
            await this.uploadToFlask(file);
            
            this.updateStatus('PDFファイルの読み込みが完了しました');
            this.showLoading(false);
            
        } catch (error) {
            this.showLoading(false);
            console.error('PDFファイル読み込みエラー:', error);
            this.showError('PDFファイルの読み込みに失敗しました');
        }
    }
    
    async uploadToFlask(file) {
        const formData = new FormData();
        formData.append('pdf_file', file);
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (data.success) {
            this.currentPdf = data.filename;
        } else {
            throw new Error(data.message);
        }
    }
    
    async renderPdfPage() {
        console.log('renderPdfPage called, currentPdfDocument:', this.currentPdfDocument);
        console.log('pdfCanvas in renderPdfPage:', this.pdfCanvas);
        console.log('pdfContext in renderPdfPage:', this.pdfContext);
        
        if (!this.currentPdfDocument) {
            console.log('No PDF document loaded');
            return;
        }
        
        if (!this.pdfCanvas) {
            console.error('Canvas element is null, re-initializing...');
            this.initializePdfViewer();
            if (!this.pdfCanvas) {
                console.error('Cannot find canvas element even after re-initialization');
                return;
            }
        }
        
        try {
            console.log('Getting page:', this.currentPage + 1);
            const page = await this.currentPdfDocument.getPage(this.currentPage + 1);
            console.log('Page loaded successfully');
            
            // スケールを計算
            const scale = this.zoomLevel / 100;
            const viewport = page.getViewport({ scale });
            console.log('Viewport:', viewport);
            
            // キャンバスサイズを設定
            this.pdfCanvas.width = viewport.width;
            this.pdfCanvas.height = viewport.height;
            this.pdfCanvas.style.width = viewport.width + 'px';
            this.pdfCanvas.style.height = viewport.height + 'px';
            console.log('Canvas size set:', viewport.width, 'x', viewport.height);
            
            // テキストレイヤーとハイライトオーバーレイのサイズも調整
            this.textLayer.style.width = viewport.width + 'px';
            this.textLayer.style.height = viewport.height + 'px';
            this.highlightOverlay.style.width = viewport.width + 'px';
            this.highlightOverlay.style.height = viewport.height + 'px';
            
            // PDFページをレンダリング
            const renderContext = {
                canvasContext: this.pdfContext,
                viewport: viewport
            };
            console.log('Starting page render...');
            
            await page.render(renderContext).promise;
            console.log('Page render completed');
            
            // テキストレイヤーを更新
            console.log('Rendering text layer...');
            await this.renderTextLayer(page, viewport);
            console.log('Text layer completed');
            
            // ハイライトを表示
            if (this.elements.showHighlights.checked) {
                console.log('Rendering highlights...');
                this.renderHighlights();
            }
            
        } catch (error) {
            console.error('PDFページレンダリングエラー:', error);
            this.showError('PDFページの表示に失敗しました');
        }
    }
    
    async renderTextLayer(page, viewport) {
        // 既存のテキストレイヤーをクリア
        this.textLayer.innerHTML = '';
        
        try {
            const textContent = await page.getTextContent();
            
            // テキストアイテムを配置
            textContent.items.forEach(item => {
                const textDiv = document.createElement('span');
                textDiv.textContent = item.str;
                textDiv.style.position = 'absolute';
                textDiv.style.left = item.transform[4] + 'px';
                textDiv.style.top = (viewport.height - item.transform[5]) + 'px';
                textDiv.style.fontSize = Math.abs(item.transform[0]) + 'px';
                textDiv.style.transform = `scaleX(${item.transform[0] / Math.abs(item.transform[0])})`;
                textDiv.style.transformOrigin = '0% 0%';
                textDiv.setAttribute('data-text', item.str);
                
                this.textLayer.appendChild(textDiv);
            });
            
        } catch (error) {
            console.error('テキストレイヤーレンダリングエラー:', error);
        }
    }
    
    renderHighlights() {
        // 既存のハイライトをクリア
        this.highlightOverlay.innerHTML = '';
        
        if (!this.detectionResults || this.detectionResults.length === 0) return;
        
        // 現在のページのハイライトを表示
        const pageHighlights = this.detectionResults.filter(entity => 
            entity.page === this.currentPage + 1
        );
        
        pageHighlights.forEach((entity, index) => {
            if (entity.coordinates) {
                const highlight = this.createHighlightElement(entity, index);
                this.highlightOverlay.appendChild(highlight);
            }
        });
    }
    
    createHighlightElement(entity, index) {
        const highlight = document.createElement('div');
        highlight.className = 'highlight-rect';
        highlight.classList.add(entity.entity_type.toLowerCase());
        
        if (this.selectedEntityIndex === index) {
            highlight.classList.add('selected');
        }
        
        // 座標を設定（PDF.jsの座標系に合わせて調整）
        const scale = this.zoomLevel / 100;
        const coords = entity.coordinates;
        
        highlight.style.left = coords.x0 * scale + 'px';
        highlight.style.top = coords.y0 * scale + 'px';
        highlight.style.width = (coords.x1 - coords.x0) * scale + 'px';
        highlight.style.height = (coords.y1 - coords.y0) * scale + 'px';
        
        // クリックイベント
        highlight.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectEntity(index);
        });
        
        // ツールチップ
        highlight.title = `${this.getEntityTypeJapanese(entity.entity_type)}: ${entity.text}`;
        
        return highlight;
    }
    
    checkHighlightSelection(x, y) {
        // クリック位置にハイライトがあるかチェック
        const highlights = this.highlightOverlay.querySelectorAll('.highlight-rect');
        let selectedIndex = -1;
        
        highlights.forEach((highlight, index) => {
            const rect = highlight.getBoundingClientRect();
            const canvasRect = this.pdfCanvas.getBoundingClientRect();
            
            const highlightX = rect.left - canvasRect.left;
            const highlightY = rect.top - canvasRect.top;
            const highlightWidth = rect.width;
            const highlightHeight = rect.height;
            
            if (x >= highlightX && x <= highlightX + highlightWidth &&
                y >= highlightY && y <= highlightY + highlightHeight) {
                selectedIndex = index;
            }
        });
        
        if (selectedIndex >= 0) {
            this.selectEntity(selectedIndex);
        } else {
            this.clearSelection();
        }
    }
    
    handleTextSelection(startX, startY, currentX, currentY) {
        // テキスト選択の表示領域を作成/更新
        if (!this.textSelection) {
            this.textSelection = document.createElement('div');
            this.textSelection.className = 'text-selection';
            this.highlightOverlay.appendChild(this.textSelection);
        }
        
        const minX = Math.min(startX, currentX);
        const minY = Math.min(startY, currentY);
        const maxX = Math.max(startX, currentX);
        const maxY = Math.max(startY, currentY);
        
        this.textSelection.style.left = minX + 'px';
        this.textSelection.style.top = minY + 'px';
        this.textSelection.style.width = (maxX - minX) + 'px';
        this.textSelection.style.height = (maxY - minY) + 'px';
    }
    
    async finalizeTextSelection() {
        if (!this.textSelection) return;
        
        // 選択範囲のテキストを取得
        const rect = this.textSelection.getBoundingClientRect();
        const canvasRect = this.pdfCanvas.getBoundingClientRect();
        
        const selectionRect = {
            left: rect.left - canvasRect.left,
            top: rect.top - canvasRect.top,
            width: rect.width,
            height: rect.height
        };
        
        const selectedText = await this.getTextInArea(selectionRect);
        
        if (selectedText.trim()) {
            // 新しいハイライトとして追加
            this.addNewHighlight(selectedText, selectionRect);
        }
        
        // 選択表示を削除
        this.textSelection.remove();
        this.textSelection = null;
    }
    
    async getTextInArea(selectionRect) {
        // テキストレイヤーから選択範囲内のテキストを抽出
        const textSpans = this.textLayer.querySelectorAll('span');
        let selectedText = '';
        
        textSpans.forEach(span => {
            const spanRect = span.getBoundingClientRect();
            const canvasRect = this.pdfCanvas.getBoundingClientRect();
            
            const spanX = spanRect.left - canvasRect.left;
            const spanY = spanRect.top - canvasRect.top;
            
            // 選択範囲内にあるかチェック
            if (spanX >= selectionRect.left &&
                spanY >= selectionRect.top &&
                spanX <= selectionRect.left + selectionRect.width &&
                spanY <= selectionRect.top + selectionRect.height) {
                selectedText += span.textContent;
            }
        });
        
        return selectedText;
    }
    
    addNewHighlight(text, rect) {
        // 新しいハイライトをdetectionResultsに追加
        const scale = this.zoomLevel / 100;
        const newEntity = {
            entity_type: 'CUSTOM',
            text: text,
            confidence: 1.0,
            page: this.currentPage + 1,
            coordinates: {
                x0: rect.left / scale,
                y0: rect.top / scale,
                x1: (rect.left + rect.width) / scale,
                y1: (rect.top + rect.height) / scale
            }
        };
        
        this.detectionResults.push(newEntity);
        this.renderEntityList();
        this.renderHighlights();
        this.updateStatus(`新しいハイライトを追加: ${text}`);
    }
    
    selectWordAtPosition(x, y) {
        // 指定位置の単語を選択
        const textSpans = this.textLayer.querySelectorAll('span');
        
        textSpans.forEach(span => {
            const rect = span.getBoundingClientRect();
            const canvasRect = this.pdfCanvas.getBoundingClientRect();
            
            const spanX = rect.left - canvasRect.left;
            const spanY = rect.top - canvasRect.top;
            const spanWidth = rect.width;
            const spanHeight = rect.height;
            
            if (x >= spanX && x <= spanX + spanWidth &&
                y >= spanY && y <= spanY + spanHeight) {
                // この単語を新しいハイライトとして追加
                const wordRect = {
                    left: spanX,
                    top: spanY,
                    width: spanWidth,
                    height: spanHeight
                };
                this.addNewHighlight(span.textContent, wordRect);
            }
        });
    }
    
    // 以下は既存のメソッドを継続
    async detectEntities() {
        if (!this.currentPdf) {
            this.showError('PDFファイルを選択してください');
            return;
        }
        
        this.showLoading(true);
        this.updateStatus('個人情報を検出中...');
        
        try {
            const response = await fetch('/api/detect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(this.settings)
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.detectionResults = data.results;
                this.renderEntityList();
                this.renderPdfPage(); // ハイライトを表示
                
                this.elements.saveBtn.disabled = false;
                this.updateStatus(`検出完了: ${data.results.length}件の個人情報が見つかりました`);
            } else {
                this.showError(data.message);
            }
        } catch (error) {
            console.error('検出エラー:', error);
            this.showError('個人情報の検出に失敗しました');
        } finally {
            this.showLoading(false);
        }
    }
    
    renderEntityList() {
        this.elements.entityList.innerHTML = '';
        this.elements.resultCount.textContent = this.detectionResults.length;
        
        this.detectionResults.forEach((entity, index) => {
            const listItem = document.createElement('div');
            listItem.className = `list-group-item list-group-item-action ${index === this.selectedEntityIndex ? 'active' : ''}`;
            listItem.style.cursor = 'pointer';
            
            const entityTypeJa = this.getEntityTypeJapanese(entity.entity_type || entity.type);
            const confidencePercent = Math.round(entity.confidence * 100);
            
            listItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${entityTypeJa}</h6>
                        <p class="mb-1 text-truncate">${entity.text}</p>
                        <small class="text-muted">信頼度: ${confidencePercent}% | ページ: ${entity.page}</small>
                    </div>
                    <div class="ms-2">
                        <span class="badge bg-primary">${confidencePercent}%</span>
                    </div>
                </div>
            `;
            
            listItem.addEventListener('click', () => {
                this.selectEntity(index);
            });
            
            this.elements.entityList.appendChild(listItem);
        });
    }
    
    selectEntity(index) {
        this.selectedEntityIndex = index;
        this.selectedHighlight = this.detectionResults[index];
        this.renderEntityList();
        
        // 該当ページに移動
        const entity = this.detectionResults[index];
        const targetPage = entity.page - 1;
        if (targetPage !== this.currentPage) {
            this.currentPage = targetPage;
            this.updatePageInfo();
            this.renderPdfPage();
        } else {
            this.renderHighlights(); // 選択状態を更新
        }
        
        // 編集コントロールを表示
        if (this.selectedHighlight) {
            this.showHighlightEditControls(this.selectedHighlight);
        }
    }
    
    previousPage() {
        if (this.currentPage > 0) {
            this.currentPage--;
            this.updatePageInfo();
            this.renderPdfPage();
        }
    }
    
    nextPage() {
        if (this.currentPage < this.totalPages - 1) {
            this.currentPage++;
            this.updatePageInfo();
            this.renderPdfPage();
        }
    }
    
    updatePageInfo() {
        this.elements.pageInfo.textContent = `${this.currentPage + 1} / ${this.totalPages}`;
        this.elements.prevPageBtn.disabled = this.currentPage === 0;
        this.elements.nextPageBtn.disabled = this.currentPage === this.totalPages - 1;
    }
    
    updateZoom(value) {
        this.zoomLevel = parseInt(value);
        
        if (this.elements.zoomValue) {
            this.elements.zoomValue.textContent = this.zoomLevel + '%';
        }
        if (this.elements.zoomDisplay) {
            this.elements.zoomDisplay.textContent = this.zoomLevel + '%';
        }
        
        this.renderPdfPage();
    }
    
    showHighlightEditControls(highlight) {
        this.editMode = true;
        
        if (this.elements.selectedHighlightText) {
            this.elements.selectedHighlightText.textContent = highlight.text;
        }
        if (this.elements.selectedHighlightType) {
            const typeText = this.getEntityTypeJapanese(highlight.entity_type || highlight.type);
            this.elements.selectedHighlightType.textContent = typeText;
        }
        if (this.elements.selectedHighlightConfidence) {
            const confText = (highlight.confidence * 100).toFixed(1) + '%';
            this.elements.selectedHighlightConfidence.textContent = confText;
        }
        if (this.elements.selectedHighlightPage) {
            const pageText = highlight.page || '-';
            this.elements.selectedHighlightPage.textContent = pageText;
        }
        if (this.elements.selectedHighlightPosition) {
            if (highlight.coordinates) {
                const posText = `(${Math.round(highlight.coordinates.x0)}, ${Math.round(highlight.coordinates.y0)})`;
                this.elements.selectedHighlightPosition.textContent = posText;
            } else {
                this.elements.selectedHighlightPosition.textContent = '座標不明';
            }
        }
    }
    
    clearSelection() {
        this.selectedHighlight = null;
        this.selectedEntityIndex = -1;
        this.editMode = false;
        
        if (this.elements.selectedHighlightText) {
            this.elements.selectedHighlightText.textContent = 'ハイライトをクリックしてください';
        }
        if (this.elements.selectedHighlightType) {
            this.elements.selectedHighlightType.textContent = '-';
        }
        if (this.elements.selectedHighlightConfidence) {
            this.elements.selectedHighlightConfidence.textContent = '-';
        }
        if (this.elements.selectedHighlightPage) {
            this.elements.selectedHighlightPage.textContent = '-';
        }
        if (this.elements.selectedHighlightPosition) {
            this.elements.selectedHighlightPosition.textContent = '-';
        }
        
        this.renderEntityList();
        this.renderHighlights();
        this.updateStatus('選択を解除しました');
    }
    
    deleteHighlight() {
        if (this.selectedEntityIndex >= 0 && this.selectedEntityIndex < this.detectionResults.length) {
            const deletedEntity = this.detectionResults[this.selectedEntityIndex];
            const entityIndex = this.selectedEntityIndex;
            
            fetch(`/api/delete_entity/${entityIndex}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.detectionResults.splice(entityIndex, 1);
                    this.clearSelection();
                    this.renderEntityList();
                    this.renderHighlights();
                    this.updateStatus(`ハイライトを削除しました: ${deletedEntity.text}`);
                } else {
                    this.showError(data.message || 'ハイライト削除に失敗しました');
                }
            })
            .catch(error => {
                console.error('ハイライト削除エラー:', error);
                this.showError('ハイライト削除に失敗しました');
            });
        } else {
            this.showError('削除するハイライトが選択されていません');
        }
    }
    
    adjustHighlight(adjustmentType) {
        if (!this.selectedHighlight) {
            this.showError('ハイライトが選択されていません');
            return;
        }
        
        fetch('/api/highlights/adjust', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                highlight_id: this.selectedEntityIndex,
                page_num: this.currentPage,
                adjustment_type: adjustmentType,
                amount: 1
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.selectedHighlight = data.updated_highlight;
                this.detectionResults[this.selectedEntityIndex] = data.updated_highlight;
                this.showHighlightEditControls(this.selectedHighlight);
                this.renderEntityList();
                this.renderHighlights();
                this.updateStatus(data.message);
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            console.error('ハイライト調整エラー:', error);
            this.showError('ハイライト調整に失敗しました');
        });
    }
    
    handleKeyDown(event) {
        if (!this.editMode || !this.selectedHighlight) {
            return;
        }
        
        switch(event.key) {
            case 'ArrowLeft':
                if (event.shiftKey) {
                    this.adjustHighlight('shrink_right');
                } else {
                    this.adjustHighlight('extend_left');
                }
                event.preventDefault();
                break;
            case 'ArrowRight':
                if (event.shiftKey) {
                    this.adjustHighlight('shrink_left');
                } else {
                    this.adjustHighlight('extend_right');
                }
                event.preventDefault();
                break;
            case 'Escape':
                this.clearSelection();
                event.preventDefault();
                break;
        }
    }
    
    // その他のメソッド（設定、保存など）
    async savePdf() {
        if (!this.currentPdf) {
            this.showError('PDFファイルが選択されていません');
            return;
        }
        
        this.showLoading(true);
        this.updateStatus('PDFを保存中...');
        
        try {
            const response = await fetch('/api/generate_pdf', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    entities: this.detectionResults,
                    masking_method: this.settings.masking_method
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.updateStatus('PDFの保存が完了しました');
                
                const link = document.createElement('a');
                link.href = `/api/download_pdf/${data.filename}`;
                link.download = data.download_filename || data.filename;
                link.click();
            } else {
                this.showError(data.message);
            }
        } catch (error) {
            console.error('保存エラー:', error);
            this.showError('PDFの保存に失敗しました');
        } finally {
            this.showLoading(false);
        }
    }
    
    saveSettings() {
        const selectedEntities = [];
        ['PERSON', 'LOCATION', 'PHONE_NUMBER', 'DATE_TIME'].forEach(entity => {
            const checkbox = document.getElementById('entity' + entity.charAt(0) + entity.slice(1).toLowerCase().replace('_', ''));
            if (checkbox && checkbox.checked) {
                selectedEntities.push(entity);
            }
        });
        
        this.settings.entities = selectedEntities;
        this.settings.threshold = parseFloat(this.elements.thresholdSlider.value);
        this.settings.masking_method = document.getElementById('maskingMethod').value;
        
        fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(this.settings)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.updateStatus('設定を保存しました');
                const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
                modal.hide();
            } else {
                this.showError(data.message);
            }
        })
        .catch(error => {
            console.error('設定保存エラー:', error);
            this.showError('設定の保存に失敗しました');
        });
    }
    
    loadSettings() {
        fetch('/api/settings')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.settings = data.settings;
                
                this.elements.thresholdSlider.value = this.settings.threshold;
                this.elements.thresholdValue.textContent = this.settings.threshold;
                
                ['PERSON', 'LOCATION', 'PHONE_NUMBER', 'DATE_TIME'].forEach(entity => {
                    const checkbox = document.getElementById('entity' + entity.charAt(0) + entity.slice(1).toLowerCase().replace('_', ''));
                    if (checkbox) {
                        checkbox.checked = this.settings.entities.includes(entity);
                    }
                });
            }
        })
        .catch(error => {
            console.error('設定読み込みエラー:', error);
        });
    }
    
    getEntityTypeJapanese(entityType) {
        const mapping = {
            "PERSON": "人名",
            "LOCATION": "場所",
            "PHONE_NUMBER": "電話番号",
            "DATE_TIME": "日時",
            "CUSTOM": "カスタム"
        };
        return mapping[entityType] || entityType;
    }
    
    updateStatus(message) {
        if (this.elements.statusMessage) {
            this.elements.statusMessage.textContent = message;
        } else {
            console.log('Status:', message);
        }
    }
    
    showError(message) {
        this.updateStatus('エラー: ' + message);
        console.error(message);
    }
    
    showLoading(show) {
        if (this.elements.loadingOverlay) {
            if (show) {
                this.elements.loadingOverlay.classList.add('show');
            } else {
                this.elements.loadingOverlay.classList.remove('show');
            }
        }
    }
    
    setupZoomSlider() {
        if (!this.elements.zoomSlider) {
            console.warn('Zoom slider element not found');
            return;
        }
        
        this.elements.zoomSlider.min = 25;
        this.elements.zoomSlider.max = 400;
        this.elements.zoomSlider.step = 25;
        this.elements.zoomSlider.value = this.zoomLevel;
        
        if (this.elements.zoomValue) {
            this.elements.zoomValue.textContent = this.zoomLevel + '%';
        }
        if (this.elements.zoomDisplay) {
            this.elements.zoomDisplay.textContent = this.zoomLevel + '%';
        }
    }
}

// グローバルアプリインスタンス
let app;

// アプリケーションの初期化
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM Content Loaded');
    console.log('Creating PresidioPDFWebApp instance...');
    app = new PresidioPDFWebApp();
    console.log('App instance created:', app);
});