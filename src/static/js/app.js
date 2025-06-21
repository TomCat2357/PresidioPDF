/**
 * PDF個人情報マスキングツール - Webアプリケーション
 * JavaScript フロントエンド（PDF.js統合版）
 */

document.addEventListener('DOMContentLoaded', () => {
    // PDF.jsのグローバルワーカーを設定
    if (typeof pdfjsLib === 'undefined') {
        console.error('PDF.js library not found!');
        return;
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    class PresidioPDFWebApp {
        constructor() {
            this.currentPdfDocument = null;
            this.currentPdfPath = null;
            this.currentPage = 1;
            this.totalPages = 0;
            this.zoomLevel = 100;
            this.detectionResults = [];
            this.selectedEntityIndex = -1;
            this.currentSelection = null;
            this.viewport = null;
            
            // 選択範囲のバッファ（最新10件まで保存）
            this.selectionHistory = [];
            this.maxSelectionHistory = 10;

            this.settings = {
                entities: ["PERSON", "LOCATION", "PHONE_NUMBER", "DATE_TIME"],
                threshold: 0.5,
                masking_method: "highlight"
            };

            this.initializeElements();
            this.bindEvents();
            this.loadSettings();
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
                thresholdSlider: document.getElementById('thresholdSlider'),
                thresholdValue: document.getElementById('thresholdValue'),
                saveSettingsBtn: document.getElementById('saveSettingsBtn'),
                contextMenu: document.getElementById('contextMenu'),
                cancelSelection: document.getElementById('cancelSelection')
            };
            this.pdfContext = this.elements.pdfCanvas.getContext('2d');
        }

        // =================================================================
        // ==  イベント処理の根本的な修正  ==
        // =================================================================
        bindEvents() {
            // --- ファイル操作と基本的なUIボタンのイベント ---
            this.elements.uploadArea.addEventListener('click', () => this.elements.pdfFileInput.click());
            this.elements.pdfFileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files[0]));
            ['dragover', 'dragleave', 'drop'].forEach(eventName => {
                this.elements.uploadArea.addEventListener(eventName, this.preventDefaults, false);
            });
            ['dragenter', 'dragover'].forEach(eventName => {
                this.elements.uploadArea.addEventListener(eventName, () => this.elements.uploadArea.classList.add('dragover'), false);
            });
            ['dragleave', 'drop'].forEach(eventName => {
                this.elements.uploadArea.addEventListener(eventName, () => this.elements.uploadArea.classList.remove('dragover'), false);
            });
            this.elements.uploadArea.addEventListener('drop', (e) => this.handleFileDrop(e), false);

            this.elements.detectBtn.addEventListener('click', () => this.detectEntities());
            this.elements.prevPageBtn.addEventListener('click', () => this.changePage(this.currentPage - 1));
            this.elements.nextPageBtn.addEventListener('click', () => this.changePage(this.currentPage + 1));
            this.elements.zoomSlider.addEventListener('input', (e) => this.updateZoom(parseInt(e.target.value, 10)));
            this.elements.showHighlights.addEventListener('change', () => this.renderHighlights());
            this.elements.saveBtn.addEventListener('click', () => this.generateAndDownloadPdf());
            this.elements.thresholdSlider.addEventListener('input', (e) => { this.elements.thresholdValue.textContent = e.target.value; });
            this.elements.saveSettingsBtn.addEventListener('click', () => this.saveSettings());

            // --- PDFビューアのインタラクティブなイベント（整理・統合済み） ---

            // 1. マウスのボタンが押された時のログ出力
            this.elements.pdfViewer.addEventListener('mousedown', (e) => {
                if (e.button === 0) { // 左クリックのみ
                    console.log('Mouse Down (Left Button)', { x: e.clientX, y: e.clientY });
                }
            });

            // 2. マウスがドラッグされている間のログ出力
            this.elements.pdfViewer.addEventListener('mousemove', (e) => {
                if (e.buttons & 1) { // 左クリックが押されている場合
                    console.log('Mouse Move (Left Button Held)', { x: e.clientX, y: e.clientY });
                }
            });

            // 3. 左クリックを離した時に、選択範囲をエンティティとして追加
            let mouseDownPosition = null;
            let selectionAtMouseDown = null;
            
            this.elements.pdfViewer.addEventListener('mousedown', (e) => {
                if (e.button === 0) {
                    mouseDownPosition = { x: e.clientX, y: e.clientY };
                    selectionAtMouseDown = window.getSelection().toString();
                }
            });
            
            this.elements.pdfViewer.addEventListener('mouseup', (e) => {
                if (e.button === 0) { // 左クリックのみ
                    console.log('Mouse Up (Left Button)', { x: e.clientX, y: e.clientY });
                    
                    // マウスが移動していない場合（単純なクリック）は処理しない
                    if (mouseDownPosition && 
                        Math.abs(e.clientX - mouseDownPosition.x) < 5 && 
                        Math.abs(e.clientY - mouseDownPosition.y) < 5) {
                        console.log('Single click detected, skipping selection processing');
                        return;
                    }
                    
                    // 短い遅延の代わりに、すぐに処理を実行
                    const selection = window.getSelection();
                    let currentSelection = null;
                    
                    console.log('Selection object:', selection);
                    console.log('Range count:', selection?.rangeCount);
                    
                    if (selection && selection.rangeCount > 0) {
                        const range = selection.getRangeAt(0);
                        const selectedText = range.toString().trim();
                        
                        console.log('Selected text:', selectedText);
                        console.log('Range commonAncestorContainer:', range.commonAncestorContainer);
                        console.log('TextLayer element:', this.elements.textLayer);
                        
                        // より厳密な含有チェック
                        let isInTextLayer = false;
                        if (range.commonAncestorContainer) {
                            if (range.commonAncestorContainer === this.elements.textLayer) {
                                isInTextLayer = true;
                            } else if (range.commonAncestorContainer.nodeType === Node.TEXT_NODE) {
                                isInTextLayer = this.elements.textLayer.contains(range.commonAncestorContainer.parentNode);
                            } else {
                                isInTextLayer = this.elements.textLayer.contains(range.commonAncestorContainer);
                            }
                        }
                        
                        console.log('Contains check:', isInTextLayer);
                        
                        // 選択範囲がtextLayerの中にあり、テキストが存在するかチェック
                        if (selectedText && selectedText.length > 0 && isInTextLayer) {
                            const rect = range.getBoundingClientRect();
                            const referenceRect = this.elements.textLayer.getBoundingClientRect();
                            
                            currentSelection = {
                                text: selectedText,
                                range: range.cloneRange(),
                                rect: rect,
                                pdfX: rect.left - referenceRect.left,
                                pdfY: rect.top - referenceRect.top,
                                pageNumber: this.currentPage
                            };
                            console.log('Created currentSelection:', currentSelection);
                        } else {
                            console.log('Failed text or contains check:', {
                                hasText: !!selectedText,
                                textLength: selectedText ? selectedText.length : 0,
                                isInTextLayer: isInTextLayer
                            });
                        }
                    } else {
                        console.log('No selection or no ranges');
                    }
                    
                    console.log('Mouse Up - Direct Selection:', currentSelection);
                    
                    // 直接の選択が取得できない場合は、選択履歴から最新の有効な選択を取得
                    if (!currentSelection) {
                        currentSelection = this.getLatestValidSelection();
                        console.log('Using selection from history:', currentSelection);
                    }
                    
                    if (currentSelection && currentSelection.text.length > 0) {
                        const selectedMode = document.querySelector('input[name="entityMode"]:checked');
                        console.log('Selected Mode:', selectedMode, 'Value:', selectedMode?.value);
                        
                        // 一時的にcurrentSelectionを設定
                        this.currentSelection = currentSelection;
                        
                        if (selectedMode && selectedMode.value) {
                            // エンティティタイプが選択されている場合は直接追加
                            console.log('Adding manual entity:', selectedMode.value);
                            this.addManualEntity(selectedMode.value);
                        } else {
                            // エンティティタイプが未選択の場合はコンテキストメニューを表示
                            console.log('Showing context menu at:', e.clientX, e.clientY);
                            this.showContextMenu(e.clientX, e.clientY);
                        }
                    } else {
                        console.log('No valid selection found, even in history');
                    }
                }
            });

            // 4. 右クリックでコンテキストメニューを表示
            this.elements.pdfViewer.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.handleSelection(e, true);
            });

            // 5. テキストの選択範囲が変化するたびに、選択情報を更新し、ログを出力
            document.addEventListener('selectionchange', () => {
                const selection = window.getSelection();
                if (selection && selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    
                    // より厳密な含有チェック
                    let isInTextLayer = false;
                    if (range.commonAncestorContainer) {
                        if (range.commonAncestorContainer === this.elements.textLayer) {
                            isInTextLayer = true;
                        } else if (range.commonAncestorContainer.nodeType === Node.TEXT_NODE) {
                            isInTextLayer = this.elements.textLayer.contains(range.commonAncestorContainer.parentNode);
                        } else {
                            isInTextLayer = this.elements.textLayer.contains(range.commonAncestorContainer);
                        }
                    }
                    
                    if (isInTextLayer) {
                        const selectedText = selection.toString().trim();
                        if (selectedText.length > 0) {
                            console.log(`選択中の文字列: "${selectedText}", 文字数: ${selectedText.length}`);
                            const rect = range.getBoundingClientRect();
                            const referenceRect = this.elements.textLayer.getBoundingClientRect(); 
                            
                            const selectionData = {
                                text: selectedText,
                                range: range.cloneRange(),
                                rect: rect,
                                pdfX: rect.left - referenceRect.left,
                                pdfY: rect.top - referenceRect.top,
                                pageNumber: this.currentPage,
                                timestamp: Date.now()
                            };
                            
                            this.currentSelection = selectionData;
                            
                            // 選択履歴に追加
                            this.addToSelectionHistory(selectionData);
                        } else {
                            this.currentSelection = null;
                        }
                    }
                } else {
                    this.currentSelection = null;
                }
            });
            
            // 6. PDFビューア外のクリックでコンテキストメニューを閉じる
            document.addEventListener('click', (e) => {
                if (this.elements.contextMenu && !this.elements.contextMenu.contains(e.target)) {
                    this.hideContextMenu();
                }
            });
        }
        // =================================================================
        // ==  ここまでが修正点です ==
        // =================================================================
        
        preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        handleFileDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                this.elements.uploadArea.style.borderColor = '#28a745';
                this.elements.uploadArea.style.backgroundColor = '#d4edda';
                this.updateStatus('ファイルを処理中...');
                setTimeout(() => {
                    this.handleFileSelect(files[0]);
                }, 100);
            }
        }

        async handleFileSelect(file) {
            if (!file || file.type !== 'application/pdf') {
                this.showError('PDFファイルを選択してください');
                return;
            }
            this.showLoading(true, 'PDFをアップロード中...');
            
            try {
                const formData = new FormData();
                formData.append('pdf_file', file);
                const response = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await response.json();

                if (!data.success) throw new Error(data.message);

                this.currentPdfPath = data.filename;
                this.elements.selectedFileName.textContent = file.name;
                this.updateStatus('PDFを読み込み中...');
                
                const arrayBuffer = await file.arrayBuffer();
                this.currentPdfDocument = await pdfjsLib.getDocument(arrayBuffer).promise;
                this.totalPages = this.currentPdfDocument.numPages;
                this.currentPage = 1;
                this.elements.detectBtn.disabled = false;
                
                await this.renderPage(this.currentPage);
                this.updateStatus(`PDF読み込み完了: ${file.name}`);

            } catch (error) {
                console.error('File handling error:', error);
                this.showError(error.message || 'ファイルの処理中にエラーが発生しました');
            } finally {
                this.showLoading(false);
            }
        }

        async renderPage(pageNum) {
            if (!this.currentPdfDocument || pageNum < 1 || pageNum > this.totalPages) return;
            this.showLoading(true, 'ページを描画中...');
            try {
                const page = await this.currentPdfDocument.getPage(pageNum);
                const scale = this.zoomLevel / 100;
                this.viewport = page.getViewport({ scale });

                const canvas = this.elements.pdfCanvas;
                const container = this.elements.pdfCanvasContainer;

                container.style.setProperty('--scale-factor', this.viewport.scale);
                canvas.width = this.viewport.width;
                canvas.height = this.viewport.height;

                const renderContext = {
                    canvasContext: this.pdfContext,
                    viewport: this.viewport
                };
                await page.render(renderContext).promise;

                await this.renderTextLayer(page);
                this.renderHighlights();

                this.updatePageInfo();
                this.elements.pdfPlaceholder.style.display = 'none';
                this.elements.pdfCanvasContainer.style.display = 'block';

            } catch (error) {
                console.error(`Error rendering page ${pageNum}:`, error);
                this.showError('ページの描画に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }

        async renderTextLayer(page) {
            const container = this.elements.textLayer;
            container.innerHTML = '';
            container.style.width = `${this.viewport.width}px`;
            container.style.height = `${this.viewport.height}px`;
            
            try {
                const textContent = await page.getTextContent();
                pdfjsLib.renderTextLayer({
                    textContentSource: textContent,
                    container: container,
                    viewport: this.viewport,
                    textDivs: []
                });
            } catch (error) {
                console.error('Failed to render text layer:', error);
            }
        }

        renderHighlights() {
            const container = this.elements.highlightOverlay;
            container.innerHTML = '';
            container.style.width = `${this.viewport.width}px`;
            container.style.height = `${this.viewport.height}px`;

            if (!this.elements.showHighlights.checked || !this.viewport) return;

            const pageEntities = this.detectionResults.filter(e => e.page === this.currentPage);
            pageEntities.forEach((entity, localIndex) => {
                const globalIndex = this.detectionResults.indexOf(entity);
                const el = this.createHighlightElement(entity, globalIndex);
                if (el) container.appendChild(el);
            });
        }
        
        createHighlightElement(entity, index) {
            if (!entity.coordinates) return null;

            const highlightEl = document.createElement('div');
            highlightEl.className = 'highlight-rect';
            highlightEl.classList.add(entity.entity_type.toLowerCase().replace(/_/g, '-'));

            if (index === this.selectedEntityIndex) {
                highlightEl.classList.add('selected');
            }

            const pageHeight = this.viewport.viewBox[3];
            const pdfRect = [
                entity.coordinates.x0,
                pageHeight - entity.coordinates.y1,
                entity.coordinates.x1,
                pageHeight - entity.coordinates.y0
            ];

            const viewportRect = this.viewport.convertToViewportRectangle(pdfRect);
            
            const left = Math.min(viewportRect[0], viewportRect[2]);
            const top = Math.min(viewportRect[1], viewportRect[3]);
            const right = Math.max(viewportRect[0], viewportRect[2]);
            const bottom = Math.max(viewportRect[1], viewportRect[3]);
            
            const width = right - left;
            const height = bottom - top;
            
            const minHeight = 12;
            const adjustedHeight = Math.max(height, minHeight);

            highlightEl.style.left = `${left}px`;
            highlightEl.style.top = `${top}px`;
            highlightEl.style.width = `${width}px`;
            highlightEl.style.height = `${adjustedHeight}px`;
            highlightEl.dataset.index = index;
            
            highlightEl.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectEntity(index);
                this.scrollToEntityInList(index);
            });

            return highlightEl;
        }

        async detectEntities() {
            if (!this.currentPdfPath) return this.showError('PDFファイルを選択してください');
            this.showLoading(true, '個人情報を検出中...');

            try {
                const response = await fetch('/api/detect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                const data = await response.json();
                if (!data.success) throw new Error(data.message);

                this.detectionResults = data.results || [];
                this.renderEntityList();
                this.renderHighlights();
                this.elements.saveBtn.disabled = false;
                
                const manualCount = data.manual_count || 0;
                const newCount = data.new_count || 0;
                const totalCount = data.count || this.detectionResults.length;
                
                let statusMessage = `検出完了: 新規${newCount}件`;
                if (manualCount > 0) {
                    statusMessage += `, 手動保護${manualCount}件`;
                }
                statusMessage += `, 合計${totalCount}件`;
                
                this.updateStatus(statusMessage);

            } catch (error) {
                console.error('Detection error:', error);
                this.showError(error.message || '個人情報の検出に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }

        renderEntityList() {
            const listEl = this.elements.entityList;
            listEl.innerHTML = '';
            this.elements.resultCount.textContent = this.detectionResults.length;

            if (this.detectionResults.length === 0) {
                listEl.innerHTML = `<div class="list-group-item text-muted">検出結果がここに表示されます</div>`;
                return;
            }

            this.detectionResults.forEach((entity, index) => {
                const item = document.createElement('div');
                item.className = `list-group-item list-group-item-action d-flex justify-content-between align-items-start`;
                if (index === this.selectedEntityIndex) {
                    item.classList.add('active');
                }
                
                const confidence = (entity.confidence * 100).toFixed(0);
                const isManual = entity.manual || false;
                const manualBadge = isManual ? '<span class="badge bg-success ms-1">手動</span>' : '<span class="badge bg-info ms-1">自動</span>';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'flex-grow-1';
                contentDiv.style.cursor = 'pointer';
                contentDiv.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${this.getEntityTypeJapanese(entity.entity_type)}${manualBadge}</h6>
                        <small>信頼度: ${confidence}%</small>
                    </div>
                    <p class="mb-1 text-truncate">${entity.text}</p>
                    <small>ページ: ${entity.page}</small>`;
                
                contentDiv.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.selectEntity(index);
                });
                
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn btn-outline-danger btn-sm';
                deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
                deleteBtn.title = '削除';
                deleteBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    await this.deleteEntity(index);
                });
                
                item.appendChild(contentDiv);
                item.appendChild(deleteBtn);
                listEl.appendChild(item);
            });
        }
        
        selectEntity(index) {
            this.selectedEntityIndex = index;
            const entity = this.detectionResults[index];
            if (entity.page !== this.currentPage) {
                this.changePage(entity.page);
            } else {
                this.renderEntityList();
                this.renderHighlights();
                this.scrollToEntityInPDF(index);
            }
        }

        changePage(newPage) {
            if (this.currentPdfDocument && newPage > 0 && newPage <= this.totalPages) {
                this.currentPage = newPage;
                this.renderPage(this.currentPage).then(() => {
                    // ページ変更後にエンティティが選択されている場合はスクロール
                    if (this.selectedEntityIndex >= 0) {
                        const entity = this.detectionResults[this.selectedEntityIndex];
                        if (entity && entity.page === this.currentPage) {
                            this.scrollToEntityInPDF(this.selectedEntityIndex);
                        }
                    }
                });
            }
        }

        previousPage() { this.changePage(this.currentPage - 1); }
        nextPage() { this.changePage(this.currentPage + 1); }

        updatePageInfo() {
            this.elements.pageInfo.textContent = `${this.currentPage} / ${this.totalPages}`;
            this.elements.prevPageBtn.disabled = this.currentPage <= 1;
            this.elements.nextPageBtn.disabled = this.currentPage >= this.totalPages;
        }

        updateZoom(value) {
            this.zoomLevel = value;
            this.elements.zoomValue.textContent = `${value}%`;
            this.elements.zoomDisplay.textContent = `${value}%`;
            if (this.currentPdfDocument) {
                this.renderPage(this.currentPage);
            }
        }

        async generateAndDownloadPdf() {
            if (!this.currentPdfPath) return this.showError('PDFファイルが選択されていません');
            this.showLoading(true, 'マスキング適用中...');
            
            try {
                const response = await fetch('/api/generate_pdf', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ entities: this.detectionResults })
                });
                const data = await response.json();
                if (!data.success) throw new Error(data.message);

                this.updateStatus('ダウンロード準備完了');
                const link = document.createElement('a');
                link.href = `/api/download_pdf/${data.filename}`;
                link.download = data.download_filename || 'masked_document.pdf';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

            } catch (error) {
                console.error('PDF generation/download error:', error);
                this.showError(error.message || 'PDFの保存に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }

        saveSettings() {
            this.settings.entities = Array.from(document.querySelectorAll('#settingsModal .form-check-input:checked')).map(cb => cb.value);
            this.settings.threshold = parseFloat(this.elements.thresholdSlider.value);
            this.settings.masking_method = document.getElementById('maskingMethod').value;
            this.updateStatus('設定を保存しました');
            const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
            if(modal) modal.hide();
        }

        loadSettings() {
            this.settings.entities.forEach(entityValue => {
                const checkbox = document.querySelector(`#settingsModal input[value="${entityValue}"]`);
                if (checkbox) checkbox.checked = true;
            });
            this.elements.thresholdSlider.value = this.settings.threshold;
            this.elements.thresholdValue.textContent = this.settings.threshold;
            document.getElementById('maskingMethod').value = this.settings.masking_method;
        }

        getEntityTypeJapanese(entityType) {
            const mapping = { "PERSON": "人名", "LOCATION": "場所", "PHONE_NUMBER": "電話番号", "DATE_TIME": "日時", "CUSTOM": "カスタム" };
            return mapping[entityType] || entityType;
        }

        updateStatus(message, isError = false) {
            this.elements.statusMessage.textContent = message;
            this.elements.statusMessage.style.color = isError ? '#dc3545' : '#212529';
            this.elements.statusMessage.style.borderColor = isError ? '#dc3545' : '#17a2b8';
        }
        
        showError(message) {
            this.updateStatus(`エラー: ${message}`, true);
        }

        showLoading(show, message = '処理中...') {
            if (show) {
                this.elements.loadingOverlay.querySelector('p').textContent = message;
                this.elements.loadingOverlay.style.display = 'flex';
            } else {
                this.elements.loadingOverlay.style.display = 'none';
            }
        }

        hideContextMenu() {
            if (this.elements.contextMenu) {
                this.elements.contextMenu.style.display = 'none';
            }
            this.clearTextSelection();
        }
        
        handleSelection(e, isContextMenu = false) {
            try {
                const selection = window.getSelection();
                if (!selection || selection.rangeCount === 0) {
                    if (isContextMenu) this.hideContextMenu();
                    return;
                }

                const range = selection.getRangeAt(0);
                const selectedText = range.toString().trim();
                
                // テキストが空、または選択範囲がtextLayerの外なら何もしない
                if (!selectedText || !this.elements.textLayer.contains(range.commonAncestorContainer)) {
                    if (isContextMenu) this.hideContextMenu();
                    return;
                }

                const rect = range.getBoundingClientRect();
                // ★ 変更点：座標の基準をtextLayerに変更
                const referenceRect = this.elements.textLayer.getBoundingClientRect();
                
                const relativeX = rect.left - referenceRect.left;
                const relativeY = rect.top - referenceRect.top;

                this.currentSelection = {
                    text: selectedText,
                    range: range.cloneRange(),
                    rect: rect,
                    pdfX: relativeX,
                    pdfY: relativeY,
                    pageNumber: this.currentPage
                };

                if (isContextMenu) {
                    this.showContextMenu(e.clientX, e.clientY);
                } else {
                    this.handleModeBasedSelection();
                }

            } catch (error) {
                console.error('Selection handling error:', error);
                this.hideContextMenu();
            }
        }

        showContextMenu(x, y) {
            console.log('showContextMenu called with:', { x, y });
            console.log('contextMenu element:', this.elements.contextMenu);
            console.log('currentSelection:', this.currentSelection);
            
            if (!this.elements.contextMenu || !this.currentSelection) {
                console.log('Early return: missing contextMenu or currentSelection');
                return;
            }
            
            console.log('Setting context menu display to block');
            this.elements.contextMenu.style.display = 'block';
            
            const menuRect = this.elements.contextMenu.getBoundingClientRect();
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;
            
            let menuX = x;
            let menuY = y;
            
            if (x + menuRect.width > windowWidth) {
                menuX = windowWidth - menuRect.width - 10;
            }
            if (y + menuRect.height > windowHeight) {
                menuY = windowHeight - menuRect.height - 10;
            }
            
            this.elements.contextMenu.style.left = menuX + 'px';
            this.elements.contextMenu.style.top = menuY + 'px';
            
            this.bindContextMenuEvents();
        }

        bindContextMenuEvents() {
            const menuItems = this.elements.contextMenu.querySelectorAll('.context-menu-item[data-entity-type]');
            
            menuItems.forEach(item => {
                const newItem = item.cloneNode(true);
                item.parentNode.replaceChild(newItem, item);
                
                newItem.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const entityType = newItem.getAttribute('data-entity-type');
                    this.hideContextMenu();
                    await this.addManualEntity(entityType);
                });
            });

            const cancelBtn = this.elements.contextMenu.querySelector('#cancelSelection');
            if (cancelBtn) {
                const newCancelBtn = cancelBtn.cloneNode(true);
                cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
                
                newCancelBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.hideContextMenu();
                });
            }
        }

        handleModeBasedSelection() {
            const selectedMode = document.querySelector('input[name="entityMode"]:checked');
            if (!selectedMode || !selectedMode.value) {
                this.updateStatus('手動追加するには、まずエンティティタイプ（人名など）を選択してください。', false);
                this.clearTextSelection();
                return;
            }

            const entityType = selectedMode.value;
            this.addManualEntity(entityType);
        }

        async addManualEntity(entityType) {
            if (!this.currentSelection || !this.currentSelection.text.trim()) {
                return;
            }
            if (!this.viewport) {
                return;
            }

            console.log('Adding manual entity:', {
                entityType,
                text: this.currentSelection.text,
                selection: this.currentSelection
            });

            // 座標の安全な計算（エラーが出ても続行）
            let coordinates = {
                x0: 100,
                y0: 100,
                x1: 200,
                y1: 120
            };
            
            if (this.currentSelection.pdfX !== undefined && this.currentSelection.pdfY !== undefined && 
                this.currentSelection.rect && this.viewport) {
                
                const viewportRect = [
                    this.currentSelection.pdfX || 0,
                    this.currentSelection.pdfY || 0,
                    (this.currentSelection.pdfX || 0) + (this.currentSelection.rect?.width || 100),
                    (this.currentSelection.pdfY || 0) + (this.currentSelection.rect?.height || 20)
                ];
                
                const pdfPoint1 = this.viewport.convertToPdfPoint(viewportRect[0], viewportRect[1]);
                const pdfPoint2 = this.viewport.convertToPdfPoint(viewportRect[2], viewportRect[3]);
                const pageHeight = this.viewport.viewBox[3];
                
                coordinates = {
                    x0: Math.min(pdfPoint1[0], pdfPoint2[0]),
                    y0: pageHeight - Math.max(pdfPoint1[1], pdfPoint2[1]),
                    x1: Math.max(pdfPoint1[0], pdfPoint2[0]),
                    y1: pageHeight - Math.min(pdfPoint1[1], pdfPoint2[1])
                };
            }
            
            const newEntity = {
                entity_type: entityType,
                text: this.currentSelection.text,
                start: 0,
                end: this.currentSelection.text.length,
                confidence: 1.0,
                page: this.currentPage,
                coordinates: coordinates,
                manual: true
            };

            console.log('Sending entity to server:', newEntity);

            // サーバーに送信（エラーが出ても無視）
            fetch('/api/highlights/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newEntity),
            })
            .then(response => response.json())
            .then(data => {
                console.log('Server response:', data);
                
                if (data.success && data.entity) {
                    // UIの更新
                    this.detectionResults.push(data.entity);
                    this.renderEntityList();
                    this.renderHighlights();
                    this.updateResultCount();
                    this.updateStatus(`手動追加: ${this.getEntityTypeLabel(entityType)} "${this.currentSelection.text}"`);
                    console.log('Manual entity added successfully');
                }
            })
            .catch(error => {
                console.log('Request failed but continuing silently:', error);
                // エラーメッセージは表示しない
            });

            // 常に選択をクリア
            this.clearTextSelection();
        }

        getEntityTypeLabel(entityType) {
            const labels = {
                'PERSON': '人名',
                'LOCATION': '場所',
                'PHONE_NUMBER': '電話番号',
                'DATE_TIME': '日時',
                'CUSTOM': 'その他'
            };
            return labels[entityType] || entityType;
        }

        addToSelectionHistory(selectionData) {
            // 重複チェック（同じテキストと座標の場合は追加しない）
            const isDuplicate = this.selectionHistory.some(item => 
                item.text === selectionData.text &&
                Math.abs(item.pdfX - selectionData.pdfX) < 5 &&
                Math.abs(item.pdfY - selectionData.pdfY) < 5 &&
                item.pageNumber === selectionData.pageNumber
            );
            
            if (!isDuplicate) {
                this.selectionHistory.unshift(selectionData);
                
                // 最大数を超えた場合は古いものを削除
                if (this.selectionHistory.length > this.maxSelectionHistory) {
                    this.selectionHistory = this.selectionHistory.slice(0, this.maxSelectionHistory);
                }
                
                console.log(`Selection history updated: ${this.selectionHistory.length} items`);
            }
        }
        
        getLatestValidSelection() {
            // 最新の有効な選択を取得（過去5秒以内のもの）
            const fiveSecondsAgo = Date.now() - 5000;
            
            for (let selection of this.selectionHistory) {
                if (selection.timestamp > fiveSecondsAgo && 
                    selection.pageNumber === this.currentPage &&
                    selection.text && selection.text.length > 0) {
                    console.log(`Found valid selection from history: "${selection.text}"`);
                    return selection;
                }
            }
            
            console.log('No valid selection found in history');
            return null;
        }

        clearTextSelection() {
            if (window.getSelection) {
                window.getSelection().removeAllRanges();
            }
            this.currentSelection = null;
        }

        updateResultCount() {
            if (this.elements.resultCount) {
                this.elements.resultCount.textContent = this.detectionResults.length;
            }
        }

        scrollToEntityInList(index) {
            const listEl = this.elements.entityList;
            const items = listEl.querySelectorAll('.list-group-item');
            
            if (index >= 0 && index < items.length) {
                const item = items[index];
                item.scrollIntoView({
                    behavior: 'smooth',
                    block: 'center'
                });
            }
        }

        scrollToEntityInPDF(index) {
            const entity = this.detectionResults[index];
            if (!entity || !entity.coordinates || entity.page !== this.currentPage) {
                return;
            }

            // ハイライト要素を取得
            const highlightEl = this.elements.highlightOverlay.querySelector(`[data-index="${index}"]`);
            if (!highlightEl) {
                return;
            }

            // PDFビューアコンテナを取得
            const pdfViewer = this.elements.pdfViewer;
            const pdfContainer = this.elements.pdfCanvasContainer;
            
            // ハイライト要素の位置を取得
            const highlightRect = highlightEl.getBoundingClientRect();
            const viewerRect = pdfViewer.getBoundingClientRect();
            
            // ハイライトがビューアの表示範囲内にあるかチェック
            const isVisible = (
                highlightRect.top >= viewerRect.top &&
                highlightRect.bottom <= viewerRect.bottom &&
                highlightRect.left >= viewerRect.left &&
                highlightRect.right <= viewerRect.right
            );
            
            // 表示範囲外の場合はスクロール
            if (!isVisible) {
                // ハイライト要素がビューアの中央に来るようにスクロール
                const targetTop = highlightRect.top - viewerRect.top + pdfViewer.scrollTop - (viewerRect.height / 2) + (highlightRect.height / 2);
                const targetLeft = highlightRect.left - viewerRect.left + pdfViewer.scrollLeft - (viewerRect.width / 2) + (highlightRect.width / 2);
                
                pdfViewer.scrollTo({
                    top: Math.max(0, targetTop),
                    left: Math.max(0, targetLeft),
                    behavior: 'smooth'
                });
            }
        }
        
        async deleteEntity(index) {
            try {
                if (index < 0 || index >= this.detectionResults.length) {
                    this.showError('無効なエンティティです');
                    return;
                }
                
                const entity = this.detectionResults[index];
                
                this.showLoading(true, 'エンティティを削除中...');
                
                const response = await fetch(`/api/delete_entity/${index}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                if (!data.success) throw new Error(data.message);
                
                this.detectionResults.splice(index, 1);
                
                if (this.selectedEntityIndex === index) {
                    this.selectedEntityIndex = -1;
                } else if (this.selectedEntityIndex > index) {
                    this.selectedEntityIndex--;
                }
                
                this.renderEntityList();
                this.renderHighlights();
                this.updateResultCount();
                this.updateStatus(`削除完了: ${data.deleted_entity.text}`);
                
            } catch (error) {
                console.error('Delete entity error:', error);
                this.showError(error.message || 'エンティティの削除に失敗しました');
            } finally {
                this.showLoading(false);
            }
        }
    }

    new PresidioPDFWebApp();
});