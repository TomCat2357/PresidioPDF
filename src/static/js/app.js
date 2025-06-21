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
        
        // 手動追加関連の状態
        this.manualAddMode = '';  // 選択中のエンティティタイプ
        this.currentSelection = null;
        
        // PDF.js関連
        this.pdfCanvas = null;
        this.pdfContext = null;
        this.textLayer = null;
        this.highlightOverlay = null;
        this.viewport = null; // ビューポートを保持
        
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
            deleteHighlightBtn: document.getElementById('deleteHighlightBtn'),
            // 手動追加関連
            contextMenu: document.getElementById('contextMenu'),
            cancelSelection: document.getElementById('cancelSelection')
        };
    }
    
    initializePdfViewer() {
        this.pdfCanvas = this.elements.pdfCanvas;
        if (this.pdfCanvas) {
            this.pdfContext = this.pdfCanvas.getContext('2d');
        }
        this.textLayer = this.elements.textLayer;
        this.highlightOverlay = this.elements.highlightOverlay;
    }
    
    bindEvents() {
        this.elements.uploadArea.addEventListener('click', () => this.elements.pdfFileInput.click());
        this.elements.pdfFileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files[0]));
        this.elements.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.elements.uploadArea.classList.add('dragover');
        });
        this.elements.uploadArea.addEventListener('dragleave', () => this.elements.uploadArea.classList.remove('dragover'));
        this.elements.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            this.elements.uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) this.handleFileSelect(files[0]);
        });

        this.elements.detectBtn.addEventListener('click', () => this.detectEntities());
        this.elements.prevPageBtn.addEventListener('click', () => this.previousPage());
        this.elements.nextPageBtn.addEventListener('click', () => this.nextPage());
        this.elements.zoomSlider.addEventListener('input', (e) => this.updateZoom(parseInt(e.target.value)));
        this.elements.showHighlights.addEventListener('change', () => this.renderHighlights());
        this.elements.saveBtn.addEventListener('click', () => this.savePdf());
        this.elements.thresholdSlider.addEventListener('input', (e) => { this.elements.thresholdValue.textContent = e.target.value; });
        this.elements.saveSettingsBtn.addEventListener('click', () => this.saveSettings());
        this.elements.clearSelectionBtn?.addEventListener('click', () => this.clearSelection());
        this.elements.deleteHighlightBtn?.addEventListener('click', () => this.deleteHighlight());
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        this.setupPdfCanvasEvents();
        this.setupManualAddEvents();
    }

    setupPdfCanvasEvents() {
        // テキスト選択後のマウスアップイベントで選択範囲を取得
        this.elements.pdfViewer.addEventListener('mouseup', (e) => {
            if (e.button !== 2) { // 右クリック以外
                setTimeout(() => this.handleSelection(e), 50);
            }
        });

        // 右クリックでコンテキストメニューを表示
        this.elements.pdfViewer.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.handleSelection(e, true);
        });
    }
    
    handleSelection(event, isContextMenu = false) {
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();

        if (selectedText) {
            const range = selection.getRangeAt(0);
            const rect = range.getBoundingClientRect();
            const canvasRect = this.elements.pdfCanvas.getBoundingClientRect();
            
            // 選択範囲を保存
            this.currentSelection = {
                text: selectedText,
                rect: { // canvasに対する相対CSSピクセル座標
                    left: rect.left - canvasRect.left,
                    top: rect.top - canvasRect.top,
                    width: rect.width,
                    height: rect.height,
                }
            };

            // 手動モードなら即時追加、そうでなければコンテキストメニュー表示
            if (this.manualAddMode && !isContextMenu) {
                this.addEntityFromSelection(this.manualAddMode);
            } else {
                this.showContextMenu(event.pageX, event.pageY);
            }
        } else if (!isContextMenu) {
            this.clearSelection();
        }
    }

    setupManualAddEvents() {
        const entityModeInputs = document.querySelectorAll('input[name="entityMode"]');
        entityModeInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                this.manualAddMode = e.target.value;
                this.updateCanvasCursor();
            });
        });

        const contextMenuItems = this.elements.contextMenu.querySelectorAll('.context-menu-item[data-entity-type]');
        contextMenuItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const entityType = e.currentTarget.getAttribute('data-entity-type');
                this.addEntityFromSelection(entityType);
                this.hideContextMenu();
            });
        });

        this.elements.cancelSelection?.addEventListener('click', () => {
            this.cancelCurrentSelection();
            this.hideContextMenu();
        });

        document.addEventListener('click', (e) => {
            if (!this.elements.contextMenu.contains(e.target)) this.hideContextMenu();
        });
    }

    async handleFileSelect(file) {
        if (!file || file.type !== 'application/pdf') {
            this.showError('PDFファイルを選択してください');
            return;
        }
        
        try {
            this.showLoading(true);
            this.updateStatus('PDFファイルを読み込み中...');
            
            const arrayBuffer = await file.arrayBuffer();
            this.currentPdfDocument = await pdfjsLib.getDocument(arrayBuffer).promise;
            this.totalPages = this.currentPdfDocument.numPages;
            this.currentPage = 0;
            
            this.elements.selectedFileName.textContent = file.name;
            this.elements.detectBtn.disabled = false;
            this.updatePageInfo();
            
            this.elements.pdfPlaceholder.style.display = 'none';
            this.elements.pdfCanvasContainer.style.display = 'block';
            
            await this.renderPdfPage();
            await this.uploadToFlask(file);
            
            this.updateStatus('PDFファイルの読み込みが完了しました');
        } catch (error) {
            console.error('PDFファイル読み込みエラー:', error);
            this.showError('PDFファイルの読み込みに失敗しました');
        } finally {
            this.showLoading(false);
        }
    }

    async uploadToFlask(file) {
        const formData = new FormData();
        formData.append('pdf_file', file);
        
        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await response.json();
        if (!data.success) throw new Error(data.message);
        this.currentPdf = data.filename;
    }

    async renderPdfPage() {
        if (!this.currentPdfDocument) return;
        this.showLoading(true);

        try {
            const page = await this.currentPdfDocument.getPage(this.currentPage + 1);
            const scale = this.zoomLevel / 100;
            this.viewport = page.getViewport({ scale });

            this.pdfCanvas.width = this.viewport.width;
            this.pdfCanvas.height = this.viewport.height;
            this.pdfCanvas.style.width = this.viewport.width + 'px';
            this.pdfCanvas.style.height = this.viewport.height + 'px';

            this.textLayer.style.width = this.viewport.width + 'px';
            this.textLayer.style.height = this.viewport.height + 'px';
            this.highlightOverlay.style.width = this.viewport.width + 'px';
            this.highlightOverlay.style.height = this.viewport.height + 'px';
            
            const renderContext = { canvasContext: this.pdfContext, viewport: this.viewport };
            await page.render(renderContext).promise;
            await this.renderTextLayer(page, this.viewport);
            
            this.renderHighlights();
        } catch (error) {
            console.error('PDFページレンダリングエラー:', error);
            this.showError('PDFページの表示に失敗しました');
        } finally {
            this.showLoading(false);
        }
    }

    async renderTextLayer(page, viewport) {
        this.textLayer.innerHTML = '';
        try {
            const textContent = await page.getTextContent();
            pdfjsLib.renderTextLayer({
                textContentSource: textContent,
                container: this.textLayer,
                viewport: viewport,
                textDivs: []
            });
        } catch (error) {
            console.error('テキストレイヤーレンダリングエラー:', error);
        }
    }

    renderHighlights() {
        this.highlightOverlay.innerHTML = '';
        if (!this.detectionResults) return;

        const pageHighlights = this.detectionResults.filter(entity => entity.page === this.currentPage + 1);
        pageHighlights.forEach((entity, localIndex) => {
            const globalIndex = this.detectionResults.indexOf(entity);
            const highlight = this.createHighlightElement(entity, globalIndex);
            if (highlight) this.highlightOverlay.appendChild(highlight);
        });
    }

    createHighlightElement(entity, index) {
        const coords = entity.coordinates;
        if (!coords || !this.viewport) return null;

        const highlight = document.createElement('div');
        highlight.className = 'highlight-rect';
        highlight.classList.add(entity.entity_type.toLowerCase());
        if (this.selectedEntityIndex === index) {
            highlight.classList.add('selected');
        }

        const pdfRect = [coords.x0, coords.y0, coords.x1, coords.y1];
        const viewportRect = this.viewport.convertToViewportRect(pdfRect);
        
        highlight.style.left = viewportRect[0] + 'px';
        highlight.style.top = viewportRect[1] + 'px';
        highlight.style.width = viewportRect[2] - viewportRect[0] + 'px';
        highlight.style.height = viewportRect[3] - viewportRect[1] + 'px';

        highlight.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectEntity(index);
        });

        highlight.title = `${this.getEntityTypeJapanese(entity.entity_type)}: ${entity.text}`;
        return highlight;
    }

    addEntityFromSelection(entityType) {
        if (!this.currentSelection) return;
        try {
            const canvasRect = this.currentSelection.rect;
            const topLeft = this.viewport.convertToPdfPoint(canvasRect.left, canvasRect.top);
            const bottomRight = this.viewport.convertToPdfPoint(canvasRect.left + canvasRect.width, canvasRect.top + canvasRect.height);

            const newEntity = {
                entity_type: entityType,
                text: this.currentSelection.text,
                confidence: 1.0,
                page: this.currentPage + 1,
                coordinates: {
                    x0: Math.min(topLeft[0], bottomRight[0]),
                    y0: Math.min(topLeft[1], bottomRight[1]),
                    x1: Math.max(topLeft[0], bottomRight[0]),
                    y1: Math.max(topLeft[1], bottomRight[1]),
                }
            };
            
            this.detectionResults.push(newEntity);
            this.renderEntityList();
            this.renderHighlights();
            this.updateStatus(`${this.getEntityTypeJapanese(entityType)}を追加: ${this.currentSelection.text}`);
        } catch (error) {
            console.error('エンティティ追加エラー:', error);
        } finally {
            this.cancelCurrentSelection();
        }
    }

    cancelCurrentSelection() {
        if (this.currentSelection && this.currentSelection.element) {
            this.currentSelection.element.remove();
        }
        this.currentSelection = null;
        window.getSelection().removeAllRanges();
        this.hideContextMenu();
    }
    
    updateCanvasCursor() {
        this.pdfCanvas.className = 'pdf-canvas'; // Reset
        if (this.manualAddMode) {
            this.pdfCanvas.classList.add('selection-mode', this.manualAddMode.toLowerCase().replace('_', ''));
        }
    }

    showContextMenu(x, y) {
        if (!this.elements.contextMenu) return;
        
        this.elements.contextMenu.style.display = 'block';
        const menuRect = this.elements.contextMenu.getBoundingClientRect();
        const posX = (x + menuRect.width > window.innerWidth) ? (window.innerWidth - menuRect.width - 10) : x;
        const posY = (y + menuRect.height > window.innerHeight) ? (window.innerHeight - menuRect.height - 10) : y;
        this.elements.contextMenu.style.left = posX + 'px';
        this.elements.contextMenu.style.top = posY + 'px';
    }

    hideContextMenu() {
        if (this.elements.contextMenu) this.elements.contextMenu.style.display = 'none';
    }
    
    // ... (rest of the methods like detectEntities, renderEntityList, selectEntity, pagination, zoom, etc. remain largely the same)
    // ... all other methods from the original file should be here ...

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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.settings)
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.detectionResults = data.results;
                this.renderEntityList();
                this.renderHighlights();
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
        
        const entity = this.detectionResults[index];
        const targetPage = entity.page - 1;
        if (targetPage !== this.currentPage) {
            this.currentPage = targetPage;
            this.updatePageInfo();
            this.renderPdfPage();
        } else {
            this.renderHighlights();
        }
    }

    clearSelection() {
        this.selectedHighlight = null;
        this.selectedEntityIndex = -1;
        this.renderEntityList();
        this.renderHighlights();
        this.updateStatus('選択を解除しました');
    }

    deleteHighlight() {
        if (this.selectedEntityIndex === -1) {
            this.showError('削除するハイライトが選択されていません');
            return;
        }

        const entityIndex = this.selectedEntityIndex;
        fetch(`/api/delete_entity/${entityIndex}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.detectionResults.splice(entityIndex, 1);
                this.clearSelection();
            } else {
                this.showError(data.message || 'ハイライト削除に失敗しました');
            }
        })
        .catch(error => {
            console.error('ハイライト削除エラー:', error);
            this.showError('ハイライト削除に失敗しました');
        });
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
        this.elements.nextPageBtn.disabled = this.currentPage >= this.totalPages - 1;
    }

    updateZoom(value) {
        this.zoomLevel = parseInt(value);
        if (this.elements.zoomValue) {
            this.elements.zoomValue.textContent = this.zoomLevel + '%';
        }
        if (this.elements.zoomDisplay) {
            this.elements.zoomDisplay.textContent = this.zoomLevel + '%';
        }
        if (this.currentPdfDocument) {
            this.renderPdfPage();
        }
    }

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
                headers: { 'Content-Type': 'application/json' },
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
        // ... (this method can remain as is)
    }
    
    loadSettings() {
        // ... (this method can remain as is)
    }

    getEntityTypeJapanese(entityType) {
        const mapping = {
            "PERSON": "人名", "LOCATION": "場所", "PHONE_NUMBER": "電話番号",
            "DATE_TIME": "日時", "CUSTOM": "カスタム"
        };
        return mapping[entityType] || entityType;
    }
    
    updateStatus(message) {
        this.elements.statusMessage.textContent = message;
    }
    
    showError(message) {
        this.updateStatus('エラー: ' + message);
        console.error(message);
    }
    
    showLoading(show) {
        this.elements.loadingOverlay.style.display = show ? 'flex' : 'none';
    }

    setupZoomSlider() {
        // ... (this method can remain as is)
    }
}

// グローバルアプリインスタンス
let app;

// アプリケーションの初期化
document.addEventListener('DOMContentLoaded', () => {
    app = new PresidioPDFWebApp();
});